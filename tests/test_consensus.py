import asyncio

import pytest

from app.config import settings
from app.consensus import multi_judge_consensus
from app.models import EvaluationRequest, JudgeResult


def make_request(**overrides) -> EvaluationRequest:
    base = dict(
        customer_request="Return damaged chocolate box and get refund",
        transcript=(
            "Customer: My chocolate box arrived crushed and melted.\n"
            "Agent: I'm sorry — I've authorized a return and a full refund of $45.99."
        ),
        system_state="Return authorized, refund $45.99 initiated",
    )
    base.update(overrides)
    return EvaluationRequest(**base)


@pytest.mark.asyncio
async def test_demo_mode_runs_without_api_keys():
    """With no API keys configured, consensus must still run end-to-end using demo judges."""
    assert not settings.has_openai
    assert not settings.has_anthropic

    result = await multi_judge_consensus(make_request())

    assert len(result.individual_results) == 3
    assert all(r.mode == "demo" for r in result.individual_results)
    assert all(0 <= r.score <= 10 for r in result.individual_results)
    assert 0 <= result.consensus_score <= 10
    assert result.score_spread >= 0


@pytest.mark.asyncio
async def test_demo_scoring_is_deterministic():
    """Same inputs must always produce the same demo scores (reproducible evaluation)."""
    r1 = await multi_judge_consensus(make_request())
    r2 = await multi_judge_consensus(make_request())

    scores1 = [j.score for j in r1.individual_results]
    scores2 = [j.score for j in r2.individual_results]
    assert scores1 == scores2


@pytest.mark.asyncio
async def test_unrelated_transcript_scores_lower():
    """A transcript with no overlap to the request should score meaningfully lower
    than a transcript that clearly resolves it."""
    relevant = make_request()
    irrelevant = make_request(
        transcript="Customer: What's the weather like today?\nAgent: It's sunny.",
        system_state="No action taken",
    )

    relevant_result = await multi_judge_consensus(relevant)
    irrelevant_result = await multi_judge_consensus(irrelevant)

    assert relevant_result.consensus_score > irrelevant_result.consensus_score


@pytest.mark.asyncio
async def test_needs_human_review_flag_follows_threshold(monkeypatch):
    """needs_human_review must flip True exactly when spread exceeds the configured threshold."""
    from app import consensus as consensus_module

    async def fake_judge_low(request):
        return JudgeResult(judge_name="low", mode="demo", score=2.0, reasoning="low")

    async def fake_judge_high(request):
        return JudgeResult(judge_name="high", mode="demo", score=9.0, reasoning="high")

    monkeypatch.setattr(consensus_module, "ALL_JUDGES", [fake_judge_low, fake_judge_high])

    result = await multi_judge_consensus(make_request())

    assert result.score_spread == 7.0
    assert result.needs_human_review is True


@pytest.mark.asyncio
async def test_all_judges_failing_is_handled_gracefully(monkeypatch):
    """If every judge raises, the pipeline must not crash and must flag for review."""
    from app import consensus as consensus_module

    async def broken_judge(request):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(consensus_module, "ALL_JUDGES", [broken_judge, broken_judge])

    result = await multi_judge_consensus(make_request())

    assert result.consensus_score == 0.0
    assert result.needs_human_review is True
    assert all(r.error is not None for r in result.individual_results)
