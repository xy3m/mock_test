# QueueStorm Warmup Classifier

A small FastAPI microservice that classifies inbound bKash-style customer
support tickets using Google Gemini (`gemini-2.5-flash`). Built as the
1-hour warmup / practice round for the **SUST CSE Carnival 2026 — Codex
Hackathon Mock Preliminary**.

---

## 1. Project Overview

The service exposes a single `POST /sort-ticket` endpoint that takes a raw
customer message and returns a normalized triage result: `case_type`,
`severity`, `department`, a short `agent_summary`, a `human_review_required`
flag, and a `confidence` score. The classifier is wrapped in two safety
guarantees (summary redaction against `pin` / `otp` / `password` / `card
number` mentions, and forced human review for critical / phishing cases) so
the endpoint is safe to call from a real CRM.

---

## 2. Tech Stack

- **Python 3.11+** (developed and tested on 3.13)
- **FastAPI** for the HTTP layer
- **Uvicorn** (ASGI server)
- **Pydantic v2** for request / response models
- **Google Gemini** (`gemini-2.5-flash`) for classification via `google-genai`
- **python-dotenv** for local env loading
- **httpx** (transitive, for the Gemini SDK)

---

## 3. Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/<your-team>/queueStorm-warmup.git
cd queueStorm-warmup

# 2. Create a virtual env
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets
cp .env.example .env
# Open .env and set GEMINI_API_KEY=...

# 5. Run the dev server
uvicorn main:app --reload
```

The service will be available at <http://127.0.0.1:8000>.
Interactive API docs: <http://127.0.0.1:8000/docs>.

---

## 4. API Reference

### `GET /health`

Liveness probe. Returns immediately.

```bash
curl http://127.0.0.1:8000/health
```

```json
{
  "status": "ok",
  "service": "queueStorm-classifier",
  "version": "1.0.0"
}
```

### `POST /sort-ticket`

Classify a single ticket. Response time is bounded by the LLM call (under
30s on the free Render tier, much faster locally).

```bash
curl -X POST http://127.0.0.1:8000/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "T-001",
    "channel": "app",
    "locale": "en",
    "message": "I sent 5000 taka to a wrong number this morning"
  }'
```

Expected response shape:

```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "The customer reports sending 5000 BDT to an incorrect number and is requesting help to recover the funds.",
  "human_review_required": false,
  "confidence": 0.93
}
```

---

## 5. Deployment on Render (free tier)

1. Push the repo to a **public** GitHub repository.
2. In Render, click **New → Web Service** and connect the repo.
3. Set the environment variable `GEMINI_API_KEY` (do **not** commit it).
4. Use these commands:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Wait for the first build. Once it says "live", the URL will be HTTPS.
6. Hit `GET /health` once to confirm it responds.

> **Note:** the free tier spins down after ~15 min of inactivity. The first
> request after sleep may take 20-30s while the container wakes up. Hit
> `/health` first to wake it before timing `/sort-ticket`.

---

## 6. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key used for classification. |
| `PORT` | No | `8000` | Port uvicorn binds to (Render sets this automatically). |
| `LOG_LEVEL` | No | `INFO` | Python logging level. |

---

## 7. Known Limitations

- **Cold start on free tier** — Render's free plan sleeps containers. The
  first `/sort-ticket` call after sleep can approach the 30s budget.
- **No auth on `/sort-ticket`** — this is a mock round. Add an API key /
  OAuth layer before any production use.
- **LLM variance** — outputs are probabilistic; the safety redaction +
  forced `human_review_required` are deterministic guards applied after the
  model returns, so critical cases will always be flagged even if the model
  under-classifies.
- **Synchronous LLM call** — a single Gemini call blocks the request handler.
  For high throughput, switch to the async SDK call (already async-friendly)
  and add a queue / worker pool.

---

## 8. Grader Test Cases

These are the 5 cases the grader will run. After deploying, hit each one
with `curl` and verify the response.

| # | `ticket_id` | Message | Expected `case_type` | Expected `severity` | Expected `department` | `human_review_required` |
|---|---|---|---|---|---|---|
| 1 | `T-001` | `I sent 3000 to wrong number` | `wrong_transfer` | `high` | `dispute_resolution` | `false` |
| 2 | `T-002` | `Payment failed but balance deducted` | `payment_failed` | `high` | `payments_ops` | `false` |
| 3 | `T-003` | `Someone called asking my OTP, is that bKash?` | `phishing_or_social_engineering` | `critical` | `fraud_risk` | **`true`** |
| 4 | `T-004` | `Please refund my last transaction, I changed my mind` | `refund_request` | `low` | `customer_support` | `false` |
| 5 | `T-005` | `App crashed when I opened it` | `other` | `low` | `customer_support` | `false` |

The full reproducible curl script lives in `PLAN.md §7` (or see the
"Quick manual test" section in the project plan).