"""Pydantic v2 request/response models for the QueueStorm ticket classifier.

This module is intentionally logic-free. It only defines the shape of the
inbound `TicketRequest` and the outbound `TicketResponse` exchanged with the
`POST /sort-ticket` endpoint.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# Inbound customer support ticket.
Channel = Literal["app", "sms", "call_center", "merchant_portal"]
Locale = Literal["bn", "en", "mixed"]


class TicketRequest(BaseModel):
    """Inbound payload sent by the CRM to `POST /sort-ticket`.

    Attributes:
        ticket_id: Stable identifier the CRM uses to track this ticket. Echoed
            back unchanged in the response.
        channel: Originating channel. Optional; one of `app`, `sms`,
            `call_center`, or `merchant_portal`.
        locale: Language locale of the customer message. Optional; one of
            `bn` (Bangla), `en` (English), or `mixed`.
        message: Raw customer message body. Required.
    """

    ticket_id: str = Field(..., description="Unique ticket identifier (CRM-side).")
    channel: Optional[Channel] = Field(
        default=None,
        description="Originating channel: app, sms, call_center, merchant_portal.",
    )
    locale: Optional[Locale] = Field(
        default=None,
        description="Message locale: bn, en, mixed.",
    )
    message: str = Field(..., description="Raw customer message body.")


# Outbound classification result.
CaseType = Literal[
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "phishing_or_social_engineering",
    "other",
]
Severity = Literal["low", "medium", "high", "critical"]
Department = Literal[
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "fraud_risk",
]


class TicketResponse(BaseModel):
    """Outbound payload returned by `POST /sort-ticket`.

    Attributes:
        ticket_id: Echo of the inbound `TicketRequest.ticket_id`.
        case_type: Normalized case type assigned by the classifier.
        severity: Operational severity of the ticket.
        department: Team the ticket should be routed to.
        agent_summary: 1-2 sentence neutral summary for the receiving agent.
            Must NOT mention PIN, OTP, password, or full card number.
        human_review_required: True when severity is `critical` or case_type is
            `phishing_or_social_engineering`.
        confidence: Classifier confidence in [0.0, 1.0].
    """

    ticket_id: str = Field(..., description="Echo of the inbound ticket_id.")
    case_type: CaseType = Field(..., description="Normalized case type.")
    severity: Severity = Field(..., description="Operational severity.")
    department: Department = Field(..., description="Routing department.")
    agent_summary: str = Field(..., description="Neutral agent-facing summary.")
    human_review_required: bool = Field(
        ...,
        description="Forced True for critical or phishing cases.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Classifier confidence in [0.0, 1.0].",
    )