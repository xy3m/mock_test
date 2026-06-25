"""FastAPI entry point for the QueueStorm ticket classifier.

Endpoints:
    GET  /health        - liveness probe.
    POST /sort-ticket   - classify a single CRM ticket.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from classifier import classify_ticket
from schemas import TicketRequest, TicketResponse

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="QueueStorm Ticket Classifier", version="1.0.0")


@app.on_event("startup")
async def _startup_log() -> None:
    logger.info("QueueStorm classifier (Gemini backend) is ready.")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Returns a static dict; trivially under the 10s budget."""
    return {
        "status": "ok",
        "service": "queueStorm-classifier",
        "version": "1.0.0",
    }


@app.post("/sort-ticket", response_model=TicketResponse)
async def sort_ticket(ticket: TicketRequest) -> TicketResponse | JSONResponse:
    """Classify an inbound ticket.

    Always returns a `TicketResponse` shape; the classifier itself never
    raises. The try/except here is a last-resort guard for any unexpected
    error that escapes the classifier.
    """
    try:
        result = await classify_ticket(ticket)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in /sort-ticket: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "Unexpected error while classifying the ticket.",
            },
        )


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)