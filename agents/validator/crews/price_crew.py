"""
Price Review Crew

Reviews pricing fairness and value assessment using CrewAI.
"""

from crewai import Agent, Task, Crew, Process
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class PriceReviewCrew:
    """CrewAI crew for price review and fairness assessment"""

    def __init__(self, model: str = "gpt-4o"):
        """Initialize price review crew"""
        self.model = model

        # Create price analyst agent
        self.price_analyst = Agent(
            role="Pricing Analyst",
            goal="Evaluate pricing fairness and market value",
            backstory="""You are an experienced pricing analyst who understands market
            dynamics, value assessment, and fair pricing strategies. You can quickly
            determine if a price is reasonable given the data quality and quantity.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        # Create value assessor agent
        self.value_assessor = Agent(
            role="Value Assessor",
            goal="Assess the actual value of data based on quality and utility",
            backstory="""You specialize in assessing the true value of data based on its
            quality, completeness, uniqueness, and potential utility. You understand what
            makes data valuable in different contexts.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        # Create market comparator agent
        self.market_comparator = Agent(
            role="Market Price Comparator",
            goal="Compare prices against market standards and benchmarks",
            backstory="""You have extensive knowledge of data marketplace pricing and can
            compare prices against industry standards and comparable offerings.""",
            verbose=True,
            allow_delegation=False,
            llm=model
        )

        logger.info("Price review crew initialized")

    def review(
        self,
        data_type: str,
        data_size: int,
        price_glue: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Review price fairness

        Returns:
            {
                "score": float (0.0-1.0, higher = fairer price),
                "reasoning": str,
                "fair_price_range": Dict[str, str],
                "recommendation": str
            }
        """
        metadata = metadata or {}

        logger.info(f"Starting price review for {data_type} at {price_glue} GLUE")

        try:
            # Create price review tasks
            price_task = Task(
                description=f"""Evaluate the fairness of this pricing:

                Data Type: {data_type}
                Data Size: {data_size} bytes
                Asking Price: {price_glue} GLUE
                Metadata: {metadata}

                Consider:
                1. Is this price reasonable for the data type and quantity?
                2. Does it align with market expectations?
                3. Is the seller overcharging or undercharging?
                4. What would be a fair price range?

                Provide a price fairness score from 0.0 (unfair) to 1.0 (very fair).""",
                agent=self.price_analyst,
                expected_output="Price fairness score (0.0-1.0) with reasoning"
            )

            value_task = Task(
                description=f"""Assess the value of this data:

                Data Type: {data_type}
                Data Size: {data_size} bytes
                Asking Price: {price_glue} GLUE

                Evaluate:
                1. What is the estimated value of this data?
                2. How useful/valuable is this data type generally?
                3. Does the price match the value?
                4. Is this data worth paying for?

                Provide a value-to-price ratio from 0.0 (overpriced) to 1.0 (underpriced).""",
                agent=self.value_assessor,
                expected_output="Value assessment with recommended price range"
            )

            market_task = Task(
                description=f"""Compare this price against market benchmarks:

                Data Type: {data_type}
                Data Size: {data_size} bytes
                Asking Price: {price_glue} GLUE

                Compare against:
                1. Typical market prices for similar data
                2. Industry standards for this data type
                3. Price per byte/record benchmarks
                4. Historical pricing trends

                Provide a market alignment score from 0.0 (way off market) to 1.0 (perfectly aligned).""",
                agent=self.market_comparator,
                expected_output="Market comparison with price positioning analysis"
            )

            # Create and run crew
            crew = Crew(
                agents=[self.price_analyst, self.value_assessor, self.market_comparator],
                tasks=[price_task, value_task, market_task],
                process=Process.sequential,
                verbose=True
            )

            # Execute crew
            result = crew.kickoff()

            # Parse result and extract price score
            price_score = self._parse_price_score(str(result))

            # Extract fair price range
            fair_price_range = self._extract_price_range(str(result), price_glue)

            # Generate recommendation
            recommendation = self._generate_recommendation(price_score, price_glue, fair_price_range)

            return {
                "score": price_score,
                "reasoning": f"Price analysis: {str(result)[:200]}...",
                "fair_price_range": fair_price_range,
                "recommendation": recommendation
            }

        except Exception as e:
            logger.error(f"Price review failed: {e}")
            # Return moderate score on error
            return {
                "score": 0.6,
                "reasoning": f"Price review encountered an error: {str(e)}",
                "fair_price_range": {"min": "unknown", "max": "unknown"},
                "recommendation": "Unable to assess - review manually"
            }

    def _parse_price_score(self, result: str) -> float:
        """Parse price fairness score from crew result"""
        import re

        # Look for price-related scores
        patterns = [
            r'fairness[:\s]+([0-9.]+)',
            r'fair[:\s]+([0-9.]+)',
            r'score[:\s]+([0-9.]+)',
            r'value[:\s]+([0-9.]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, result.lower())
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))

        # Look for keywords indicating price fairness
        if "overpriced" in result.lower() or "expensive" in result.lower():
            return 0.4
        elif "underpriced" in result.lower() or "cheap" in result.lower():
            return 0.9
        elif "fair" in result.lower() or "reasonable" in result.lower():
            return 0.8
        else:
            return 0.6  # Default moderate score

    def _extract_price_range(self, result: str, current_price: str) -> Dict[str, str]:
        """Extract fair price range from crew result"""
        import re

        # Try to find price ranges in the result
        range_pattern = r'([0-9.]+)\s*(?:to|[-–])\s*([0-9.]+)\s*GLUE'
        match = re.search(range_pattern, result)

        if match:
            return {
                "min": match.group(1),
                "max": match.group(2)
            }

        # If no range found, estimate based on current price
        try:
            current = float(current_price)
            return {
                "min": str(round(current * 0.8, 3)),
                "max": str(round(current * 1.2, 3))
            }
        except ValueError:
            return {
                "min": "0.001",
                "max": "0.100"
            }

    def _generate_recommendation(
        self,
        score: float,
        current_price: str,
        fair_range: Dict[str, str]
    ) -> str:
        """Generate pricing recommendation"""
        if score >= 0.8:
            return f"Price of {current_price} GLUE is fair and reasonable"
        elif score >= 0.6:
            return f"Price of {current_price} GLUE is acceptable but could be adjusted to {fair_range['min']}-{fair_range['max']} GLUE range"
        elif score >= 0.4:
            return f"Price of {current_price} GLUE seems high. Fair range: {fair_range['min']}-{fair_range['max']} GLUE"
        else:
            return f"Price of {current_price} GLUE appears significantly overpriced. Consider {fair_range['min']}-{fair_range['max']} GLUE"
