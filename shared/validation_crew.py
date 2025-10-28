#!/usr/bin/env python3
"""
Validation CrewAI Crew for Karmacadabra

Reusable multi-agent validation pattern for data quality verification.
Used by Validator agent and can be adapted by other agents needing
data validation capabilities.

Pattern:
1. Quality Analyst - verifies completeness, schemas, timestamps
2. Fraud Detector - detects duplicates, verifies authenticity
3. Price Reviewer - verifies fair pricing

Usage:
    crew = ValidationCrew(openai_api_key="sk-...")
    result = await crew.validate(
        data=transaction_data,
        data_type="logs",
        seller_id=1,
        buyer_id=2
    )
    score = result.score  # 0-100
"""

import os
import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass

try:
    from crewai import Agent, Task, Crew, Process
    from crewai.tools import BaseTool
except ImportError:
    raise ImportError(
        "CrewAI not installed. Install with: pip install crewai>=0.28.0"
    )


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ValidationResult:
    """
    Result of validation crew execution

    Attributes:
        score: Overall validation score (0-100)
        quality_score: Quality analyst score
        fraud_score: Fraud detector score
        price_score: Price reviewer score
        report: Detailed validation report
        passed: Whether validation passed threshold
        issues: List of detected issues
    """
    score: int
    quality_score: int
    fraud_score: int
    price_score: int
    report: str
    passed: bool
    issues: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "score": self.score,
            "quality_score": self.quality_score,
            "fraud_score": self.fraud_score,
            "price_score": self.price_score,
            "report": self.report,
            "passed": self.passed,
            "issues": self.issues
        }


# =============================================================================
# CREWAI TOOLS
# =============================================================================

class CheckSchemaTool(BaseTool):
    """Tool for validating JSON schema compliance"""

    name: str = "check_schema"
    description: str = "Validates that data conforms to expected JSON schema"

    def _run(self, data: Any, schema: Dict) -> str:
        """
        Check if data matches schema

        Args:
            data: Data to validate
            schema: JSON schema definition

        Returns:
            str: Validation result message
        """
        # Basic schema validation (can be enhanced with jsonschema library)
        required_fields = schema.get("required", [])
        properties = schema.get("properties", {})

        if not isinstance(data, dict):
            return f"FAIL: Expected dict, got {type(data).__name__}"

        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return f"FAIL: Missing required fields: {missing_fields}"

        for field, expected_type in properties.items():
            if field in data:
                actual_type = type(data[field]).__name__
                if "type" in expected_type and actual_type != expected_type["type"]:
                    return f"FAIL: Field '{field}' type mismatch"

        return "PASS: Schema validation successful"


class VerifyTimestampsTool(BaseTool):
    """Tool for verifying timestamp validity"""

    name: str = "verify_timestamps"
    description: str = "Checks if timestamps are valid and recent"

    def _run(self, data: Any, max_age_days: int = 30) -> str:
        """
        Verify timestamps in data

        Args:
            data: Data containing timestamps
            max_age_days: Maximum age in days

        Returns:
            str: Verification result
        """
        now = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        if isinstance(data, dict) and "timestamp" in data:
            timestamp = data["timestamp"]
            if not isinstance(timestamp, (int, float)):
                return "FAIL: Timestamp not numeric"

            if timestamp > now:
                return "FAIL: Timestamp in future"

            age = now - timestamp
            if age > max_age_seconds:
                return f"WARN: Timestamp older than {max_age_days} days"

            return "PASS: Timestamp valid"

        elif isinstance(data, list):
            # Check all timestamps in list
            for item in data:
                if isinstance(item, dict) and "timestamp" in item:
                    ts = item["timestamp"]
                    if not isinstance(ts, (int, float)) or ts > now:
                        return "FAIL: Invalid timestamp found"

            return "PASS: All timestamps valid"

        return "SKIP: No timestamps found"


class SimilarityCheckTool(BaseTool):
    """Tool for detecting duplicate or similar data"""

    name: str = "similarity_check"
    description: str = "Detects duplicate or suspiciously similar data"

    def _run(self, data: Any, threshold: float = 0.95) -> str:
        """
        Check for duplicates

        Args:
            data: Data to check
            threshold: Similarity threshold (0-1)

        Returns:
            str: Check result
        """
        if isinstance(data, list):
            # Check for exact duplicates
            unique_items = set(json.dumps(item, sort_keys=True) for item in data)
            duplicate_count = len(data) - len(unique_items)

            if duplicate_count > 0:
                duplicate_pct = (duplicate_count / len(data)) * 100
                return f"WARN: Found {duplicate_count} duplicates ({duplicate_pct:.1f}%)"

            return "PASS: No duplicates detected"

        return "SKIP: Single item, cannot check for duplicates"


