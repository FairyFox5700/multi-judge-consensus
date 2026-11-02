"""Judge implementations.

Each judge is an async callable with the signature:

    async def judge(request: EvaluationRequest) -> JudgeResult

Real judges call an LLM provider and parse a strict-JSON verdict out of the response.
Demo judges are fully deterministic (seeded by a hash of the inputs) so the app is
runnable and testable with zero API keys and zero network calls — important for a
portfolio piece that strangers will want to try without setting up credentials.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

from app.config import settings
from app.models import EvaluationRequest, JudgeResult

JUDGE_SYSTEM_PROMPT = """You are a strict QA evaluator for customer-support AI agents.
Given the customer's original request, the full interaction transcript, and the resulting
system state, score how completely the task was satisfied on a 0-10 scale:

- 0-3: request not resolved, or resolved incorrectly
- 4-6: partially resolved, meaningful gaps remain
- 7-8: resolved with minor gaps or rough edges
- 9-10: fully and correctly resolved

Respond with ONLY a JSON object, no markdown fences, no extra text:
{"score": <number 0-10>, "reasoning": "<one or two sentence justification>"}
"""


def _user_prompt(request: EvaluationRequest) -> str:
    return (
        f"CUSTOMER REQUEST:\n{request.customer_request}\n\n"
        f"TRANSCRIPT:\n{request.transcript}\n\n"
        f"RESULTING SYSTEM STATE:\n{request.system_state}"
    )


def _parse_verdict(raw_text: str) -> tuple[float, str]:
    """Best-effort extraction of {score, reasoning} JSON from an LLM response."""
    text = raw_text.strip()
    # Strip markdown code fences if the model added them anyway.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        return float(data["score"]), str(data["reasoning"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    # Fallback: regex-scrape a score and use the raw text as reasoning.
    match = re.search(r"\"?score\"?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    score = float(match.group(1)) if match else 5.0
    return score, text[:500] or "No reasoning returned by model."


async def _call_openai_chat(model_or_deployment: str, request: EvaluationRequest) -> str:
    """Calls OpenAI directly, or Azure OpenAI if an Azure endpoint is configured."""
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(request)},
    ]

    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from openai import AsyncAzureOpenAI

        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    else:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

    completion = await client.chat.completions.create(
        model=model_or_deployment,
        messages=messages,
        temperature=0,
        max_tokens=300,
    )
    return completion.choices[0].message.content or ""


async def _call_anthropic(model: str, request: EvaluationRequest) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model=model,
        max_tokens=300,
        temperature=0,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(request)}],
    )
    return "".join(block.text for block in message.content if block.type == "text")


def _demo_score(judge_name: str, request: EvaluationRequest) -> JudgeResult:
    """Deterministic, explainable mock scoring used when no API key is configured.

    Heuristic: rewards transcripts/system-state text that textually overlaps with the
    customer request, with a small per-judge deterministic offset (derived from a hash)
    so the three demo judges disagree slightly, exactly like real models would.
    """
    combined = f"{request.transcript} {request.system_state}".lower()
    request_words = {w for w in re.findall(r"[a-z]{4,}", request.customer_request.lower())}
    if not request_words:
        overlap_ratio = 0.5
    else:
        hits = sum(1 for w in request_words if w in combined)
        overlap_ratio = hits / len(request_words)

    base_score = 3 + overlap_ratio * 6  # maps 0..1 overlap to 3..9

    # Small deterministic per-judge jitter so judges disagree a little, seeded on
    # (judge_name + inputs) so the same inputs always reproduce the same result.
    digest = hashlib.sha256(f"{judge_name}:{combined}:{request.customer_request}".encode()).hexdigest()
    jitter = (int(digest[:4], 16) % 21 - 10) / 10.0  # -1.0 .. +1.0
    score = max(0.0, min(10.0, round(base_score + jitter, 1)))

    if score >= 8.5:
        reasoning = "Transcript and system state strongly match the customer's request; resolution looks complete."
    elif score >= 6:
        reasoning = "Core request appears addressed, but some details in the transcript aren't fully confirmed."
    else:
        reasoning = "Transcript/system state show limited overlap with the customer's request; resolution unclear."

    return JudgeResult(judge_name=judge_name, mode="demo", score=score, reasoning=reasoning)


async def task_completion_judge_gpt4o(request: EvaluationRequest) -> JudgeResult:
    name = "gpt-4o"
    if not settings.has_openai or settings.force_demo_mode:
        return _demo_score(name, request)
    raw = await _call_openai_chat(settings.gpt4o_deployment, request)
    score, reasoning = _parse_verdict(raw)
    return JudgeResult(judge_name=name, mode="live", score=score, reasoning=reasoning)


async def task_completion_judge_gpt4o_mini(request: EvaluationRequest) -> JudgeResult:
    name = "gpt-4o-mini"
    if not settings.has_openai or settings.force_demo_mode:
        return _demo_score(name, request)
    raw = await _call_openai_chat(settings.gpt4o_mini_deployment, request)
    score, reasoning = _parse_verdict(raw)
    return JudgeResult(judge_name=name, mode="live", score=score, reasoning=reasoning)


async def task_completion_judge_claude(request: EvaluationRequest) -> JudgeResult:
    name = "claude"
    if not settings.has_anthropic or settings.force_demo_mode:
        return _demo_score(name, request)
    raw = await _call_anthropic(settings.claude_model, request)
    score, reasoning = _parse_verdict(raw)
    return JudgeResult(judge_name=name, mode="live", score=score, reasoning=reasoning)


ALL_JUDGES = [
    task_completion_judge_gpt4o,
    task_completion_judge_gpt4o_mini,
    task_completion_judge_claude,
]
