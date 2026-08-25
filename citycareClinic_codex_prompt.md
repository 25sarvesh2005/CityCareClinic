# CityCareClinic Architecture Codex
## Reusable System Prompt for Any New Project Following This Structure

---

> Copy everything below the horizontal rule into the system-prompt / AGENTS.md / GEMINI.md of any new project that should follow the same architectural conventions as CityCareClinic.

---

---

## SYSTEM PROMPT — PROJECT ARCHITECTURE CODEX

You are building a **Python/FastAPI backend** with an optional **React/TypeScript (Vite + TanStack Router) frontend**, an **AI-powered chatbot**, an **MCP (Model Context Protocol) server**, and a **CLI tool**. Follow every rule in this codex exactly. When in doubt, match the pattern already established in the codebase.

---

## 1. TECHNOLOGY STACK

| Layer | Technology |
|---|---|
| Backend API | FastAPI (async), Python 3.11+ |
| Database ORM | ODMantic (MongoDB async ODM) |
| Async DB Driver | Motor (`AsyncIOMotorClient`) |
| Authentication | JWT via `python-jose`, bcrypt via `passlib` / `bcrypt` |
| Validation | Pydantic v2 (`BaseModel`, `Field`) |
| HTTP Client | `httpx` (async) |
| AI / LLM | `google-genai` SDK |
| RAG | `chromadb`, `langchain-community`, `langchain-google-genai`, `langchain-text-splitters` |
| PDF Generation | `reportlab` |
| File Storage | `cloudinary` |
| MCP Server | `fastmcp` |
| Frontend | Vite + React + TypeScript + TanStack Router |
| Testing | `pytest`, `pytest-asyncio`, `httpx` (ASGITransport) |
| ASGI Server | `uvicorn[standard]` |
| Env vars | `python-dotenv` |

---

## 2. ROOT FOLDER STRUCTURE

```
<project_root>/
├── main.py                          # FastAPI app entry point
├── requirements.txt                 # Pinned dependencies
├── .env                             # Environment variables (never commit secrets)
├── .gitignore
├── README.md
├── PROJECT_DOCUMENTATION.md        # Full architectural documentation
│
├── common/                          # Cross-cutting utilities (auth, logging, tenant)
│   ├── __init__.py
│   ├── auth.py                      # JWT + bcrypt + FastAPI dependencies
│   ├── logger.py                    # Centralized rotating logger
│   └── tenant_scope.py              # Multi-tenant hospital scoping dependency
│
├── core/                            # Domain layer — all business logic lives here
│   ├── __init__.py
│   ├── constants.py                 # All enums, constants, and utility functions
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py              # Motor + ODMantic singleton lifecycle
│   │   └── seed.py                  # Initial data seeder
│   ├── models/                      # ODMantic document models
│   │   └── <entity>_model.py
│   ├── cruds/                       # Pure DB operations — NO business logic
│   │   └── <entity>_crud.py
│   ├── controllers/                 # Business logic — calls CRUDs, raises HTTPException
│   │   └── <entity>_controller.py
│   ├── services/                    # External service integrations (PDF, cloud storage)
│   │   └── <service>_service.py
│   └── apis/
│       ├── __init__.py
│       ├── api.py                   # Master APIRouter that mounts all sub-routers
│       ├── routes/                  # FastAPI route handlers (thin — call controllers)
│       │   └── <entity>_routes.py
│       └── schemas/                 # Pydantic request/response schemas
│           ├── <entity>_schema.py
│           ├── requests/            # (optional) dedicated request-only schemas
│           └── response/            # (optional) dedicated response-only schemas
│
├── chatbot/                         # AI chatbot module
│   ├── __init__.py
│   ├── gemini_client.py             # Gemini API wrapper
│   ├── rag_service.py               # RAG retrieval logic
│   ├── tools.py                     # Function tools for the AI agent
│   ├── <feature>_assistant.py       # High-level conversation orchestrator
│   ├── models/                      # Chatbot-specific Pydantic models
│   ├── schemas/                     # Chatbot request/response schemas
│   ├── controllers/                 # Chatbot controller layer
│   ├── cruds/                       # Chatbot DB operations (chat history, etc.)
│   └── routes/                      # FastAPI routes for chatbot endpoints
│
├── mcp_server/                      # Model Context Protocol server (FastMCP)
│   ├── __init__.py
│   ├── server.py                    # FastMCP app, tools, resources, prompts
│   └── tools/
│       ├── __init__.py
│       ├── auth.py                  # MCP-specific auth (RequesterContext)
│       └── <feature>_tools.py      # MCP tool wrappers (call API or CRUD)
│
├── cli/                             # Terminal CLI (typer / argparse)
│   ├── __init__.py
│   ├── main.py                      # CLI entry point
│   └── commands/
│       ├── __init__.py
│       └── <feature>_command.py
│
├── RAG/                             # Standalone RAG ingestion microservice
│   ├── main.py
│   ├── requirements.txt
│   └── .env
│
├── scripts/                         # One-off operational scripts
│   ├── ingest_docs.py
│   └── migrate_db.py
│
├── tests/                           # pytest test suite
│   ├── conftest.py                  # DB fixture, async_client fixture
│   └── test_<feature>.py
│
├── data/                            # Static or seed data files
├── logs/                            # Runtime log files (auto-created)
├── tmp/                             # Temporary files (gitignored)
│
└── <frontend-app>/                  # Vite + React + TypeScript frontend
    ├── src/
    │   ├── routes/                  # TanStack Router file-based routes
    │   ├── components/              # Reusable UI components
    │   ├── hooks/                   # Custom React hooks
    │   ├── lib/                     # Utility functions, API clients
    │   └── styles.css
    ├── package.json
    └── vite.config.ts
```

