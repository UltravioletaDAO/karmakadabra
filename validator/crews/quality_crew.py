"""
Quality Validation Crew

Analyzes data quality, completeness, and accuracy using CrewAI multi-agent system.
"""

from crewai import Agent, Task, Crew, Process
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class QualityValidationCrew:
    """CrewAI crew for data quality validation"""

    def __init__(self, model: str = "gpt-4o"):
        """Initialize quality validation crew"""
        self.model = model

        # Create quality analyst agent
        self.quality_analyst = Agent(
            role="Data Quality Analyst",
            goal="Analyze data quality, completeness, format, and accuracy",
            backstory="""You are an expert data quality analyst with years of experience
            evaluating data for completeness, accuracy, consistency, and format compliance.
            You have a keen eye for missing information, formatting issues, and data anomalies.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        # Create completeness checker agent
        self.completeness_checker = Agent(
            role="Completeness Checker",
            goal="Verify data completeness and identify missing fields",
            backstory="""You specialize in checking data completeness. You identify missing
            fields, incomplete records, and gaps in data that could affect its value.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        # Create format validator agent
        self.format_validator = Agent(
            role="Format Validator",
            goal="Validate data format and structure compliance",
            backstory="""You are a technical validator who checks data formats, schemas,
            and structural compliance. You ensure data meets expected formats and standards.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        logger.info("Quality validation crew initialized")

    def validate(
        self,
        data_type: str,
        data_content: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Validate data quality using CrewAI crew

        Returns:
            {
                "score": float (0.0-1.0),
                "reasoning": str,
                "issues": List[str],
                "strengths": List[str]
            }
        """
        metadata = metadata or {}

        logger.info(f"Starting quality validation for {data_type}")

        try:
            # Create validation tasks
            quality_task = Task(
                description=f"""Analyze the quality of this {data_type} data:

                Data Content: {str(data_content)[:1000]}...
                Metadata: {metadata}

                Evaluate:
                1. Overall data quality (accuracy, precision)
                2. Data consistency
                3. Potential issues or anomalies
                4. Value for the intended use case

                Provide a quality score from 0.0 to 1.0 and detailed reasoning.""",
                agent=self.quality_analyst,
                expected_output="Quality score (0.0-1.0) with detailed reasoning"
            )

            completeness_task = Task(
                description=f"""Check the completeness of this {data_type} data:

                Data Content: {str(data_content)[:1000]}...

                Evaluate:
                1. Are all expected fields present?
                2. Are there missing or null values?
                3. Is the data complete enough for its purpose?
                4. What critical information is missing (if any)?

                Provide a completeness score from 0.0 to 1.0.""",
                agent=self.completeness_checker,
                expected_output="Completeness score (0.0-1.0) with list of missing elements"
            )

            format_task = Task(
                description=f"""Validate the format and structure of this {data_type} data:

                Data Content: {str(data_content)[:1000]}...

                Evaluate:
                1. Is the data properly formatted?
                2. Does it follow expected schema/structure?
                3. Are data types correct?
                4. Are there formatting inconsistencies?

                Provide a format compliance score from 0.0 to 1.0.""",
                agent=self.format_validator,
                expected_output="Format score (0.0-1.0) with format issues identified"
            )

            # Create and run crew
            crew = Crew(
                agents=[self.quality_analyst, self.completeness_checker, self.format_validator],
                tasks=[quality_task, completeness_task, format_task],
                process=Process.sequential,
                verbose=True
            )

            # Execute crew
            result = crew.kickoff()

            # Parse result and extract scores
            # In a real implementation, you'd parse the crew output more carefully
            # For now, we'll return a simplified result
            score = self._parse_quality_score(str(result))

            return {
                "score": score,
                "reasoning": f"Quality analysis: {str(result)[:200]}...",
                "issues": self._extract_issues(str(result)),
                "strengths": self._extract_strengths(str(result))
            }

        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            # Return conservative score on error
            return {
                "score": 0.5,
                "reasoning": f"Quality validation encountered an error: {str(e)}",
                "issues": ["Validation error occurred"],
                "strengths": []
            }

    def _parse_quality_score(self, result: str) -> float:
        """Parse quality score from crew result"""
        # Look for patterns like "score: 0.8" or "quality: 0.75"
        import re

        patterns = [
            r'score[:\s]+([0-9.]+)',
            r'quality[:\s]+([0-9.]+)',
            r'rating[:\s]+([0-9.]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, result.lower())
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))  # Clamp to [0, 1]

        # Default to moderate score if parsing fails
        return 0.7

    def _extract_issues(self, result: str) -> list:
        """Extract issues from crew result"""
        # Simple extraction - look for negative keywords
        issues = []
        negative_keywords = ["missing", "incomplete", "error", "issue", "problem", "invalid"]

        for keyword in negative_keywords:
            if keyword in result.lower():
                issues.append(f"Potential {keyword} detected")

        return issues[:5]  # Limit to 5 issues

    def _extract_strengths(self, result: str) -> list:
        """Extract strengths from crew result"""
        # Simple extraction - look for positive keywords
        strengths = []
        positive_keywords = ["complete", "accurate", "valid", "good", "excellent", "strong"]

        for keyword in positive_keywords:
            if keyword in result.lower():
                strengths.append(f"Strong {keyword} rating")

        return strengths[:5]  # Limit to 5 strengths
