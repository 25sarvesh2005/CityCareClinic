# CityCare Clinic — Multi-Tenant Healthcare Consultation Platform

[![CI](https://github.com/25sarvesh2005/CityCareClinic/actions/workflows/ci.yml/badge.svg)](https://github.com/25sarvesh2005/CityCareClinic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)

CityCare Clinic is a production-grade, multi-tenant healthcare appointment booking, doctor rostering, and clinical consultation management platform. It orchestrates end-to-end clinical operations across four synchronized client surfaces: a modern React web application, a Model Context Protocol (MCP) server, an omnichannel Telegram patient gateway, and an interactive clinical CLI.

> [!IMPORTANT]
> **Production Architecture Specification**: For complete system invariants, layer dependencies, entity-relationship diagrams, and security boundaries, refer to the authoritative [Architecture Specification](docs/ARCHITECTURE.md).

---

## Key System Capabilities

- **Strict Multi-Tenant Isolation**: Hospital-scoped data boundaries guarantee complete logical separation across doctors, schedules, bookings, and clinical prescriptions.
- **Defensive Appointment Booking Engine**: Enforces four synchronous validation gates (7-day advance booking window, doctor schedule verification, 12 fixed clinic slot menus, and atomic duplicate-booking prevention).
- **Digital Clinical Prescriptions**: Automated medical prescription generation compiling structured dosage schedules into tamper-evident PDF documents with optional Cloudinary CDN distribution.
- **Dual AI Clinical Assistants**:
  - *Schedule Assistant*: Multi-turn natural language conversational agent executing function-calling tools against real-time clinic schedules with model fallback (`gemini-3.6-flash` → `gemini-3.1-flash-lite`).
  - *Prescription Assistant*: Retrieval-Augmented Generation (RAG) assistant leveraging ChromaDB vector embeddings of clinic patient handbooks for drug interaction and clinical guideline verification.
- **Omnichannel Client Interfaces**:
  - **Web Client**: High-performance React 19 Single-Page / SSR application built with TanStack Start, TanStack Router, Radix UI, and TailwindCSS.
  - **FastMCP Server**: Anthropic Model Context Protocol server exposing clinic operations, resources, and confirmation prompts to AI agents under patient JWT authorization.
  - **Telegram Patient Gateway**: Resilient conversational bot supporting symptom intake, doctor discovery, guided scheduling, and secure one-time account linking.
  - **Clinical CLI**: Terminal application for healthcare staff consultation and instant prescription generation.

---

## Interactive API Documentation

When the FastAPI backend is running, live interactive OpenAPI documentation is immediately accessible at:

| Documentation Surface | URL | Description |
|---|---|---|
| **Swagger UI** | `http://localhost:8000/docs` | Interactive API explorer with inline Bearer token authorization |
| **ReDoc** | `http://localhost:8000/redoc` | Comprehensive, structured API reference documentation |
| **OpenAPI Schema** | `http://localhost:8000/openapi.json` | Raw OpenAPI 3.1 JSON specification |
| **Liveness Probe** | `http://localhost:8000/health/liveness` | Kubernetes/service liveness health check |
| **Readiness Probe** | `http://localhost:8000/health/readiness` | Bounded MongoDB ping readiness verification |

---

## Operational Runbooks

Standard operating procedures and disaster recovery guidelines are documented in [`docs/runbooks/`](docs/runbooks/):

- 📖 [Telegram Patient Gateway Runbook](docs/runbooks/telegram_gateway.md) — Webhook configuration, update deduplication, delivery recovery, and session lifecycle.
- 📖 [Model Context Protocol (MCP) Server Runbook](docs/runbooks/mcp_server.md) — FastMCP setup, Streamable HTTP vs stdio transports, tool schemas, and patient authorization bridge.
- 📖 [Disaster Recovery & Environment Governance](docs/runbooks/disaster_recovery_and_seeding.md) — Production configuration validation gates, database migrations, backup/restore procedures, and seeding policies.

---

## Repository Structure

```
CITYCARE_CLINIC/
├── main.py                          # Application entry point, lifespan, CORS, and health probes
├── common/                          # Cross-cutting foundational modules
│   ├── auth.py                      # JWT verification, password hashing, and role dependencies
│   ├── config.py                    # Environment variable management and production validation gates
│   ├── logger.py                    # Structured logging configuration
│   └── tenant_scope.py              # Multi-tenant context extraction and boundary enforcement
├── core/                            # Core hospital and clinic business domains
│   ├── apis/                        # API route aggregation and Pydantic validation schemas
│   ├── constants.py                 # Central single source of truth for enums and clinic constants
│   ├── controllers/                 # Business logic orchestration and booking validation gates
│   ├── cruds/                       # Low-level asynchronous MongoDB operations via ODMantic
│   ├── database/                    # Motor MongoDB connection lifecycle and seeding logic
│   ├── models/                      # ODMantic Document models
│   └── services/                    # Cloudinary media uploads and ReportLab PDF compilation
├── chatbot/                         # AI Schedule Assistant and clinical conversational engine
│   ├── gemini_client.py             # Google GenAI SDK wrapper with multi-turn tool calling
│   ├── prescription_assistant.py    # Structured clinical extraction and drug interaction assistant
│   ├── rag_service.py               # ChromaDB vector store integration with patient handbook embeddings
│   ├── routes/                      # REST endpoints for interactive schedule and prescription chat
│   └── tools.py                     # Execution engine for Gemini function calling tools
├── telegram_bot/                    # Telegram messaging gateway and patient workflow state machine
│   ├── client.py                    # Asynchronous Telegram Bot API client
│   ├── conversation.py              # Natural language parsing and intent classification
│   ├── gateway.py                   # Central dispatcher, state machine transitions, and deduplication
│   ├── medical_assistant.py         # Conversational intake with emergency escalation guards
│   ├── patient_service.py           # Service bridging Telegram requests to core clinic operations
│   └── routes.py                    # Webhook endpoint and one-time account linking code generation
├── mcp_server/                      # FastMCP server exposing clinic operations to AI agents
│   ├── server.py                    # FastMCP app configuration and Streamable HTTP endpoint
│   └── tools/                       # MCP tools (appointments, discovery, prescriptions) and auth bridge
├── cli/                             # Command-line interface utilities
│   ├── commands/                    # Interactive commands (e.g. terminal prescription chat)
│   └── main.py                      # CLI entry point
├── indigo-glow-app-main/            # Modern React 19 + TypeScript + TanStack Start frontend
│   ├── src/                         # Application components, routes, hooks, and API client
│   ├── public/                      # Static web assets and icons
│   └── package.json                 # Frontend dependencies and build scripts
├── docs/                            # Architectural documentation and operational runbooks
│   ├── ARCHITECTURE.md              # Authoritative system architecture document
│   └── runbooks/                    # Operations and disaster recovery runbooks
├── scripts/                         # Operational management scripts (webhooks, migrations, secret audits)
└── tests/                           # Comprehensive test suite (130+ unit, integration, and security tests)
```

---

## Getting Started

### Prerequisites

- **Python**: Version 3.13+
- **Node.js**: Version 20+ LTS
- **Database**: MongoDB 7.0+ (running locally on port 27017 or remote connection string)

### 1. Backend Setup

```bash
# Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install development dependencies
pip install -r requirements-dev.txt

# Configure environment variables
cp .env.example .env

# Start FastAPI development server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Verify backend health at `http://localhost:8000/` or visit interactive documentation at `http://localhost:8000/docs`.

### 2. Frontend Setup

```bash
cd indigo-glow-app-main

# Install dependencies
npm ci

# Start frontend development server
npm run dev
```

Access the web application at `http://localhost:5173`.

### 3. Model Context Protocol (MCP) Server

```bash
# Start MCP server over Streamable HTTP on port 8001
python -m uvicorn mcp_server.server:app --host 127.0.0.1 --port 8001
```

The Streamable HTTP MCP endpoint is accessible at `http://127.0.0.1:8001/mcp`.

---

## Verification & Testing Loop

Run all verification suites locally before committing changes:

```bash
# 1. Bytecode syntax & compilation verification
python -m compileall -q core common chatbot telegram_bot mcp_server cli scripts tests main.py

# 2. Backend import sanity verification
python -c "import main; print('Backend import OK')"
python -c "import mcp_server.server; print('MCP import OK')"

# 3. Backend linting check
ruff check core common chatbot telegram_bot mcp_server cli scripts tests main.py

# 4. Run comprehensive backend test suite
pytest -q

# 5. Client secret leak audit
python scripts/audit_client_secrets.py

# 6. Frontend TypeScript typecheck
cd indigo-glow-app-main && npx tsc --noEmit

# 7. Frontend ESLint validation
npm run lint

# 8. Frontend production bundle build
npm run build
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