---

## 3. FILE HEADER DOCSTRING STANDARD

Every Python file **must** begin with a docstring using this exact banner format:

```python
"""
─────────────────────────────────────────────────────────────────────────────
File        : <relative/path/to/file.py>
Purpose     : One-sentence description of what this file does.

Responsibilities:
    - Bullet 1
    - Bullet 2

Flow:
    Step A
        ↓
    Step B (function name) — description
        ↓
    Step C

Used By:
    - other/module.py

Returns:
    function_name() → ReturnType — description

Raises:
    ExceptionType: When it is raised.
─────────────────────────────────────────────────────────────────────────────
"""
```

Use section dividers inside files:

```python
# ─── Section Title ────────────────────────────────────────────────────────────
```

---

## 4. LOGGING STANDARD

- **Every module** must import and instantiate a logger at the top of the file:
  ```python
  from common.logger import get_logger
  logger = get_logger(__name__)
  ```
- `logger.info(...)` for successful operations.
- `logger.warning(...)` for rejected/refused operations (e.g. auth failures, validation rejections).
- `logger.error("...", exc_info=True)` for caught unexpected exceptions in route handlers.
- `logger.debug(...)` for per-record DB lookups and token operations.
- Never use `print()` in backend code.
- The `common/logger.py` factory must configure both a `StreamHandler` (INFO+) and a `RotatingFileHandler` (DEBUG+, 5 MB / 3 backups) in UTC.

---

## 5. DATABASE LAYER — ODMantic SINGLETON PATTERN

### `core/database/database.py`

- Maintain **two module-level singletons**: `_motor_client` and `_odmantic_engine`.
- Expose three functions:
  - `async connect_to_database()` — reads `MONGO_URL` and `DB_NAME` from env, creates client + engine.
  - `async close_database_connection()` — closes client, resets singletons to `None`.
  - `get_engine() -> AIOEngine` — raises `RuntimeError` if called before connect.
- These are wired to the FastAPI lifespan context manager in `main.py`.

### Models (`core/models/<entity>_model.py`)

- Inherit from `odmantic.Model`.
- Always set `model_config = {"collection": "<collection_name>"}`.
- Define `@classmethod __indexes__` returning a `tuple` of `IndexModel` objects.
- Use `Optional[datetime]` with `default_factory=lambda: datetime.now(timezone.utc)` for timestamps.
- Never store plain-text passwords — only `hashed_password: str`.
- Use `Optional[str]` for foreign key references (stored as string ObjectId).

### CRUDs (`core/cruds/<entity>_crud.py`)

