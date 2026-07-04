# 📧 Production-Grade Email Microservice

FastAPI + aiosmtplib powered **Email Service** for sending transactional, notification, and marketing emails via any SMTP provider (Gmail, SES, Mailgun, Postmark, custom SMTP, etc.).

Built with production best practices:
- Async I/O with `aiosmtplib`
- Strong Pydantic v2 validation (`EmailStr`, attachments, size limits)
- API Key authentication
- Background task processing (non-blocking)
- Full OpenAPI/Swagger documentation
- Proper MIME (text + HTML + attachments)
- Structured logging + error handling
- Docker ready
- Environment-based configuration

---

## ✨ Features

| Feature                    | Status     | Notes |
|---------------------------|------------|-------|
| Send single email         | ✅         | To + CC + BCC |
| HTML + Plain Text         | ✅         | Multipart/alternative |
| Attachments (base64)      | ✅         | Max 5 files, 10MB each |
| Custom headers            | ✅         | X-Campaign-ID etc. |
| Sender / Reply-To override| ✅         | Per-request |
| API Key auth              | ✅         | `X-API-Key` header |
| Background sending        | ✅         | Immediate 202 response |
| Health check              | ✅         | `/api/v1/emails/health` |
| OpenAPI docs              | ✅         | `/docs` (Swagger) & `/redoc` |
| CORS                      | ✅         | Configurable origins |
| Docker + Prod ready       | ✅         | Multi-worker capable |
| Rate limiting             | 🔼         | Add `slowapi` easily |
| Retry / DLQ               | 🔼         | Use Celery + tenacity in v2 |
| Templates (Jinja)         | 🔼         | Easy to add |

---

## 🚀 Quick Start

### 1. Clone / Download

```bash
# The project is located at:
# /home/workdir/artifacts/email-service/
```

### 2. Setup Environment

```bash
cd email-service
cp .env.example .env
# Edit .env with your SMTP credentials and API_KEY
```

**Example `.env` (Gmail example):**

```env
APP_NAME="My Company Email Service"
API_KEY=super-secret-key-change-this-now-1234567890
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME="My Company"
SMTP_USE_TLS=true
SMTP_USE_SSL=false
CORS_ORIGINS=*
LOG_LEVEL=INFO
```

> **Gmail tip**: Use [App Passwords](https://support.google.com/accounts/answer/185833) (not your normal password).

### 3. Install & Run (Development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open Swagger UI: http://localhost:8000/docs

### 4. Run with Docker (Production)

```bash
# Build
docker build -t email-service:latest .

# Run (mount .env or pass env vars)
docker run -d \
  --name email-service \
  -p 8000:8000 \
  --env-file .env \
  email-service:latest
```

**Dockerfile** is included and uses `python:3.11-slim`.

---

## 📡 API Documentation

### Authentication

All protected endpoints require:

```
X-API-Key: <value-from-.env>
```

### Endpoints

#### `POST /api/v1/emails/send`

Send an email. Returns **202 Accepted** immediately. Actual delivery happens in background.

**Request Body** (`application/json`):

```json
{
  "recipients": {
    "to": ["user@example.com"],
    "cc": ["manager@company.com"],
    "bcc": []
  },
  "subject": "Your order has been shipped",
  "text_body": "Hi there,\n\nYour order #12345 has been shipped...",
  "html_body": "<h1>Order Shipped</h1><p>Track it <a href='...'>here</a>.</p>",
  "sender": "shipping@yourcompany.com",
  "reply_to": "support@yourcompany.com",
  "attachments": [
    {
      "filename": "invoice.pdf",
      "content_base64": "JVBERi0xLjQKJ...",
      "content_type": "application/pdf"
    }
  ],
  "headers": {
    "X-Order-ID": "12345",
    "X-Campaign": "summer-sale"
  },
  "tags": {
    "user_id": 42,
    "order_id": "ORD-98765"
  }
}
```

**Success Response (202)**:

```json
{
  "success": true,
  "message": "Email request accepted and queued for delivery",
  "message_id": null,
  "status": "accepted",
  "error": null
}
```

> The real `message_id` is generated and logged during background processing.

**cURL Example**:

```bash
curl -X POST "http://localhost:8000/api/v1/emails/send" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: super-secret-key-change-this-now-1234567890" \
  -d '{
    "recipients": {"to": ["test@example.com"]},
    "subject": "Test from Email Service",
    "text_body": "Hello from the production email microservice!",
    "html_body": "<b>Hello</b> from the <i>production</i> email microservice!"
  }'
```

#### `GET /api/v1/emails/health`

```bash
curl http://localhost:8000/api/v1/emails/health
```

Response:

```json
{
  "status": "healthy",
  "service": "Email Microservice",
  "version": "1.0.0",
  "smtp_configured": true,
  "debug": false
}
```

#### `GET /api/v1/emails/config` (requires API key)

Returns non-sensitive configuration for monitoring.

---

## 🛠️ Project Structure

```
email-service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + middleware + lifespan
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── email.py            # Pydantic models (req/res)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── email_service.py    # Core SMTP logic with aiosmtplib
│   ├── routers/
│       ├── __init__.py
│       ├── email_router.py     # API routes + auth + background tasks
├── .env.example
├── requirements.txt
├── Dockerfile
├── README.md
└── app/main.py                 # Can run directly with python -m
```

---

## 🔒 Production Hardening Checklist

- [x] API Key authentication
- [x] Input validation (Pydantic)
- [x] Size limits on attachments
- [x] No secrets in logs
- [x] Background processing
- [x] Proper MIME construction
- [x] CORS configuration
- [x] Health endpoint
- [ ] Add rate limiting (`slowapi`)
- [ ] Add retry with backoff (`tenacity`)
- [ ] Use Celery + Redis for high throughput / retry / DLQ
- [ ] Add OpenTelemetry tracing + metrics
- [ ] Store sent email metadata in DB (optional audit)
- [ ] Webhook support for bounces (via ESP)
- [ ] Secrets from Vault / AWS Secrets Manager
- [ ] Kubernetes readiness/liveness probes (`/health`)

---

## 🧪 Testing Recommendations

1. Use **Mailtrap** or **MailHog** / **Mailpit** for local testing (fake SMTP).
2. Test with real providers (Gmail, SES) using App Passwords / IAM.
3. Load test with `locust` or `k6` (focus on `/send`).
4. Verify attachments render correctly on major clients (Gmail, Outlook, Apple Mail).

---

## 📈 Scaling for High Volume

Current implementation uses `BackgroundTasks` (in-memory). For production at scale:

**Recommended Architecture**:
```
API (FastAPI) → Redis Queue → Celery Workers → SMTP
```

Replace `background_tasks.add_task(...)` with `celery_app.send_task("tasks.send_email", args=[email_data.model_dump()])`

Add `tenacity` retry decorator around the SMTP send.

---

## 📄 License & Credits

Built with ❤️ using:
- FastAPI
- aiosmtplib
- Pydantic v2
- Uvicorn

For questions or contributions, open an issue or PR.

---

**Ready to send emails in production!** 🚀

Visit `/docs` after starting the server for interactive API exploration.