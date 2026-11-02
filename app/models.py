"""Pydantic request/response models for the API and internal pipeline."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRequest(BaseModel):
    customer_request: str = Field(..., min_length=1, description="What the customer originally asked for")
    transcript: str = Field(..., min_length=1, description="Full interaction transcript")
    system_state: str = Field(..., min_length=1, description="Resulting system/account state after the interaction")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_request": "Return damaged chocolate box and get refund",
                "transcript": "Customer: My chocolate box arrived crushed...\nAgent: I'm sorry to hear that...",
                "system_state": "Return authorized, refund $45.99 initiated",
            }
        }
    )


class JudgeResult(BaseModel):
    judge_name: str
    mode: str  # "live" or "demo"
    score: Optional[float] = None
    reasoning: str
    error: Optional[str] = None


class ConsensusResult(BaseModel):
    consensus_score: float
    individual_results: List[JudgeResult]
    score_spread: float
    needs_human_review: bool
    review_threshold: float