**Rules (enforced strictly):**
1. **No business logic.**
2. **No `HTTPException`.**
3. **No authentication or authorization.**
4. **Only ODMantic/Motor operations via `engine: AIOEngine`.**
5. Every function receives `engine` as its **first argument**.
6. Every function has a complete docstring: Args, Returns, Raises.
7. Log at `DEBUG` level for every read/write with key identifiers.

---

## 6. CONTROLLER LAYER (`core/controllers/<entity>_controller.py`)

- Implement as a **class** (e.g. `class AppointmentController:`).
- Create a backward-compat singleton at module bottom:
  ```python
  appointment_controller = AppointmentController()
  ```
- Controllers:
  - Call `get_engine()` at the start of every method.
  - Call CRUD functions, never ODMantic directly.
  - Own all business logic, validation, and authorization checks.
  - Raise `HTTPException` with precise status codes.
  - Log at `INFO` for success, `WARNING` for expected business failures.
- Never import route-layer code. Controllers are unaware of HTTP.

---

## 7. ROUTES LAYER (`core/apis/routes/<entity>_routes.py`)

- Each route file creates one `APIRouter`:
  ```python
  router = APIRouter(tags=["EntityName"])
  ```
- Route functions are **thin wrappers**:
  1. Call the controller.
  2. Re-raise `HTTPException` as-is.
  3. Catch all other `Exception` and raise `HTTP 500` with a generic message, logging the error with `exc_info=True`.
- Always declare `response_model`, `status_code`, and `summary` on every endpoint decorator.
- Always use `Depends(get_current_user)` or `Depends(get_hospital_scope)` for protected routes — **never decode tokens in the route handler**.
- Prefix pattern: routes live at `/v1/<entity>/...`; the master router adds `/api` prefix.

---

## 8. SCHEMAS (`core/apis/schemas/<entity>_schema.py`)

- All request and response shapes are **Pydantic v2 `BaseModel`** classes.
- Request schemas end with `Request` (e.g. `SignupRequest`).
- Response schemas end with `Response` (e.g. `UserResponse`, `TokenResponse`).
- Use `model_config = ConfigDict(from_attributes=True)` when the schema maps from an ODMantic model.
- Validate inputs tightly: use `Field(min_length=..., max_length=..., pattern=...)`.
- Never expose `hashed_password` in any response schema.

---

## 9. MASTER ROUTER (`core/apis/api.py`)

```python
from fastapi import APIRouter
api_router = APIRouter(prefix="/api")
# Include all domain routers here
api_router.include_router(auth_router)
api_router.include_router(appointment_router)
# ...
```

Register in `main.py`:
```python
app.include_router(api_router)
```

---

## 10. AUTHENTICATION & AUTHORIZATION (`common/auth.py`)

- `hash_password(plain: str) -> str` — bcrypt hash.
- `verify_password(plain: str, hashed: str) -> bool` — bcrypt check.
- `create_access_token(data: dict) -> str` — HS256 JWT.
- `decode_access_token(token: str) -> dict` — raises 401 on failure.
- `get_current_user(token: str = Depends(oauth2_scheme)) -> dict` — FastAPI dependency.
- `require_doctor(current_user = Depends(get_current_user)) -> dict` — RBAC dependency.
- `require_super_admin(current_user = Depends(get_current_user)) -> dict` — RBAC dependency.
- **JWT payload keys**: `user_id`, `email`, `name`, `role`, `hospital_id`.
- All config from env: `JWT_SECRET`, `JWT_ALGORITHM` (HS256), `JWT_EXPIRE_MINUTES` (60).

---

## 11. MULTI-TENANT SCOPING (`common/tenant_scope.py`)

- `get_hospital_scope(current_user = Depends(get_current_user)) -> dict` — FastAPI dependency.
- Roles `DOCTOR` and `HOSPITAL_OWNER` **must** have a non-null `hospital_id` in their JWT or a 403 is raised.
- `PATIENT` and `SUPER_ADMIN` are unscoped (hospital_id may be None).
- **Rule**: Controllers and CRUDs must NEVER derive tenant scope from request body fields — always from the JWT via this dependency.

---

## 12. CONSTANTS (`core/constants.py`)

