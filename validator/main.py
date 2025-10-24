"""
Validator Agent - Independent data quality verification service

This agent provides trustless validation for data transactions:
- Receives validation requests from sellers
- Uses CrewAI crews to analyze data quality
- Submits validation scores on-chain (pays gas)
- Returns validation results to requestor

Pricing: 0.001 GLUE per validation
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for shared imports
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from dotenv import load_dotenv
from shared.base_agent import ERC8004BaseAgent
from shared.a2a_protocol import AgentCard, Skill, Price
from crews.quality_crew import QualityValidationCrew
from crews.fraud_crew import FraudDetectionCrew
from crews.price_crew import PriceReviewCrew

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    "agent_name": os.getenv("AGENT_NAME", "validator"),
    "agent_domain": os.getenv("AGENT_DOMAIN", "validator.ultravioletadao.xyz"),
    "private_key": os.getenv("PRIVATE_KEY") or None,
    "rpc_url": os.getenv("RPC_URL_FUJI"),
    "chain_id": int(os.getenv("CHAIN_ID", "43113")),
    "identity_registry": os.getenv("IDENTITY_REGISTRY"),
    "reputation_registry": os.getenv("REPUTATION_REGISTRY"),
    "validation_registry": os.getenv("VALIDATION_REGISTRY"),
    "glue_token": os.getenv("GLUE_TOKEN_ADDRESS"),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o"),
    "validation_fee": os.getenv("VALIDATION_FEE_GLUE", "0.001"),
    "host": os.getenv("HOST", "0.0.0.0"),
    "port": int(os.getenv("PORT", "8001"))
}


# Request/Response Models
class ValidationRequest(BaseModel):
    """Request model for validation service"""
    data_type: str = Field(..., description="Type of data to validate (chat_logs, transcription, etc)")
    data_content: Dict[str, Any] = Field(..., description="Data to validate")
    seller_address: str = Field(..., description="Address of the seller")
    buyer_address: str = Field(..., description="Address of the buyer")
    price_glue: str = Field(..., description="Price in GLUE for the data")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class ValidationResponse(BaseModel):
    """Response model for validation service"""
    validation_id: str
    quality_score: float  # 0.0 - 1.0
    fraud_score: float    # 0.0 - 1.0 (higher = more likely fraud)
    price_score: float    # 0.0 - 1.0 (how fair is the price)
    overall_score: float  # 0.0 - 1.0 (weighted average)
    recommendation: str   # "approve", "reject", "review"
    reasoning: str
    timestamp: str
    tx_hash: Optional[str] = None  # On-chain validation submission


class ValidatorAgent(ERC8004BaseAgent):
    """Validator Agent for independent data quality verification"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize validator agent"""
        super().__init__(
            agent_name=config["agent_name"],
            private_key=config["private_key"],
            rpc_url=config["rpc_url"],
            chain_id=config["chain_id"],
            identity_registry_address=config["identity_registry"],
            reputation_registry_address=config["reputation_registry"],
            validation_registry_address=config["validation_registry"],
            glue_token_address=config["glue_token"]
        )

        self.config = config
        self.validation_fee = config["validation_fee"]

        # Initialize CrewAI crews
        self.quality_crew = QualityValidationCrew(model=config["openai_model"])
        self.fraud_crew = FraudDetectionCrew(model=config["openai_model"])
        self.price_crew = PriceReviewCrew(model=config["openai_model"])

        logger.info(f"Validator agent initialized: {self.address}")

    def register_on_chain(self) -> int:
        """Register validator agent on-chain"""
        try:
            agent_id = self.register_agent(domain=self.config["agent_domain"])
            logger.info(f"Validator registered on-chain with ID: {agent_id}")
            return agent_id
        except Exception as e:
            logger.error(f"Failed to register validator: {e}")
            raise

    def get_agent_card(self) -> AgentCard:
        """Generate A2A AgentCard for validator"""
        return AgentCard(
            agentId=f"validator-{self.address}",
            name="Validator Agent",
            description="Independent data quality verification service using CrewAI multi-agent validation",
            url=f"https://{self.config['agent_domain']}",
            skills=[
                Skill(
                    name="validate_data",
                    description="Validate data quality, detect fraud, review pricing",
                    pricing=Price(
                        amount=self.validation_fee,
                        currency="GLUE"
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "data_type": {"type": "string"},
                            "data_content": {"type": "object"},
                            "seller_address": {"type": "string"},
                            "buyer_address": {"type": "string"},
                            "price_glue": {"type": "string"}
                        },
                        "required": ["data_type", "data_content", "seller_address", "buyer_address", "price_glue"]
                    },
                    outputSchema={
                        "type": "object",
                        "properties": {
                            "quality_score": {"type": "number"},
                            "fraud_score": {"type": "number"},
                            "price_score": {"type": "number"},
                            "overall_score": {"type": "number"},
                            "recommendation": {"type": "string"}
                        }
                    }
                )
            ]
        )

    async def validate_data(self, request: ValidationRequest) -> ValidationResponse:
        """
        Validate data using CrewAI crews

        Returns validation scores and recommendation
        """
        validation_id = f"val_{int(datetime.utcnow().timestamp())}_{request.seller_address[:8]}"

        logger.info(f"Starting validation {validation_id} for {request.data_type}")

        try:
            # Run validation crews in parallel
            quality_task = asyncio.create_task(
                self._run_quality_validation(request)
            )
            fraud_task = asyncio.create_task(
                self._run_fraud_detection(request)
            )
            price_task = asyncio.create_task(
                self._run_price_review(request)
            )

            # Wait for all validations to complete
            quality_result, fraud_result, price_result = await asyncio.gather(
                quality_task, fraud_task, price_task
            )

            # Calculate overall score (weighted average)
            overall_score = (
                quality_result["score"] * 0.5 +  # Quality is most important
                (1 - fraud_result["score"]) * 0.3 +  # Lower fraud score is better
                price_result["score"] * 0.2  # Price fairness
            )

            # Determine recommendation
            if overall_score >= 0.8 and fraud_result["score"] < 0.2:
                recommendation = "approve"
            elif overall_score < 0.5 or fraud_result["score"] > 0.7:
                recommendation = "reject"
            else:
                recommendation = "review"

            # Generate reasoning
            reasoning = self._generate_reasoning(
                quality_result, fraud_result, price_result, overall_score
            )

            # Submit validation score on-chain
            tx_hash = await self._submit_validation_onchain(
                validation_id=validation_id,
                seller_address=request.seller_address,
                buyer_address=request.buyer_address,
                score=int(overall_score * 100)  # Convert to 0-100 scale
            )

            response = ValidationResponse(
                validation_id=validation_id,
                quality_score=quality_result["score"],
                fraud_score=fraud_result["score"],
                price_score=price_result["score"],
                overall_score=overall_score,
                recommendation=recommendation,
                reasoning=reasoning,
                timestamp=datetime.utcnow().isoformat(),
                tx_hash=tx_hash
            )

            logger.info(f"Validation {validation_id} complete: {recommendation} (score: {overall_score:.2f})")

            return response

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

    async def _run_quality_validation(self, request: ValidationRequest) -> Dict[str, Any]:
        """Run quality validation crew"""
        return await asyncio.to_thread(
            self.quality_crew.validate,
            data_type=request.data_type,
            data_content=request.data_content,
            metadata=request.metadata
        )

    async def _run_fraud_detection(self, request: ValidationRequest) -> Dict[str, Any]:
        """Run fraud detection crew"""
        return await asyncio.to_thread(
            self.fraud_crew.detect,
            data_type=request.data_type,
            data_content=request.data_content,
            seller_address=request.seller_address,
            metadata=request.metadata
        )

    async def _run_price_review(self, request: ValidationRequest) -> Dict[str, Any]:
        """Run price review crew"""
        return await asyncio.to_thread(
            self.price_crew.review,
            data_type=request.data_type,
            data_size=len(str(request.data_content)),
            price_glue=request.price_glue,
            metadata=request.metadata
        )

    def _generate_reasoning(
        self,
        quality_result: Dict,
        fraud_result: Dict,
        price_result: Dict,
        overall_score: float
    ) -> str:
        """Generate human-readable reasoning for validation decision"""
        reasoning_parts = []

        reasoning_parts.append(f"Quality: {quality_result['reasoning']}")
        reasoning_parts.append(f"Fraud Check: {fraud_result['reasoning']}")
        reasoning_parts.append(f"Price Review: {price_result['reasoning']}")
        reasoning_parts.append(f"Overall Score: {overall_score:.2f}/1.0")

        return " | ".join(reasoning_parts)

    async def _submit_validation_onchain(
        self,
        validation_id: str,
        seller_address: str,
        buyer_address: str,
        score: int
    ) -> Optional[str]:
        """
        Submit validation score to ValidationRegistry on-chain

        This is where the validator PAYS GAS to write the validation result
        """
        try:
            # Call validationResponse on ValidationRegistry
            # This requires the validator to have AVAX for gas
            tx_hash = self.submit_validation_response(
                seller_address=seller_address,
                buyer_address=buyer_address,
                score=score,
                metadata=validation_id
            )

            logger.info(f"Validation submitted on-chain: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Failed to submit validation on-chain: {e}")
            # Don't fail the entire validation if on-chain submission fails
            return None


