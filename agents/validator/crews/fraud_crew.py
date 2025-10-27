"""
Fraud Detection Crew

Detects potential fraud, malicious data, or suspicious patterns using CrewAI.
"""

from crewai import Agent, Task, Crew, Process
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class FraudDetectionCrew:
    """CrewAI crew for fraud detection"""

    def __init__(self, model: str = "gpt-4o"):
        """Initialize fraud detection crew"""
        self.model = model

        # Create fraud analyst agent
        self.fraud_analyst = Agent(
            role="Fraud Detection Specialist",
            goal="Detect fraudulent data, scams, and malicious content",
            backstory="""You are a seasoned fraud detection specialist with expertise in
            identifying fake data, scams, phishing attempts, and malicious content. You have
            an exceptional ability to spot patterns that indicate fraud or deception.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        # Create pattern analyzer agent
        self.pattern_analyzer = Agent(
            role="Pattern Anomaly Detector",
            goal="Identify suspicious patterns and anomalies in data",
            backstory="""You specialize in detecting unusual patterns, statistical anomalies,
            and irregularities that could indicate fraudulent or artificially generated data.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        # Create authenticity checker agent
        self.authenticity_checker = Agent(
            role="Authenticity Verifier",
            goal="Verify data authenticity and detect synthetic/fake content",
            backstory="""You are an expert at distinguishing genuine data from fake or
            artificially generated content. You can detect AI-generated text, manipulated
            data, and other forms of inauthentic information.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        logger.info("Fraud detection crew initialized")

    def detect(
        self,
        data_type: str,
        data_content: Dict[str, Any],
        seller_address: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Detect potential fraud in data

        Returns:
            {
                "score": float (0.0-1.0, higher = more likely fraud),
                "reasoning": str,
                "red_flags": List[str],
                "confidence": float
            }
        """
        metadata = metadata or {}

        logger.info(f"Starting fraud detection for {data_type} from {seller_address}")

        try:
            # Create fraud detection tasks
            fraud_task = Task(
                description=f"""Analyze this {data_type} data for signs of fraud or malicious intent:

                Data Content: {str(data_content)[:1000]}...
                Seller: {seller_address}
                Metadata: {metadata}

                Look for:
                1. Obvious fraud indicators (phishing, scams, fake data)
                2. Suspicious patterns or inconsistencies
                3. Malicious content or intent
                4. Data that appears too good to be true

                Provide a fraud risk score from 0.0 (no fraud) to 1.0 (definite fraud).""",
                agent=self.fraud_analyst,
                expected_output="Fraud risk score (0.0-1.0) with detailed red flags"
            )

            pattern_task = Task(
                description=f"""Analyze patterns in this {data_type} data for anomalies:

                Data Content: {str(data_content)[:1000]}...

                Detect:
                1. Statistical anomalies
                2. Unusual patterns that deviate from expected norms
                3. Signs of data manipulation or fabrication
                4. Repetitive or template-based content

                Provide an anomaly score from 0.0 (normal) to 1.0 (highly anomalous).""",
                agent=self.pattern_analyzer,
                expected_output="Anomaly score (0.0-1.0) with pattern analysis"
            )

            authenticity_task = Task(
                description=f"""Verify the authenticity of this {data_type} data:

                Data Content: {str(data_content)[:1000]}...

                Check for:
                1. AI-generated or synthetic content
                2. Copied/plagiarized data
                3. Manipulated or edited content
                4. Signs of genuine human-generated data

                Provide an inauthenticity score from 0.0 (genuine) to 1.0 (fake).""",
                agent=self.authenticity_checker,
                expected_output="Inauthenticity score (0.0-1.0) with authenticity assessment"
            )

            # Create and run crew
            crew = Crew(
                agents=[self.fraud_analyst, self.pattern_analyzer, self.authenticity_checker],
                tasks=[fraud_task, pattern_task, authenticity_task],
                process=Process.sequential,
                verbose=True
            )

            # Execute crew
            result = crew.kickoff()

            # Parse result and extract fraud score
            fraud_score = self._parse_fraud_score(str(result))

            return {
                "score": fraud_score,
                "reasoning": f"Fraud analysis: {str(result)[:200]}...",
                "red_flags": self._extract_red_flags(str(result)),
                "confidence": self._calculate_confidence(fraud_score)
            }

        except Exception as e:
            logger.error(f"Fraud detection failed: {e}")
            # Return conservative score on error
            return {
                "score": 0.5,
                "reasoning": f"Fraud detection encountered an error: {str(e)}",
                "red_flags": ["Analysis error occurred"],
                "confidence": 0.3
            }

    def _parse_fraud_score(self, result: str) -> float:
        """Parse fraud score from crew result"""
        import re

        # Look for fraud-related scores
        patterns = [
            r'fraud[:\s]+([0-9.]+)',
            r'risk[:\s]+([0-9.]+)',
            r'suspicious[:\s]+([0-9.]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, result.lower())
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))

        # Look for negative keywords to estimate fraud risk
        fraud_keywords = ["fraud", "fake", "suspicious", "scam", "malicious"]
        fraud_mentions = sum(1 for keyword in fraud_keywords if keyword in result.lower())

        # Simple heuristic: more fraud keywords = higher fraud score
        if fraud_mentions >= 3:
            return 0.7
        elif fraud_mentions >= 2:
            return 0.4
        elif fraud_mentions >= 1:
            return 0.2
        else:
            return 0.1

    def _extract_red_flags(self, result: str) -> list:
        """Extract red flags from crew result"""
        red_flags = []

        # Keywords that indicate potential issues
        fraud_indicators = [
            ("fake", "Potentially fake data detected"),
            ("suspicious", "Suspicious patterns found"),
            ("scam", "Possible scam detected"),
            ("malicious", "Malicious intent suspected"),
            ("manipulated", "Data manipulation detected"),
            ("generated", "AI-generated content suspected"),
            ("anomaly", "Statistical anomalies detected")
        ]

        for keyword, flag in fraud_indicators:
            if keyword in result.lower():
                red_flags.append(flag)

        return red_flags[:5]  # Limit to 5 red flags

    def _calculate_confidence(self, fraud_score: float) -> float:
        """Calculate confidence in the fraud assessment"""
        # Higher confidence for extreme scores (very low or very high fraud)
        # Lower confidence for middle-range scores (uncertain)
        distance_from_middle = abs(fraud_score - 0.5)
        confidence = 0.5 + (distance_from_middle * 1.0)  # Scale to 0.5-1.0
        return round(confidence, 2)