- Single source of truth for **all enums, domain constants, and slot utility functions**.
- All enums inherit `(str, Enum)` so FastAPI serializes them as plain strings.
- Named constants use `Final[type]` annotation.
- Pure utility functions (no I/O, no DB calls) may live here alongside constants.

---

## 13. MAIN.PY STRUCTURE

```python
# 1. File header docstring with full Flow description
# 2. load_dotenv()
# 3. logger = get_logger(__name__)
# 4. @asynccontextmanager async def lifespan(app):
#      - connect_to_database()
#      - seed_initial_users()
#      yield
#      - close_database_connection()
# 5. app = FastAPI(title=..., description=..., version=..., lifespan=lifespan, ...)
# 6. app.add_middleware(CORSMiddleware, ...)
# 7. app.include_router(api_router)
# 8. @app.get("/") health check endpoint
```

---

## 14. MCP SERVER (`mcp_server/`)

### `mcp_server/server.py`

- Use `FastMCP` as the MCP app.
- Wire to database via a `@asynccontextmanager` lifespan function.
- Expose tools via `@mcp.tool` decorators.
- Expose resources via `@mcp.resource(...)` for policy/config documents.
- Expose prompt templates via `@mcp.prompt(...)`.
- All tool args must be `Annotated[type, Field(description="...", ...)]`.
- Authorization happens **inside** tool functions — never in the transport layer.
- Serve via `mcp.http_app(path="/mcp", transport="streamable-http")`.

### `mcp_server/tools/auth.py`

- Define `RequesterContext` dataclass: `user_id`, `email`, `role`, `hospital_id`, `raw_token`.
- `requester_from_mcp_context(ctx: Context) -> RequesterContext` — extracts + validates JWT from MCP request headers.
- `authorization_header_from_mcp_context(ctx: Context) -> str` — returns raw `Bearer ...` string.
- `MCPAuthorizationError(RuntimeError)` — safe user-facing error for auth failures.

### `mcp_server/tools/<feature>_tools.py`

- MCP tool implementations call the existing CRUD layer or HTTP API — never duplicate business logic.
- Async HTTP calls use `httpx.AsyncClient`.
- All HTTP errors are caught and wrapped in a domain-specific `Error(RuntimeError)` class.

---

## 15. CHATBOT MODULE (`chatbot/`)

- `gemini_client.py` — thin wrapper around `google.genai` SDK with retry logic.
- `rag_service.py` — ChromaDB retrieval, embedding with `langchain-google-genai`.
- `tools.py` — function declarations for the AI agent's tool-use loop.
- `<feature>_assistant.py` — conversation orchestrator:
  - Safety guard patterns (emergency, medical advice refusal, off-topic) defined as regex tuples.
  - Intent routing: classify query → call appropriate retrieval or tool function.
  - Pure functions for each intent type, returning structured response dicts.
- Chatbot routes registered in `core/apis/api.py`.

---

## 16. TESTING (`tests/`)

### `conftest.py` Rules

- Set `DB_NAME` to `<appname>_test_db` in env before importing the app.
- `setup_db` fixture (`autouse=True`, `async`):
  1. `await connect_to_database()`
  2. Wipe all collections via `engine.remove(Model)` for every model.
  3. Seed default accounts.
  4. `yield engine`
  5. Wipe all collections again.
  6. `await close_database_connection()`
- `async_client` fixture: `ASGITransport(app=app)` + `AsyncClient`.
- Complex shared setup (e.g. creating hospital + owner + doctor) must be extracted into named fixtures (e.g. `booking_context`).

### Test File Rules

- One test file per feature: `test_<feature>.py`.
- Every test is an `async def test_...` function.
- Test both **happy path** and **error cases** (401, 403, 404, 409, 422).
- Never share state between tests — each test is fully isolated by `setup_db`.

---

## 17. ENVIRONMENT VARIABLES (`.env`)

Required keys — adapt values per project:

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=<project>_db
JWT_SECRET=<long-random-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
GOOGLE_API_KEY=<your-gemini-key>
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
MCP_HOST=127.0.0.1
MCP_PORT=8001
MCP_TRANSPORT=streamable-http
CITYCARE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 18. DEPENDENCY NAMING CONVENTION