# FastAPI Application
app = FastAPI(
    title="Validator Agent",
    description="Independent data quality verification service",
    version="1.0.0"
)

# Global validator instance
validator: Optional[ValidatorAgent] = None


@app.on_event("startup")
async def startup():
    """Initialize validator on startup"""
    global validator

    logger.info("Starting Validator Agent...")

    try:
        # Initialize validator
        validator = ValidatorAgent(CONFIG)

        # Register on-chain if not already registered
        try:
            agent_id = validator.register_on_chain()
            logger.info(f"Validator registered with ID: {agent_id}")
        except Exception as e:
            logger.warning(f"Registration failed (may already be registered): {e}")

        logger.info(f"Validator ready at {CONFIG['host']}:{CONFIG['port']}")

    except Exception as e:
        logger.error(f"Failed to initialize validator: {e}")
        raise


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Validator Agent",
        "status": "running",
        "address": validator.address if validator else None,
        "fee": CONFIG["validation_fee"] + " GLUE"
    }


@app.get("/.well-known/agent-card")
async def agent_card():
    """Return A2A AgentCard"""
    if not validator:
        raise HTTPException(status_code=503, detail="Validator not initialized")

    return validator.get_agent_card().model_dump()


@app.post("/validate", response_model=ValidationResponse)
async def validate(request: ValidationRequest):
    """
    Validate data quality

    This endpoint receives validation requests from sellers and returns
    quality scores, fraud detection, and price review results.
    """
    if not validator:
        raise HTTPException(status_code=503, detail="Validator not initialized")

    logger.info(f"Validation request from seller: {request.seller_address}")

    return await validator.validate_data(request)


@app.get("/health")
async def health():
    """Health check with more details"""
    if not validator:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "Validator not initialized"}
        )

    return {
        "status": "healthy",
        "validator_address": validator.address,
        "chain_id": CONFIG["chain_id"],
        "validation_fee": CONFIG["validation_fee"] + " GLUE"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=CONFIG["host"],
        port=CONFIG["port"],
        reload=True,
        log_level="info"
    )
