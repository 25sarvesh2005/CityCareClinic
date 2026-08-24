# Medihub Telegram Patient Gateway

The Telegram interface is an additional patient surface. Existing web routes and dashboards remain unchanged.

## Supported patient operations

- Safe conversational symptom intake and emergency escalation
- Hospital discovery and patient-visible facilities/services
- Doctor listing and specialization filtering
- Guided appointment booking with an explicit final confirmation
- Private appointment and prescription viewing for linked patients
- Telegram-native patient registration without collecting a password in bot chat
- Secure linking of an existing web patient through a one-time, ten-minute code

## Architecture

The implementation follows the useful boundaries from Hermes Agent's gateway design:

```text
Telegram update
  -> Telegram adapter (webhook or local polling)
  -> secret/identity verification
  -> per-user persistent session key and workflow state
  -> patient-only gateway operations
  -> existing Medihub controllers/CRUDs/MongoDB
  -> durable reply ledger
  -> Telegram delivery
```

The relevant Hermes ideas are platform normalization, isolated per-chat sessions, persistent state, authorization before tool execution, bounded memory, explicit confirmation for side effects, and at-least-once delivery recovery. This project implements those patterns directly instead of giving a public medical bot Hermes' general terminal or filesystem tools.

References:

- [Hermes Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)
- [Hermes Telegram setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram)
- [Hermes Gateway internals](https://hermes-agent.nousresearch.com/docs/developer-guide/gateway-internals)
- [Hermes Session storage](https://hermes-agent.nousresearch.com/docs/developer-guide/session-storage)
- [Hermes Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)

## Identity and privacy

Telegram bot chats are not end-to-end encrypted. The bot therefore never asks for a Medihub password.

- New patients use `/register` and provide name, email, and phone number. A random unusable web password is stored as a bcrypt hash; the Telegram identity becomes their bot credential.
- Existing patients authenticate through the web/API once and call `POST /api/v1/telegram/link-code`. They then send `/link CODE` to the bot. The code is high entropy, single-use, and expires after ten minutes.
- Prescriptions and appointments are always scoped to the linked patient ID. Telegram-supplied patient IDs are never accepted.
- Patient workflows are rejected in groups and channels; private bot chats are required.
- `/reset` clears the workflow and short-term transcript but keeps the verified account link.
- Symptom history is used as bounded conversation context. The agent does not autonomously create a permanent disease profile.

## BotFather and environment setup

1. Create a bot with `@BotFather` and keep its token secret.
2. Copy `.env.example` to `.env` and configure:

```dotenv
TELEGRAM_BOT_TOKEN=<BotFather token>
TELEGRAM_WEBHOOK_SECRET=<long random secret>
TELEGRAM_PUBLIC_WEBHOOK_URL=https://your-api.example.com/api/v1/telegram/webhook
```

3. Run the FastAPI service behind HTTPS.
4. Configure Telegram and the command menu:

```powershell
.\.venv\Scripts\python.exe scripts\configure_telegram_webhook.py set
.\.venv\Scripts\python.exe scripts\configure_telegram_webhook.py info
```

Telegram sends the webhook secret in `X-Telegram-Bot-Api-Secret-Token`; the API rejects missing or incorrect secrets before processing the update.

## Local development with long polling

Do not configure a webhook and polling simultaneously. For a local, always-on process:

```powershell
.\.venv\Scripts\python.exe -m telegram_bot.polling
```

For cloud deployments, use the HTTPS webhook because it supports inbound wake-up and avoids continuous polling.

## Hospital facilities

`facilities` and `services` are optional arrays on hospital creation. Existing hospital records remain valid and display a clear “not published” message until values are configured.

Super admins can update an existing hospital with `PATCH /api/v1/admin/hospitals/{hospital_id}/services`.

Example admin payload:

```json
{
  "name": "Medihub Central Hospital",
  "address": "12 MG Road",
  "city": "Pune",
  "contact_number": "+91-20-1234-5678",
  "facilities": ["24/7 Pharmacy", "Diagnostic Lab", "ICU"],
  "services": ["General Medicine", "Cardiology", "Vaccination"]
}
```

## Production checklist

- Use a dedicated bot token per environment and rotate it after any exposure.
- Keep the webhook behind HTTPS and retain secret-header verification.
- Run one polling process or one webhook consumer group, never both.
- Telegram short-term transcripts expire after 30 days and delivery-ledger rows after 7 days; confirm those defaults against your retention policy and configure MongoDB backups accordingly.
- Add distributed per-user locking if the API runs multiple workers; the current lock is process-local while booking database constraints remain authoritative.
- Obtain patient consent and complete the applicable healthcare/privacy review before sending medical records through Telegram.
- Monitor gateway delivery failures without logging bot tokens, link codes, symptoms, or prescription content.
