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

1. In Telegram, open the verified `@BotFather`, send `/newbot`, choose a display
   name, and choose a unique username ending in `bot`. Keep the returned token secret.
2. Install dependencies and ensure MongoDB is running:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`. Generate a webhook secret containing only
   Telegram's permitted characters:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

4. Configure the three required values. The public URL must include the app's
   `/api` prefix and must be reachable over HTTPS:

```dotenv
TELEGRAM_BOT_TOKEN=<BotFather token>
TELEGRAM_WEBHOOK_SECRET=<generated hex secret>
TELEGRAM_PUBLIC_WEBHOOK_URL=https://your-api.example.com/api/v1/telegram/webhook
```

`GEMINI_API_KEY` is optional. Without it, deterministic medical safety guidance
and all hospital operations still work.

5. Start the API and check gateway configuration without exposing credentials:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/api/v1/telegram/status` and confirm both configuration
flags are `true`. Production must put this service behind a valid HTTPS endpoint.

6. Register the webhook and command menu, then inspect Telegram's result:

```powershell
.\.venv\Scripts\python.exe scripts\configure_telegram_webhook.py set
.\.venv\Scripts\python.exe scripts\configure_telegram_webhook.py info
```

Telegram sends the webhook secret in `X-Telegram-Bot-Api-Secret-Token`; the API rejects missing or incorrect secrets before processing the update.
The setup script uses one Telegram webhook connection so multi-step patient
workflows remain ordered. Do not increase it until a distributed per-patient
lock is implemented.

7. Open `https://t.me/<your_bot_username>`, press **Start**, and test:

```text
/start
/hospitals
/doctors
/speciality cardiology
/register
```

To link an existing web patient, authenticate as that patient, call
`POST /api/v1/telegram/link-code`, and send the returned `/link CODE` to the bot.
Then test `/appointments` and `/prescriptions`.

## Local development with long polling

Do not configure a webhook and polling simultaneously. Telegram disables
`getUpdates` while a webhook exists. Delete the webhook first, then run:

```powershell
.\.venv\Scripts\python.exe scripts\configure_telegram_webhook.py delete
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
- Run exactly one polling process, or keep the configured webhook at one
  connection; never run polling and a webhook together.
- Telegram short-term transcripts expire after 30 days and delivery-ledger rows after 7 days; confirm those defaults against your retention policy and configure MongoDB backups accordingly.
- Add distributed per-user locking before increasing webhook concurrency; update
  IDs and one-time link codes are already claimed atomically in MongoDB.
- Obtain patient consent and complete the applicable healthcare/privacy review before sending medical records through Telegram.
- Monitor gateway delivery failures without logging bot tokens, link codes, symptoms, or prescription content.