class MarketCheckTool(BaseTool):
    """Tool for checking market price fairness"""

    name: str = "market_check"
    description: str = "Verifies price is fair compared to market rates"

    def _run(self, price: str, data_type: str, data_size: int) -> str:
        """
        Check price fairness

        Args:
            price: Price in GLUE
            data_type: Type of data (logs, transcript, etc.)
            data_size: Size of data in bytes or items

        Returns:
            str: Price check result
        """
        # Market rates (GLUE per 1000 items or 1MB)
        market_rates = {
            "logs": Decimal("0.01"),  # 0.01 GLUE per 1000 messages
            "transcript": Decimal("0.02"),  # 0.02 GLUE per transcript
            "ideas": Decimal("1.20"),  # 1.20 GLUE for idea extraction
            "images": Decimal("0.80")  # 0.80 GLUE for image generation
        }

        try:
            price_decimal = Decimal(price)
            expected_rate = market_rates.get(data_type, Decimal("0.01"))

            # Calculate expected price based on size
            if data_type == "logs":
                expected = expected_rate * (data_size / 1000)
            else:
                expected = expected_rate

            # Check if within 20% of expected
            diff_pct = abs(price_decimal - expected) / expected * 100

            if diff_pct > 20:
                return f"WARN: Price {price_pct:.0f}% from market rate"

            return "PASS: Price is fair"

        except (ValueError, TypeError):
            return f"FAIL: Invalid price format: {price}"


# =============================================================================
# VALIDATION CREW
# =============================================================================

