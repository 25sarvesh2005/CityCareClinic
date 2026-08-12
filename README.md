# CityCare MCP Day 7

CityCare exposes its existing appointment API through an MCP server in `mcp_server/server.py`. The server reuses the API as the source of truth: it does not recreate appointment dates, capacity rules, duplicate-booking checks, or patient identity in MCP.

## What the server exposes

| MCP capability | Name | Purpose |
| --- | --- | --- |
| Tool | `get_available_slots` | Retrieves real, doctor-specific availability from CityCare's Day-4 API. |
| Tool | `book_appointment` | Creates an appointment for the patient represented by the verified CityCare JWT. |
| Resource | `citycare://appointment-booking-policy` | Safe ordering and confirmation rules for appointment booking. |
| Prompt | `book_appointment_safely` | A reusable model instruction for availability-first, confirmation-required booking. |

The existing prescription, patient-appointment, and doctor-schedule MCP tools remain available.

## Run the Inspector

From the project root:

```powershell
.\.venv\Scripts\fastmcp.exe dev mcp_server\server.py --ui-port 6274 --server-port 6277
```

Open the Inspector URL printed by FastMCP. It should list tools, one resource, and one prompt. The non-interactive equivalent is:

```powershell
.\.venv\Scripts\fastmcp.exe inspect mcp_server\server.py --format mcp
```

## Run CityCare and the MCP HTTP server

Start CityCare's API in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Start the MCP server under Uvicorn in another terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn mcp_server.server:app --host 127.0.0.1 --port 8001
```

The Streamable HTTP MCP endpoint is `http://127.0.0.1:8001/mcp`.

`CITYCARE_API_BASE_URL` is optional and defaults to `http://127.0.0.1:8000`. Set it only when CityCare runs at a different origin.

### Transport swap

Changing from `stdio` to Streamable HTTP changes only how the client connects: a local process stream becomes the `/mcp` HTTP endpoint served by Uvicorn. The tools, resource, prompt, schemas, JWT checks, and CityCare booking API remain the same.

## Codex (local development)

Codex Desktop, the Codex CLI, and the Codex IDE extension share the MCP configuration in `%USERPROFILE%\.codex\config.toml`. Start CityCare's API on port 8000, log in as a **patient** at `POST /api/v1/login`, then add the following server section to that file. Preserve your existing configuration and use a short-lived patient JWT only for local development.

```toml
[mcp_servers.citycare_clinic]
command = "C:\\Games\\FOLDER PRACTICE\\CITYCARE_CLINIC\\.venv\\Scripts\\fastmcp.exe"
args = [
  "run",
  "C:\\Games\\FOLDER PRACTICE\\CITYCARE_CLINIC\\mcp_server\\server.py:mcp",
  "--transport",
  "stdio"
]
cwd = "C:\\Games\\FOLDER PRACTICE\\CITYCARE_CLINIC"
startup_timeout_sec = 20
tool_timeout_sec = 60
default_tools_approval_mode = "prompt"

[mcp_servers.citycare_clinic.env]
CITYCARE_API_BASE_URL = "http://127.0.0.1:8000"
CITYCARE_MCP_JWT = "PASTE_A_SHORT_LIVED_PATIENT_JWT_HERE"
```

Restart Codex, then type `/mcp` to confirm **citycare_clinic** is connected. Ask: "Find real slots for this doctor tomorrow, then book the 10:00 slot only after I confirm." The model should first select `get_available_slots`, then call `book_appointment` only after explicit confirmation.

The wording that steers correct tool selection is intentional:

- Availability tool: “**Get real slots ... before proposing or booking**.”
- Booking tool: “**Exact available slot returned by get_available_slots and explicitly confirmed**.”
- Booking identity: “**never from tool arguments**.”

`CITYCARE_MCP_JWT` is only a local-stdio development bridge. Do not expose it in a public deployment, source control, screenshots, or logs.

## Proof of persistence

`tests/test_mcp_day7.py` invokes the registered `book_appointment` MCP handler, forwards the patient JWT to the Day-4 `/api/v1/book` endpoint, and then queries MongoDB for the returned appointment ID. It proves that the appointment created through MCP is persisted, while the test database is isolated and cleaned afterwards.

Run it with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_mcp_day7.py -q
```

## Security review — `book_appointment`

| Manipulated-model misuse | Guard | Chapter 7 safety mapping |
| --- | --- | --- |
| Supplies another patient's ID or name to book on their behalf. | The tool accepts neither field. CityCare derives patient identity from a validated bearer JWT and the MCP tool rejects non-patient roles. | Authorization and least privilege. |
| Books a guessed slot, repeats bookings, or acts before the patient agrees. | The tool description and prompt require an exact slot returned by availability plus explicit consent; the API independently rejects unavailable slots and same-day duplicates. Add a confirmation nonce/idempotency key before production. | Human confirmation and transaction integrity. |
| Injects invalid values or fabricated medical details to force a booking. | Typed schemas constrain IDs, dates, temperature, and symptoms; the API repeats validation and no tool output exposes credentials. Add per-user rate limits, audit events, and anomaly alerts for public use. | Input validation, defense in depth, and auditability. |

## Public deployment

Use **Streamable HTTP** behind HTTPS, with an OAuth 2.1/OIDC access-token flow at the HTTP boundary and CityCare JWT/tenant authorization inside every protected tool. Do not use the local `CITYCARE_MCP_JWT` environment fallback outside a single-user development machine; add request rate limits, idempotency keys, audit logs, token rotation, and an allowlisted CORS/reverse-proxy configuration before public access.
