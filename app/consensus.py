"""Consensus orchestration: run all judges concurrently and aggregate their verdicts."""
from __future__ import annotations

import asyncio
import logging
from typing import List

from app.config import settings
from app.judges import ALL_JUDGES
from app.models import ConsensusResult, EvaluationRequest, JudgeResult

logger = logging.getLogger("multi_judge_consensus")


async def _run_judge_safely(judge, request: EvaluationRequest) -> JudgeResult:
    """Wraps a judge call so one failing provider doesn't take down the whole batch."""
    try:
        return await judge(request)
    except Exception as exc:  # noqa: BLE001 - we deliberately want to catch anything here
        judge_name = getattr(judge, "__name__", "unknown_judge")
        logger.exception("Judge %s failed", judge_name)
        return JudgeResult(
            judge_name=judge_name,
            mode="error",
            score=None,
            reasoning="Judge raised an exception and was excluded from consensus.",
            error=str(exc),
        )


async def multi_judge_consensus(request: EvaluationRequest) -> ConsensusResult:
    """Run every configured judge in parallel and aggregate the result."""
    results: List[JudgeResult] = await asyncio.gather(
        *(_run_judge_safely(judge, request) for judge in ALL_JUDGES)
    )

    scored = [r for r in results if r.score is not None]
    if not scored:
        # Every judge failed — surface a clearly-flagged zero-confidence result
        # rather than crashing with a ZeroDivisionError.
        return ConsensusResult(
            consensus_score=0.0,
            individual_results=results,
            score_spread=0.0,
            needs_human_review=True,
            review_threshold=settings.review_threshold,
        )

    scores = [r.score for r in scored]
    avg_score = round(sum(scores) / len(scores), 2)
    spread = round(max(scores) - min(scores), 2)

    return ConsensusResult(
        consensus_score=avg_score,
        individual_results=results,
        score_spread=spread,
        needs_human_review=spread > settings.review_threshold,
        review_threshold=settings.review_threshold,
    )