class ValidationCrew:
    """
    CrewAI-based validation crew

    Orchestrates three agents to validate transaction data:
    - Quality Analyst: Data completeness and format
    - Fraud Detector: Duplicate and authenticity checks
    - Price Reviewer: Price fairness verification

    Example:
        crew = ValidationCrew()
        result = crew.validate(
            data={"messages": [...]},
            data_type="logs",
            seller_id=1,
            buyer_id=2
        )
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o",
        verbose: bool = False
    ):
        """
        Initialize validation crew

        Args:
            openai_api_key: OpenAI API key (or set OPENAI_API_KEY env)
            model: OpenAI model to use (default: gpt-4o)
            verbose: Enable verbose logging
        """
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.verbose = verbose

        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required for CrewAI agents")

        # Initialize agents
        self._setup_agents()

    def _setup_agents(self):
        """Create the three validation agents"""

        # Agent 1: Quality Analyst
        self.quality_analyst = Agent(
            role="Data Quality Analyst",
            goal="Verify data completeness, format correctness, and schema compliance",
            backstory=(
                "You are an expert data quality analyst with 15+ years of experience "
                "in data validation. You meticulously check data schemas, timestamps, "
                "required fields, and data integrity. Your analysis is thorough and precise."
            ),
            tools=[
                CheckSchemaTool(),
                VerifyTimestampsTool()
            ],
            verbose=self.verbose,
            allow_delegation=False
        )

        # Agent 2: Fraud Detector
        self.fraud_detector = Agent(
            role="Fraud Detection Specialist",
            goal="Detect fake, duplicate, or manipulated data",
            backstory=(
                "You are a forensic data analyst specialized in fraud detection. "
                "You identify patterns that indicate data manipulation, spot duplicates, "
                "and verify data authenticity. Your vigilance protects buyers from scams."
            ),
            tools=[
                SimilarityCheckTool()
            ],
            verbose=self.verbose,
            allow_delegation=False
        )

        # Agent 3: Price Reviewer
        self.price_reviewer = Agent(
            role="Price Fairness Reviewer",
            goal="Ensure pricing is fair and competitive based on market rates",
            backstory=(
                "You are a market analyst with deep knowledge of data pricing in the "
                "AI agent economy. You compare prices against market rates, data quality, "
                "and historical pricing to ensure buyers get fair value."
            ),
            tools=[
                MarketCheckTool()
            ],
            verbose=self.verbose,
            allow_delegation=False
        )

    def validate(
        self,
        data: Any,
        data_type: str,
        seller_id: int,
        buyer_id: int,
        price: Optional[str] = None
    ) -> ValidationResult:
        """
        Execute validation crew on transaction data

        Args:
            data: Data to validate
            data_type: Type of data ("logs", "transcript", etc.)
            seller_id: Seller agent ID
            buyer_id: Buyer agent ID
            price: Price in GLUE (optional)

        Returns:
            ValidationResult: Validation scores and report
        """
        # Create tasks for each agent
        tasks = [
            Task(
                description=(
                    f"Analyze the quality of {data_type} data:\n"
                    f"- Check schema compliance\n"
                    f"- Verify timestamps are valid and recent\n"
                    f"- Ensure all required fields are present\n"
                    f"- Rate quality from 0-100\n\n"
                    f"Data: {json.dumps(data)[:500]}..."
                ),
                agent=self.quality_analyst,
                expected_output="Quality score (0-100) with detailed analysis"
            ),
            Task(
                description=(
                    f"Detect fraud indicators in {data_type} data:\n"
                    f"- Check for duplicate entries\n"
                    f"- Verify data authenticity\n"
                    f"- Look for manipulation patterns\n"
                    f"- Rate fraud risk from 0-100 (100 = no fraud)\n\n"
                    f"Data: {json.dumps(data)[:500]}..."
                ),
                agent=self.fraud_detector,
                expected_output="Fraud score (0-100) with risk assessment"
            ),
            Task(
                description=(
                    f"Review price fairness for {data_type}:\n"
                    f"- Price: {price or 'N/A'} GLUE\n"
                    f"- Seller: Agent #{seller_id}\n"
                    f"- Buyer: Agent #{buyer_id}\n"
                    f"- Compare against market rates\n"
                    f"- Rate fairness from 0-100\n"
                ),
                agent=self.price_reviewer,
                expected_output="Price fairness score (0-100) with market comparison"
            )
        ]

        # Execute crew
        crew = Crew(
            agents=[
                self.quality_analyst,
                self.fraud_detector,
                self.price_reviewer
            ],
            tasks=tasks,
            process=Process.sequential,
            verbose=self.verbose
        )

        result = crew.kickoff()

        # Extract scores from crew output
        scores = self._extract_scores(str(result))

        # Calculate overall score (weighted average)
        overall_score = int(
            scores["quality"] * 0.4 +
            scores["fraud"] * 0.3 +
            scores["price"] * 0.3
        )

        # Determine pass/fail (threshold: 70)
        passed = overall_score >= 70

        # Extract issues
        issues = self._extract_issues(str(result))

        return ValidationResult(
            score=overall_score,
            quality_score=scores["quality"],
            fraud_score=scores["fraud"],
            price_score=scores["price"],
            report=str(result),
            passed=passed,
            issues=issues
        )

    def _extract_scores(self, report: str) -> Dict[str, int]:
        """
        Extract numeric scores from crew report

        Args:
            report: Crew kickoff output

        Returns:
            dict: Scores for quality, fraud, price
        """
        # Simple extraction - looks for patterns like "Score: 85"
        import re

        scores = {
            "quality": 50,  # Default
            "fraud": 50,
            "price": 50
        }

        # Try to extract scores from report
        quality_match = re.search(r"quality.*?(\d+)", report, re.IGNORECASE)
        if quality_match:
            scores["quality"] = int(quality_match.group(1))

        fraud_match = re.search(r"fraud.*?(\d+)", report, re.IGNORECASE)
        if fraud_match:
            scores["fraud"] = int(fraud_match.group(1))

        price_match = re.search(r"price.*?(\d+)", report, re.IGNORECASE)
        if price_match:
            scores["price"] = int(price_match.group(1))

        return scores

    def _extract_issues(self, report: str) -> List[str]:
        """
        Extract detected issues from report

        Args:
            report: Crew kickoff output

        Returns:
            list: List of issue descriptions
        """
        issues = []

        # Look for common issue indicators
        issue_keywords = ["FAIL", "WARN", "MISSING", "INVALID", "DUPLICATE", "FRAUD"]

        for line in report.split("\n"):
            if any(keyword in line.upper() for keyword in issue_keywords):
                issues.append(line.strip())

        return issues


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Validation Crew Example")
    print("=" * 70)
    print()

    # Example data: Twitch chat logs
    example_data = {
        "stream_id": "12345",
        "messages": [
            {
                "timestamp": int(time.time() - 3600),  # 1 hour ago
                "user": "alice",
                "message": "Great stream!"
            },
            {
                "timestamp": int(time.time() - 3000),
                "user": "bob",
                "message": "PogChamp"
            }
        ]
    }

    print("[1] Validation Crew Components:")
    print("    - Quality Analyst: Schema + timestamp validation")
    print("    - Fraud Detector: Duplicate detection")
    print("    - Price Reviewer: Market rate comparison")
    print()

    print("[2] Example Usage:")
    print(f"    crew = ValidationCrew()")
    print(f"    result = crew.validate(")
    print(f"        data=logs_data,")
    print(f"        data_type='logs',")
    print(f"        seller_id=1,")
    print(f"        buyer_id=2,")
    print(f"        price='0.01'")
    print(f"    )")
    print()

    print("[3] Expected Output:")
    print("    ValidationResult(")
    print("        score=85,")
    print("        quality_score=90,")
    print("        fraud_score=95,")
    print("        price_score=70,")
    print("        passed=True,")
    print("        issues=[]")
    print("    )")
    print()

    print("=" * 70)
    print("Pattern complete! Use this crew in Validator agent.")
    print("=" * 70)