| File name pattern | Purpose |
|---|---|
| `<entity>_model.py` | ODMantic document |
| `<entity>_crud.py` | Raw DB operations |
| `<entity>_controller.py` | Business logic + validation |
| `<entity>_routes.py` | HTTP route handlers |
| `<entity>_schema.py` | Pydantic request/response models |
| `<entity>_service.py` | External service wrapper |
| `<entity>_tools.py` | MCP or AI tool wrappers |

---

## 19. CODING STYLE RULES

1. **All functions and methods must have complete docstrings**: Args, Returns, Raises.
2. **Type annotations everywhere** — no untyped function signatures.
3. **`Optional[X]`** for nullable fields (use `from typing import Optional`).
4. **`Final[type]`** for module-level constants.
5. **`str(Enum)` inheritance** for all enums used in API responses.
6. **`from __future__ import annotations`** at the top of files with forward references.
7. **No circular imports** — dependency direction: `routes → controllers → cruds → models`.
8. **Never** call `get_engine()` in a route handler — only in controllers and CRUDs.
9. **Never** put business logic in route handlers or CRUDs.
10. **`strip().lower()`** all email inputs before DB operations.
11. Every response from a route must match its declared `response_model`.
12. All DB foreign keys stored as `str` (ObjectId hex string), never as `ObjectId`.

---

## 20. REQUEST FLOW (MANDATORY MENTAL MODEL)

```
HTTP Request
    ↓
Route Handler (routes/*.py)
    — validates auth via Depends(get_current_user / get_hospital_scope)
    — calls Controller method
    — re-raises HTTPException; wraps other errors as 500
    ↓
Controller (controllers/*.py)
    — gets engine via get_engine()
    — applies business rules
    — raises HTTPException on rule violations
    — calls CRUD functions
    ↓
CRUD (cruds/*.py)
    — pure ODMantic operations
    — no exceptions, no logic
    — returns domain model objects
    ↓
MongoDB (via Motor + ODMantic engine)
```

---

## 21. SERVICES LAYER (`core/services/`)

- Wrap **external APIs** (Cloudinary, PDF generation, email, etc.).
- Never import FastAPI or raise HTTPException — services raise plain Python exceptions.
- Controllers catch service exceptions and convert them to HTTPException.

---

## 22. SCRIPTS (`scripts/`)

- `migrate_db.py` — run once to set up indexes or migrate data.
- `ingest_docs.py` — ingest PDFs/documents into the RAG vector store.
- Scripts are standalone: they load `.env` and call `connect_to_database()` themselves.

---

## 23. CLI (`cli/`)

- Entry point: `cli/main.py` — sets up the CLI app (typer or argparse).
- Commands: `cli/commands/<feature>_command.py`.
- CLI commands may call controllers or CRUDs directly after connecting to DB.

---

## 24. FRONTEND (Vite + React + TanStack Router)

- File-based routing under `src/routes/`.
- Shared components in `src/components/`.
- Custom hooks in `src/hooks/`.
- API utility functions in `src/lib/`.
- All API calls use a typed fetch wrapper — never raw `fetch` in components.
- Auth state managed via a context or Zustand store.
- Protected routes redirect unauthenticated users to `/login`.
- Role-based route guards for `patient`, `doctor`, `hospital_owner`, `super_admin`.

---

## 25. WHAT NOT TO DO

| ❌ Anti-pattern | ✅ Correct approach |
|---|---|
| Business logic in route handler | Move to controller |
| HTTPException in CRUD | Raise in controller |
| `print()` statements | `logger.info/debug/warning/error()` |
| Decoding JWT in route body | `Depends(get_current_user)` |
| `engine` as global variable | `get_engine()` called per function |
| Storing plain-text password | `hash_password()` before saving |
| Duplicate business logic in MCP tools | MCP tools call existing CRUD/API |
| Tenant id from request body | Tenant id from JWT via `get_hospital_scope` |
| Shared state between tests | `autouse` db fixture isolates each test |
| Untyped function signatures | Full type annotations everywhere |

---

*End of Codex. Use this as the system prompt / AGENTS.md for any new project following the CityCareClinic architecture.*
