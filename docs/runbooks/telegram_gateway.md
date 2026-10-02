# Runbook: Telegram Patient Gateway Operations

## Overview

The CityCare Clinic Telegram Patient Gateway provides an omnichannel conversational interface enabling patients to discover healthcare providers, check availability, book appointments, and review historical prescriptions using natural language.

---

## 1. Gateway Architecture & Flow

```
Telegram Client
      │
      ▼
HTTPS Webhook (/api/v1/telegram/webhook) OR Local Polling Runner
      │
      ▼ (Header verification: X-Telegram-Bot-Api-Secret-Token)
Deduplication & Idempotency Check (update_id validation against MongoDB)
      │
      ▼
Session State Machine & Natural Language Parser (telegram_bot/gateway.py)
      │
      ├─► Clinical Symptom Assessment & Emergency Escalation
      ├─► Hospital & Doctor Discovery Query
      ├─► Doctor Availability Verification
      ├─► Guided Multi-Turn Booking with Explicit Confirmation
      └─► Account Linking via Secure 10-Minute One-Time Code
      │
      ▼
Core Services & MongoDB Persistence (core/controllers, core/cruds)
      │
      ▼
Outbound Delivery via Telegram Bot API Client
```

---

## 2. Configuration & Environment Variables

The gateway requires the following environment variables configured in `.env`:

| Variable | Description | Production Requirement |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot API token obtained from @BotFather | Required |
| `TELEGRAM_WEBHOOK_SECRET` | Cryptographic secret for `X-Telegram-Bot-Api-Secret-Token` | Required in webhook mode (alphanumeric, 1-256 chars) |
| `TELEGRAM_PUBLIC_WEBHOOK_URL` | Public HTTPS URL pointing to `/api/v1/telegram/webhook` | Required in webhook mode (must use https://) |
| `TELEGRAM_API_BASE_URL` | Base URL for Telegram Bot API | Defaults to `https://api.telegram.org` |

---

## 3. Deployment Modes

### Mode A: Production Webhook Configuration

In production environments, updates are received via push webhook:

1. Verify the public webhook URL is reachable over HTTPS:
   ```bash
   curl -I https://api.citycareclinic.com/health/liveness
   ```

2. Register the webhook with Telegram using the helper script:
   ```bash
   python scripts/configure_telegram_webhook.py --url https://api.citycareclinic.com/api/v1/telegram/webhook
   ```

3. Verify webhook status and delivery health:
   ```bash
   python scripts/configure_telegram_webhook.py --info
   ```

4. Inspect webhook health endpoint:
   ```bash
   curl https://api.citycareclinic.com/api/v1/telegram/health
   ```

### Mode B: Local Development Long-Polling

For local development or testing behind firewalls without public HTTPS ingress:

1. Ensure the webhook is deleted or unset:
   ```bash
   python scripts/configure_telegram_webhook.py --delete
   ```

2. Start the local polling runner:
   ```bash
   python -m telegram_bot.polling
   ```

---

## 4. Idempotency & Delivery Recovery

- **Update Deduplication**: Every incoming `update_id` is registered in `telegram_updates`. If Telegram retries a delivery due to transient upstream timeouts, the gateway detects the existing `update_id` and acknowledges with HTTP 200 without repeating state mutations or double-booking.
- **Workflow State Persistence**: The patient's conversational stage (e.g., `SELECTING_HOSPITAL`, `CHOOSING_DOCTOR`, `SELECTING_SLOT`, `CONFIRMING_BOOKING`) and collected parameters are persisted to MongoDB. If an interaction is interrupted, the patient can resume seamlessly.

---

## 5. Account Linking Runbook

For privacy and security, the Telegram bot **never** solicits passwords in chat:

1. The patient logs into the web application and navigates to **Dashboard → Telegram Integration**.
2. The web application issues a one-time, 6-digit alphanumeric code valid for 10 minutes via `POST /api/v1/telegram/link-code`.
3. The patient sends `/link <code>` to the Telegram bot.
4. The gateway validates the code, links the Telegram `chat_id` to the patient's MongoDB `user_id`, and immediately invalidates the code.
