"""LLM-backed ticket classifier.

Wraps the Google Gemini API call, parses the JSON response, and applies
two safety guarantees on top of whatever the model returns:

1. The `agent_summary` is scanned for the tokens `pin`, `otp`, `password`, and
   `card number` (case-insensitive). If any are present, the field is replaced
   with a neutral fallback sentence so we never echo sensitive prompts back to
   the customer or the agent.
2. `human_review_required` is forced to `True` whenever `severity == "critical"`
   or `case_type == "phishing_or_social_engineering"`, regardless of what the
   model returned.

On any failure (missing key, network error, malformed JSON, schema violation)
the function returns a safe fallback `TicketResponse` so the API endpoint
never crashes the caller.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT
from schemas import TicketRequest, TicketResponse

# Load .env if present (no-op in production where the platform injects env vars).
load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google Gemini client
# ---------------------------------------------------------------------------

try:
    from google import genai  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - the dep is in requirements.txt
    genai = None  # type: ignore[assignment]

# Gemini 2.5 Flash is fast, cheap, and strong on structured JSON output.
MODEL_NAME: str = "gemini-2.5-flash"
MAX_TOKENS: int = 512

# Tokens that must never appear in the agent_summary field.
_SENSITIVE_TOKENS = ("pin", "otp", "password", "card number")
# Use word boundaries for short tokens so e.g. "pinned" or "stopping" do not
# match. "card number" is a multi-word phrase; we do a plain substring check
# for it and word-boundary checks for the single-word tokens.
_SENSITIVE_PATTERN = re.compile(
    r"\b(pin|otp|password)\b|card\s*number",
    re.IGNORECASE,
)

_FALLBACK_AGENT_SUMMARY = "Customer requires assistance. Please review the ticket details."
_FALLBACK_AGENT_SUMMARY_ON_ERROR = (
    "Classification failed. Please review manually."
)


async def _call_with_retry(call_once, attempts: int = 3, base_delay: float = 1.5):
    """Invoke the LLM call up to `attempts` times with exponential backoff.

    Re-raises the last exception if all attempts fail. Used to ride out
    transient upstream 503s.
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await call_once()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            # Don't sleep after the final attempt.
            if i < attempts - 1:
                await asyncio.sleep(base_delay * (2 ** i))
    assert last_exc is not None  # for type-checkers
    raise last_exc


def _get_client():
    """Build a Gemini client using GEMINI_API_KEY from the environment.

    Returns None if the SDK isn't installed or the key is missing, so callers
    can fall back gracefully.
    """
    if genai is None:  # pragma: no cover
        logger.error("google-genai SDK not installed")
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_key_here":
        logger.error("GEMINI_API_KEY is missing or unset")
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to construct Gemini client: %s", exc)
        return None


def _strip_code_fences(text: str) -> str:
    """Remove ``` or ```json fences that some models still occasionally emit."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop the opening fence (and optional language tag).
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _build_user_message(ticket: TicketRequest) -> str:
    return (
        f"ticket_id: {ticket.ticket_id}\n"
        f"channel: {ticket.channel}\n"
        f"locale: {ticket.locale}\n"
        f"message: {ticket.message}"
    )


def _redact_summary(summary: str) -> str:
    """Replace any agent_summary that mentions sensitive tokens with a neutral line."""
    if not summary:
        return _FALLBACK_AGENT_SUMMARY
    if _SENSITIVE_PATTERN.search(summary):
        return _FALLBACK_AGENT_SUMMARY
    return summary


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y")
    return bool(value)


def _coerce_confidence(value: Any) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.0
    # Clamp into [0.0, 1.0] as a safety net.
    if c < 0.0:
        return 0.0
    if c > 1.0:
        return 1.0
    return c


def _parse_llm_json(raw_text: str) -> dict[str, Any]:
    """Parse the model's reply as JSON, tolerating accidental code fences."""
    cleaned = _strip_code_fences(raw_text)
    return json.loads(cleaned)


def _build_response_from_dict(ticket: TicketRequest, data: dict[str, Any]) -> TicketResponse:
    """Build a TicketResponse from a parsed JSON dict, applying safety rules."""
    case_type = str(data.get("case_type", "other"))
    severity = str(data.get("severity", "low"))
    department = str(data.get("department", "customer_support"))
    agent_summary = _redact_summary(str(data.get("agent_summary", "")))
    confidence = _coerce_confidence(data.get("confidence", 0.0))
    human_review_required = _coerce_bool(data.get("human_review_required", False))

    # Force human review on critical or phishing cases regardless of model output.
    if severity == "critical" or case_type == "phishing_or_social_engineering":
        human_review_required = True

    return TicketResponse(
        ticket_id=ticket.ticket_id,
        case_type=case_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        department=department,  # type: ignore[arg-type]
        agent_summary=agent_summary,
        human_review_required=human_review_required,
        confidence=confidence,
    )


def _fallback_response(ticket: TicketRequest) -> TicketResponse:
    """The safe-default response used whenever the LLM path fails."""
    return TicketResponse(
        ticket_id=ticket.ticket_id,
        case_type="other",
        severity="low",
        department="customer_support",
        agent_summary=_FALLBACK_AGENT_SUMMARY_ON_ERROR,
        human_review_required=False,
        confidence=0.0,
    )


async def classify_ticket(ticket: TicketRequest) -> TicketResponse:
    """Classify a single ticket using Google Gemini.

    Never raises; on any failure returns a fallback `TicketResponse`.
    """
    try:
        client = _get_client()
        if client is None:
            return _fallback_response(ticket)

        # Gemini takes the system prompt as a separate `config.system_instruction`
        # and the user turn as `contents`. Wrap in a small retry loop because
        # `gemini-2.5-flash` returns occasional 503s under load.
        async def _call_once() -> str:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=_build_user_message(ticket),
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "max_output_tokens": MAX_TOKENS,
                    "response_mime_type": "application/json",
                },
            )
            return getattr(response, "text", "") or ""

        try:
            raw_text = await _call_with_retry(_call_once)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Gemini call failed for ticket %s after retries: %s",
                ticket.ticket_id,
                exc,
            )
            return _fallback_response(ticket)

        if not raw_text:
            logger.warning("Gemini returned no text content for ticket %s", ticket.ticket_id)
            return _fallback_response(ticket)

        try:
            data = _parse_llm_json(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to parse LLM JSON for ticket %s: %s | raw=%r",
                ticket.ticket_id,
                exc,
                raw_text[:300],
            )
            return _fallback_response(ticket)

        try:
            return _build_response_from_dict(ticket, data)
        except Exception as exc:  # Pydantic ValidationError, etc.
            logger.warning(
                "LLM output failed validation for ticket %s: %s | data=%r",
                ticket.ticket_id,
                exc,
                data,
            )
            return _fallback_response(ticket)

    except Exception as exc:  # noqa: BLE001 - last-resort safety net
        logger.exception("Unexpected error classifying ticket %s: %s", ticket.ticket_id, exc)
        return _fallback_response(ticket)