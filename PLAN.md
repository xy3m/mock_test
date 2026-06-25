# QueueStorm Warmup: AI-Readable Project Plan
## bKash × SUST CSE Carnival 2026 — Codex Hackathon Mock Preliminary

> **Purpose of this document:** A machine-readable, prompt-driven build plan for an AI coding assistant (Claude, Cursor, Copilot, etc.). Each section contains context, constraints, and a ready-to-paste prompt. Follow sections in order.

---

## 0. Project Overview

| Field | Value |
|---|---|
| Task | Build a ticket classification microservice for a digital finance CRM |
| Time limit | 1 hour (warmup / practice round) |
| Stack recommendation | Python + FastAPI (or Node.js + Express) |
| LLM allowed | Yes — use Anthropic Claude API (`claude-sonnet-4-6`) |
| GPU | Not allowed |
| Deployment target | Render / Railway / Fly.io / Vercel |
| Secrets management | Environment variables only — never hardcode API keys |

---

## 1. What the Service Must Do

Read one customer support message and return:

| Output field | Possible values |
|---|---|
| `case_type` | `wrong_transfer`, `payment_failed`, `refund_request`, `phishing_or_social_engineering`, `other` |
| `severity` | `low`, `medium`, `high`, `critical` |
| `department` | `customer_support`, `dispute_resolution`, `payments_ops`, `fraud_risk` |
| `agent_summary` | 1–2 neutral sentences. **Must NOT mention PIN, OTP, password, or card number.** |
| `human_review_required` | `true` if severity is `critical` OR `case_type` is `phishing_or_social_engineering` |
| `confidence` | Float 0.0–1.0 |

---

## 2. File Structure to Generate

```
queueStorm-warmup/
├── main.py                  # FastAPI app entry point
├── classifier.py            # LLM classification logic
├── schemas.py               # Pydantic request/response models
├── prompts.py               # System prompt and few-shot examples
├── requirements.txt         # Python dependencies
├── .env.example             # Template for env variables (no real secrets)
├── Dockerfile               # Optional, for container deployments
├── README.md                # Deployment runbook
└── .gitignore               # Ignore .env and __pycache__
```

---

## 3. Dependency List (`requirements.txt`)

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.0.0
anthropic>=0.28.0
python-dotenv>=1.0.0
httpx>=0.27.0
```

---

## 4. Environment Variables

```
# .env.example
ANTHROPIC_API_KEY=your_key_here
PORT=8000
```

---

## 5. Build Prompts (paste these into your AI assistant one at a time)

---

### PROMPT 1 — Pydantic Schemas (`schemas.py`)

```
You are a Python backend developer. Generate a file called schemas.py using Pydantic v2.

It must define two models:

1. TicketRequest
   Fields:
   - ticket_id: str (required)
   - channel: Optional[str] — one of: app, sms, call_center, merchant_portal
   - locale: Optional[str] — one of: bn, en, mixed
   - message: str (required)

2. TicketResponse
   Fields:
   - ticket_id: str
   - case_type: str — one of: wrong_transfer, payment_failed, refund_request, phishing_or_social_engineering, other
   - severity: str — one of: low, medium, high, critical
   - department: str — one of: customer_support, dispute_resolution, payments_ops, fraud_risk
   - agent_summary: str
   - human_review_required: bool
   - confidence: float (between 0.0 and 1.0, inclusive)

Use Literal types for the enum fields. Add docstrings to each class. No logic, just models.
```

---

### PROMPT 2 — System Prompt and Few-Shot Examples (`prompts.py`)

```
You are a Python developer. Create a file called prompts.py.

It must contain one string constant called SYSTEM_PROMPT. 

The prompt is for an LLM that classifies customer support tickets for a Bangladeshi mobile financial service (like bKash). The LLM must:

1. Read the customer message.
2. Return ONLY a valid JSON object with exactly these fields:
   - case_type: one of [wrong_transfer, payment_failed, refund_request, phishing_or_social_engineering, other]
   - severity: one of [low, medium, high, critical]
   - department: one of [customer_support, dispute_resolution, payments_ops, fraud_risk]
   - agent_summary: one or two neutral sentences summarizing the ticket for an agent. CRITICAL SAFETY RULE: this field must NEVER mention or ask the customer to share their PIN, OTP, password, or full card number.
   - human_review_required: boolean, true if severity is critical OR case_type is phishing_or_social_engineering
   - confidence: float between 0.0 and 1.0

