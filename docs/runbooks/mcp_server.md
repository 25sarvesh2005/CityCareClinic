# Runbook: Model Context Protocol (MCP) Server Operations

## Overview

CityCare Clinic provides a Model Context Protocol (MCP) server adhering to the Anthropic/FastMCP standard. It enables external AI agents (e.g. Claude Desktop, Codex, IDE assistants) to interact with CityCare's appointment and clinic APIs safely and under strict user authorization.

---

## 1. Exposed Capabilities

| Capability Type | Identifier | Description |
|---|---|---|
| **Tool** | `search_hospitals` | Finds active healthcare facilities by name, city, or address keyword. |
| **Tool** | `list_hospital_doctors` | Lists practicing doctors and specialties for a given hospital tenant. |
| **Tool** | `get_available_slots` | Fetches real-time, doctor-specific consultation slots for a target date. |
| **Tool** | `book_appointment` | Books a consultation slot under verified patient JWT credentials. |
| **Tool** | `list_patient_appointments` | Retrieves historical and upcoming appointments for the authenticated patient. |
| **Tool** | `list_patient_prescriptions` | Fetches generated medical prescriptions and downloadable PDF links. |
| **Tool** | `get_doctor_schedule` | Retrieves daily consultation rosters for authenticated doctors. |
| **Resource** | `citycare://appointment-booking-policy` | Safety guidelines, advance booking bounds, and confirmation policy. |
| **Prompt** | `book_appointment_safely` | Reusable workflow prompt enforcing availability checks before booking. |

---

## 2. Server Configuration & Transports

The server supports two standard transports:
1. **Streamable HTTP (Server-Sent Events)**: For networked microservice architectures and multi-tenant agent gateways.
2. **Standard I/O (`stdio`)**: For direct subprocess execution by desktop applications.

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CITYCARE_API_BASE_URL` | Base URL of the CityCare FastAPI backend | `http://127.0.0.1:8000` |
| `MCP_HOST` | Host address for HTTP transport | `127.0.0.1` |
| `MCP_PORT` | Port for HTTP transport | `8001` |
| `MCP_TRANSPORT` | Transport mode (`streamable-http` or `stdio`) | `streamable-http` |
| `CITYCARE_MCP_JWT` | Short-lived patient token (stdio local development only) | None |

---

## 3. Running the MCP Server

### Running with Streamable HTTP

Start the CityCare backend in one terminal:
```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Start the MCP server in a separate terminal:
```bash
cd backend
python -m uvicorn mcp_server.server:app --host 127.0.0.1 --port 8001
```

The Streamable HTTP endpoint is available at:
`http://127.0.0.1:8001/mcp`

### Running the FastMCP Inspector

Inspect tools, schemas, resources, and prompts interactively:
```bash
cd backend
fastmcp dev mcp_server/server.py --ui-port 6274 --server-port 6277
```

Non-interactive schema validation:
```bash
cd backend
fastmcp inspect mcp_server/server.py --format mcp
```

---

## 4. Security & Authorization Model

1. **Patient Identity Never Provided by Tool Arguments**:
   The `book_appointment` MCP tool strictly prohibits accepting `patient_id` or `patient_name` from model parameters. Patient identity is derived solely from the cryptographically verified JWT bearer token supplied in the request context.

2. **Confirmation Enforcement**:
   Model prompts and tools explicitly enforce a two-phase commit:
   - Phase 1: Call `get_available_slots` to retrieve verified, real-time unbooked slots.
   - Phase 2: Require explicit user confirmation before executing `book_appointment`.
