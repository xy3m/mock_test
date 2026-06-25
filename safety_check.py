"""One-off safety checklist runner (PLAN.md §6). Run with the project venv."""

from __future__ import annotations

import json
import re
import sys

from classifier import (
    _SENSITIVE_PATTERN,
    _build_response_from_dict,
    _parse_llm_json,
    _redact_summary,
    _strip_code_fences,
)
from prompts import SYSTEM_PROMPT
from schemas import TicketRequest


def banner(title: str) -> None:
    print("\n=== " + title + " ===")


def report(name: str, passed: bool) -> bool:
    print(("PASS  " if passed else "FAIL  ") + name)
    return passed


def main() -> int:
    results: list[bool] = []

    # 1. .env present in .gitignore
    banner("Static checks")
    gitignore_lines = open(".gitignore", encoding="utf-8").read().splitlines()
    results.append(report(".env is in .gitignore", ".env" in gitignore_lines))

    # 2. No hardcoded API key in any .py file
    hardcoded = False
    for p in ("schemas.py", "prompts.py", "classifier.py", "main.py"):
        txt = open(p, encoding="utf-8").read()
        if re.search(r"AQ\.[A-Za-z0-9_-]{16,}", txt):
            hardcoded = True
            print("  hardcoded in:", p)
    results.append(report("No hardcoded AQ. Gemini key in any .py file", not hardcoded))

    # 3. SYSTEM_PROMPT covers all enums + routing keywords
    banner("Prompt coverage")
    for token in (
        "wrong_transfer",
        "payment_failed",
        "refund_request",
        "phishing_or_social_engineering",
        "other",
        "customer_support",
        "dispute_resolution",
        "payments_ops",
        "fraud_risk",
    ):
        results.append(report("SYSTEM_PROMPT contains " + token, token in SYSTEM_PROMPT))
    results.append(report(
        "SYSTEM_PROMPT ends with the required closing sentence",
        SYSTEM_PROMPT.rstrip().endswith(
            "Return only the raw JSON object. No markdown, no explanation, no code fences."
        ),
    ))

    # 4. Safety redaction
    banner("Safety redaction")
    for bad in [
        "Please share your PIN with me.",
        "Your OTP is 12345",
        "I forgot my password.",
        "Card number 4111 1111 1111 1111",
    ]:
        out = _redact_summary(bad)
        passed = (
            out == "Customer requires assistance. Please review the ticket details."
            and not _SENSITIVE_PATTERN.search(out)
        )
        results.append(report("redacts: " + bad, passed))

    # 5. human_review_required is forced True on critical + phishing
    banner("human_review_required enforcement")
    t = TicketRequest(ticket_id="X", channel="app", locale="en", message="hi")
    r1 = _build_response_from_dict(
        t,
        {
            "case_type": "other",
            "severity": "critical",
            "department": "fraud_risk",
            "agent_summary": "x",
            "confidence": 0.5,
            "human_review_required": False,
        },
    )
    results.append(report("forced True on critical severity", r1.human_review_required is True))

    r2 = _build_response_from_dict(
        t,
        {
            "case_type": "phishing_or_social_engineering",
            "severity": "low",
            "department": "fraud_risk",
            "agent_summary": "x",
            "confidence": 0.5,
            "human_review_required": False,
        },
    )
    results.append(report("forced True on phishing case_type", r2.human_review_required is True))

    # 6. ticket_id echo
    results.append(report("ticket_id echoed into response", r1.ticket_id == "X"))

    # 7. confidence clamping into [0, 1]
    banner("Confidence clamp")
    for v in (-0.5, 0.0, 0.42, 1.0, 1.5):
        t2 = TicketRequest(ticket_id="Y", message="m")
        rr = _build_response_from_dict(
            t2,
            {
                "case_type": "other",
                "severity": "low",
                "department": "customer_support",
                "agent_summary": "x",
                "confidence": v,
                "human_review_required": False,
            },
        )
        results.append(report(f"confidence {v} -> {rr.confidence} in [0,1]", 0.0 <= rr.confidence <= 1.0))

    # 8. Markdown-fence stripping + JSON parsing
    banner("JSON parse")
    raw = (
        "```json\n"
        '{"case_type":"payment_failed","severity":"high","department":"payments_ops",'
        '"agent_summary":"x","confidence":0.9,"human_review_required":false}\n'
        "```"
    )
    cleaned = _strip_code_fences(raw)
    parsed = _parse_llm_json(cleaned)
    results.append(report("stripped fences parse to JSON dict", parsed["case_type"] == "payment_failed"))

    # 9. .env.example present and has placeholders
    env_example = open(".env.example", encoding="utf-8").read()
    results.append(report(".env.example exists with GEMINI_API_KEY", "GEMINI_API_KEY" in env_example))
    results.append(report(".env.example has PORT placeholder", "PORT=8000" in env_example))

    # 10. Dockerfile basics
    banner("Container")
    dockerfile = open("Dockerfile", encoding="utf-8").read()
    results.append(report("Dockerfile uses python:3.11-slim", "python:3.11-slim" in dockerfile))
    results.append(report("Dockerfile exposes 8000", "EXPOSE 8000" in dockerfile))
    results.append(report("Dockerfile does not bake secrets", "GEMINI_API_KEY" not in dockerfile and "AQ." not in dockerfile))

    # 11. .dockerignore excludes .env
    dockerignore = open(".dockerignore", encoding="utf-8").read()
    results.append(report(".dockerignore excludes .env", re.search(r"^\.env$", dockerignore, re.M) is not None))

    # 12. README has the 8 required sections
    banner("README")
    readme = open("README.md", encoding="utf-8").read().lower()
    for sec in (
        "project overview",
        "tech stack",
        "local setup",
        "api reference",
        "deployment on render",
        "environment variables",
        "known limitations",
        "grader test cases",
    ):
        results.append(report("README has section: " + sec, sec in readme))

    # 13. Re-import main and list routes
    import main
    paths = [getattr(r, "path", "") for r in main.app.routes]
    results.append(report("/health route registered", "/health" in paths))
    results.append(report("/sort-ticket route registered", "/sort-ticket" in paths))

    print("\n---")
    print(f"Total checks: {len(results)}  Passed: {sum(results)}  Failed: {len(results) - sum(results)}")
    print("OVERALL:", "PASS" if all(results) else "FAIL")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())