3. Use these routing rules:
   - wrong_transfer → dispute_resolution, severity high
   - payment_failed → payments_ops, severity high
   - phishing_or_social_engineering → fraud_risk, severity critical, human_review_required true
   - refund_request (simple, customer changed mind) → customer_support, severity low
   - refund_request (contested, disputed) → dispute_resolution, severity medium/high
   - other → customer_support, severity low

4. Include 5 few-shot examples in the system prompt covering each case_type. Use realistic Bangladeshi MFS customer messages.

5. The prompt must end with: "Return only the raw JSON object. No markdown, no explanation, no code fences."
```

---

### PROMPT 3 — Classifier Logic (`classifier.py`)

```
You are a Python backend developer. Create a file called classifier.py.

It calls the Anthropic API using the official `anthropic` Python SDK (not httpx directly).

Requirements:
- Import SYSTEM_PROMPT from prompts.py
- Import TicketRequest, TicketResponse from schemas.py
- Load ANTHROPIC_API_KEY from environment variables using python-dotenv
- Create an async function: async def classify_ticket(ticket: TicketRequest) -> TicketResponse
- Build the user message as: f"ticket_id: {ticket.ticket_id}\nchannel: {ticket.channel}\nlocale: {ticket.locale}\nmessage: {ticket.message}"
- Call claude-sonnet-4-6 with max_tokens=512, the system prompt, and the user message
- Parse the response text as JSON (strip any accidental markdown fences before parsing)
- Enforce the safety rule: if the agent_summary contains the words pin, otp, password, or card number (case-insensitive), replace it with: "Customer requires assistance. Please review the ticket details."
- Enforce human_review_required: force it to True if severity == "critical" or case_type == "phishing_or_social_engineering"
- Echo ticket_id from the request into the response
- Wrap the entire call in try/except; on failure return a fallback TicketResponse with case_type="other", severity="low", department="customer_support", confidence=0.0, human_review_required=False, agent_summary="Classification failed. Please review manually."
```

---

### PROMPT 4 — FastAPI App (`main.py`)

```
You are a Python backend developer. Create main.py for a FastAPI application.

Requirements:
- Import FastAPI, and the classify_ticket function from classifier.py
- Import TicketRequest, TicketResponse from schemas.py
- Create a FastAPI app with title "QueueStorm Ticket Classifier" and version "1.0.0"

