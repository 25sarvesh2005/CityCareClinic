# Runbook: Disaster Recovery, Database Migrations & Environment Governance

## Overview

This runbook documents operational procedures for database management, data migrations, backup/restore cycles, environment configuration audits, and data seeding policies for the CityCare Clinic platform.

---

## 1. Environment Verification & Validation Gates

On every application startup, `main.py` executes `common.config.validate_config()`. This validation gate enforces:

- **Environment Setting (`APP_ENV`)**: Must be explicitly set to `development`, `test`, or `production`.
- **JWT Cryptographic Hardening**:
  - `JWT_ALGORITHM` must be one of `HS256`, `HS384`, `HS512`.
  - In `production`, `JWT_SECRET` must be at least 32 characters, cannot be empty, and cannot contain placeholder or default strings.
- **CORS Origin Validation**:
  - In `production`, wildcard `*` origins are strictly prohibited.
  - All origins must use the `https://` protocol and contain valid hostnames.
- **Seeding Prohibitions**:
  - `SEED_DEMO_USERS` is strictly prohibited in `production`. Attempting to boot the API with `SEED_DEMO_USERS=true` in production aborts startup immediately with HTTP-preventative exceptions.

---

## 2. Database Migrations

Database migrations are located in `scripts/`. To apply non-destructive schema migrations:

1. Test connection to the target database:
   ```bash
   python -c "from common.config import get_mongo_url, get_db_name; print('Target:', get_mongo_url(), get_db_name())"
   ```

2. Execute the migration script:
   ```bash
   python scripts/migrate_db.py
   ```

3. Verify modified document count in logs.

---

## 3. Vector Database (RAG) Document Ingestion

The clinical RAG assistant references a persistent ChromaDB vector store populated from medical handbooks.

To re-index or update handbook documents:

```bash
python scripts/ingest_docs.py --pdf-path backend/data/handbook/CityCare-Clinic-Patient-Handbook.pdf
```

The script chunks text, generates vector embeddings, and stores them in `data/chroma_db/`.

---

## 4. Backup & Disaster Recovery Procedures

### MongoDB Automated Backup
```bash
# Dump target MongoDB database
mongodump --uri="$MONGO_URL" --db="$DB_NAME" --out="/backups/citycare_$(date +%Y%m%d_%H%M%S)"
```

### MongoDB Restore
```bash
# Restore specific point-in-time backup
mongorestore --uri="$MONGO_URL" --db="$DB_NAME" --drop "/backups/citycare_20261002_000000/$DB_NAME"
```

### ChromaDB Vector Store Backup
Copy or snapshot the `data/chroma_db/` directory while the service is paused, or maintain reproducible ingestion pipelines via `scripts/ingest_docs.py`.