Endpoints:
1. GET /health
   - Returns: {"status": "ok", "service": "queueStorm-classifier", "version": "1.0.0"}
   - Must respond within 10 seconds (it's just a dict return, this is trivially met)

2. POST /sort-ticket
   - Accepts: TicketRequest JSON body
   - Calls: await classify_ticket(ticket)
   - Returns: TicketResponse
   - Response time target: within 30 seconds (LLM call is the bottleneck)
   - Add a try/except that returns HTTP 500 with a JSON error body if something unexpected occurs

- Run with: uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
- Add a startup event log: print("QueueStorm classifier is ready.")
- No authentication required for this mock round.
```

---

### PROMPT 5 — README / Deployment Runbook (`README.md`)

```
You are a technical writer. Write a README.md for a hackathon project called "QueueStorm Warmup Classifier".

It must contain the following sections:

1. Project Overview — one paragraph describing what this service does (classify bKash CRM tickets using AI)

2. Tech Stack — list: Python 3.11+, FastAPI, Anthropic Claude (claude-sonnet-4-6), Pydantic v2, Uvicorn

3. Local Setup
   - git clone instructions
   - python -m venv venv && source venv/bin/activate (and Windows equivalent)
   - pip install -r requirements.txt
   - cp .env.example .env → fill in ANTHROPIC_API_KEY
   - uvicorn main:app --reload

4. API Reference
   - GET /health — example curl and response
   - POST /sort-ticket — example curl with the sample message "I sent 5000 taka to a wrong number this morning" and the expected JSON response shape

5. Deployment on Render (free tier)
   - Create a new Web Service
   - Connect the GitHub repo
   - Set environment variable: ANTHROPIC_API_KEY
   - Build command: pip install -r requirements.txt
   - Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
   - Note that the free tier may spin down after inactivity; hit /health to wake it

6. Environment Variables table: ANTHROPIC_API_KEY (required), PORT (optional, default 8000)

7. Known Limitations — LLM cold start may push /sort-ticket close to the 30s limit on free Render tier; /health is always fast.

8. Grader Test Cases — include the 5 sample cases from the problem statement in a markdown table.
```

---

### PROMPT 6 — Dockerfile (optional but recommended)

```
Write a minimal Dockerfile for a Python FastAPI app.

Requirements:
- Base image: python:3.11-slim
- WORKDIR /app
- Copy requirements.txt first, then run pip install --no-cache-dir -r requirements.txt
- Copy the rest of the source code
- Expose port 8000
- CMD: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
- Do not bake in any secrets or API keys
```

---

## 6. Safety Checklist (run before submission)

```
PROMPT — Final Safety and Submission Check

You are a code reviewer for a hackathon submission. Review the following project for these issues:

1. [ ] Does .env appear in .gitignore? (it must)
2. [ ] Is ANTHROPIC_API_KEY ever hardcoded in any .py file? (it must not be)
3. [ ] Does any agent_summary in the classifier ever contain the words: pin, otp, password, card number? (it must not)
4. [ ] Is human_review_required forced True for phishing_or_social_engineering and critical severity? (it must be)
5. [ ] Does GET /health return within 10 seconds? (it must — it should be a static dict)
6. [ ] Does POST /sort-ticket return within 30 seconds? (it should — LLM call is the bottleneck)
7. [ ] Does ticket_id in the response match ticket_id in the request? (it must)
8. [ ] Is confidence always a float between 0.0 and 1.0? (it must be)
9. [ ] Is the live URL HTTPS? (required for submission)
10. [ ] Does the GitHub repo have a README with deployment instructions? (required)

Report any issues found and suggest fixes.
```

---

## 7. Quick Manual Test Script

After deploying, run these curl commands to verify all 5 grader cases:

```bash
# Case 1 — wrong_transfer
curl -X POST https://YOUR_URL/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-001","channel":"app","locale":"en","message":"I sent 3000 to wrong number"}'

# Case 2 — payment_failed
curl -X POST https://YOUR_URL/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-002","channel":"app","locale":"en","message":"Payment failed but balance deducted"}'

# Case 3 — phishing (expect critical + human_review_required=true)
curl -X POST https://YOUR_URL/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-003","channel":"sms","locale":"en","message":"Someone called asking my OTP, is that bKash?"}'

# Case 4 — refund_request
curl -X POST https://YOUR_URL/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-004","channel":"app","locale":"en","message":"Please refund my last transaction, I changed my mind"}'

# Case 5 — other
curl -X POST https://YOUR_URL/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-005","channel":"app","locale":"en","message":"App crashed when I opened it"}'

# Health check
curl https://YOUR_URL/health
```

---

## 8. Team Coordination Breakdown (1-hour sprint)

| Time | Who | Task |
|---|---|---|
| 0:00 – 0:05 | All | Clone repo, set up venv, confirm ANTHROPIC_API_KEY works |
| 0:05 – 0:20 | Dev 1 | Run Prompt 1 + 2 → generate schemas.py and prompts.py |
| 0:05 – 0:20 | Dev 2 | Run Prompt 3 → generate classifier.py |
| 0:20 – 0:30 | Dev 1 | Run Prompt 4 → generate main.py, wire everything together |
| 0:20 – 0:30 | Dev 2 | Run Prompt 5 + 6 → README and Dockerfile |
| 0:30 – 0:40 | All | Local test: uvicorn main:app --reload, run curl cases |
| 0:40 – 0:55 | Dev 1 | Deploy to Render, set env vars, wait for build |
| 0:40 – 0:55 | Dev 2 | Final safety checklist (Prompt 6), fix any issues |
| 0:55 – 1:00 | All | Submit Google Form: team name, GitHub URL, live HTTPS URL |

---

## 9. Google Form Submission Checklist

- [ ] Team name (must match registration)
- [ ] GitHub repository URL (must be **public**)
- [ ] Live API base URL (must be **HTTPS**, `/health` must respond)
- [ ] Deployment platform (e.g. Render)
- [ ] LLM used: **Yes — Anthropic Claude (claude-sonnet-4-6)**
- [ ] Known issues (optional)

---

*Generated for SUST CSE Carnival 2026 — QueueStorm Warmup Mock Preliminary*
