# P0: Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up an empty `investment-platform-v2` repo into a deployed-on-Cloud-Run FastAPI service with full DB schema, JWT + Google auth, audit logging, basic CRUD for accounts/instruments, and CI/CD — ready to receive transaction ledger work in P1.

**Architecture:** Single-process FastAPI on Cloud Run. SQLAlchemy 2.0 with `Mapped[]` annotations. Alembic for migrations. Three auth entry points (Google for browser, password for CLI/MCP, service token for scheduler) all minted as HS256 JWTs verified by one shared dependency. All mutations write `audit_log`. Postgres in shared `paulfun-postgres` container with new DB `investment_v2`.

**Tech Stack:** Python 3.14 · FastAPI 0.117+ · SQLAlchemy 2.0 · Alembic · Pydantic v2 · pydantic-settings · python-jose (JWT) · passlib + bcrypt · pytest + httpx · ruff + mypy · Docker · Cloud Build · Cloud Run · Artifact Registry · GitHub Actions

**Reference Spec:** `docs/superpowers/specs/2026-05-12-investment-platform-v2-design.md`

---

## File Structure

```
investment-platform-v2/
├── .github/workflows/
│   ├── ci.yml                          # lint + test on PR
│   └── deploy.yml                      # build + push + deploy on main
├── .gitignore
├── .dockerignore
├── pyproject.toml                      # ruff, mypy, pytest config
├── requirements.txt                    # runtime deps
├── requirements-dev.txt                # dev deps
├── Dockerfile
├── docker-compose.dev.yml              # local pg
├── cloudbuild.yaml
├── alembic.ini
├── README.md                           # human entry
├── CLAUDE.md                           # Claude entry
├── AGENTS.md                           # agent operation guide
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app, lifespan, router mounts
│   ├── config.py                       # Settings (pydantic-settings)
│   ├── db.py                           # SQLAlchemy engine + session
│   ├── dependencies.py                 # get_db, get_current_user
│   ├── security.py                     # JWT encode/decode/verify, bcrypt
│   ├── audit.py                        # audit_log writer
│   ├── errors.py                       # exception → JSON handler
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                     # DeclarativeBase + TimestampMixin
│   │   ├── user.py
│   │   ├── allowlisted_email.py
│   │   ├── refresh_token.py
│   │   ├── account.py
│   │   ├── instrument.py
│   │   ├── industry.py
│   │   └── audit_log.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                     # LoginRequest, TokenResponse, ...
│   │   ├── user.py
│   │   ├── account.py
│   │   ├── instrument.py
│   │   └── errors.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── refresh_token.py
│   │   ├── allowlisted_email.py
│   │   ├── account.py
│   │   └── instrument.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── account.py
│   │   └── instrument.py
│   └── routers/
│       ├── __init__.py
│       ├── auth.py
│       ├── accounts.py
│       ├── instruments.py
│       ├── admin.py
│       └── health.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_2026-05-12_create_initial_schema.py
├── scripts/
│   ├── init_db.py
│   ├── seed_industries.sql
│   └── generate_service_token.py
├── tests/
│   ├── conftest.py                     # DB fixture, client fixture
│   ├── unit/
│   │   ├── test_security.py
│   │   ├── test_audit.py
│   │   ├── test_repositories.py
│   │   └── test_services.py
│   └── integration/
│       ├── test_auth_api.py
│       ├── test_accounts_api.py
│       ├── test_instruments_api.py
│       └── test_e2e_smoke.py
└── docs/
    ├── api.md
    ├── data-model.md
    └── superpowers/
        ├── specs/2026-05-12-investment-platform-v2-design.md
        └── plans/2026-05-12-p0-foundations.md         (this file)
```

---

## Conventions used in this plan

- **Python**: 3.14 — install via `uv` or `pyenv` locally
- **Package manager**: `pip` with `requirements*.txt` (matches v1 — minimal change)
- **SQLAlchemy**: 2.0 syntax (`DeclarativeBase`, `Mapped[]`, `mapped_column()`)
- **Pydantic**: v2 (`model_config`, `Field`, `model_validator`)
- **Test runner**: `pytest`
- **Lint**: `ruff check` + `ruff format`
- **Type check**: `mypy --strict app/`
- **Commit prefix**: Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `refactor:`)
- **Each task ends with a commit step** — frequent commits, atomic changes


---

## Phase 0a — Repo Foundation (Tasks 1-6)

Goal: Empty repo → running FastAPI service deployed to Cloud Run with `/healthz` returning 200. No DB yet.

---

### Task 1: Project skeleton + Python tooling

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `.dockerignore`
- Create: `README.md`

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
venv/
.env
.env.local
*.log
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
.DS_Store
.idea/
.vscode/
```

- [ ] **Step 2: Create `.dockerignore`**

```
.git
.github
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
tests/
docs/
.env
.env.local
*.md
```

- [ ] **Step 3: Create `requirements.txt`**

```
fastapi==0.117.1
uvicorn[standard]==0.32.0
pydantic==2.9.2
pydantic-settings==2.6.0
SQLAlchemy==2.0.36
alembic==1.14.0
psycopg[binary,pool]==3.2.3
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
google-auth==2.35.0
httpx==0.27.2
python-multipart==0.0.20
itsdangerous==2.2.0
jinja2==3.1.4
```

- [ ] **Step 4: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==6.0.0
ruff==0.8.0
mypy==1.13.0
types-python-jose==3.3.4.20240106
types-passlib==1.7.7.20240819
```

- [ ] **Step 5: Create `pyproject.toml`**

```toml
[project]
name = "investment-platform-v2"
version = "0.1.0"
description = "Multi-asset portfolio platform with AI integration"
requires-python = ">=3.14"

[tool.ruff]
line-length = 100
target-version = "py314"
extend-exclude = ["alembic/versions"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM", "RUF"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.14"
strict = true
exclude = ["tests/", "alembic/"]
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["passlib.*", "jose.*", "google.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers --cov=app --cov-report=term-missing"
```

- [ ] **Step 6: Create `README.md`**

```markdown
# Investment Platform v2

Multi-asset portfolio platform — TW stocks, US stocks, crypto, bank deposits, funds — with Claude Code MCP integration and AI-generated weekly reports.

## Development

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Deployment

See `docs/api.md` and `cloudbuild.yaml`. Production: https://invest.paulfun.net
```

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: project skeleton + tooling config"
```

---

### Task 2: Settings/Config module

**Files:**
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing test `tests/unit/test_config.py`**

```python
from app.config import Settings


def test_settings_loads_required_fields(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client.apps.googleusercontent.com")

    settings = Settings()

    assert settings.db_url == "postgresql+psycopg://u:p@h/d"
    assert settings.jwt_secret == "a" * 32
    assert settings.google_oauth_client_id == "client.apps.googleusercontent.com"
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_minutes == 15
    assert settings.refresh_token_days == 30


def test_settings_rejects_short_jwt_secret(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("JWT_SECRET", "too-short")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "x")

    import pytest

    with pytest.raises(ValueError):
        Settings()
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
pytest tests/unit/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Create `app/__init__.py`** (empty file)

- [ ] **Step 4: Create `tests/__init__.py`** (empty)
- [ ] **Step 5: Create `tests/unit/__init__.py`** (empty)

- [ ] **Step 6: Implement `app/config.py`**

```python
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = Field(..., min_length=10)
    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    google_oauth_client_id: str

    first_admin_email: str = "pin0513@gmail.com"
    allowed_origins: str = "http://localhost:8000"

    log_level: str = "INFO"
    environment: str = "dev"

    @field_validator("jwt_secret")
    @classmethod
    def _check_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 chars")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Run test, expect PASS**

```bash
pytest tests/unit/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add app/ tests/
git commit -m "feat(config): Settings with env validation"
```

---

### Task 3: FastAPI app skeleton with /healthz

**Files:**
- Create: `app/main.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/health.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_health.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _set_test_env():
    os.environ.setdefault("DB_URL", "postgresql+psycopg://test:test@localhost:5432/test")
    os.environ.setdefault("JWT_SECRET", "x" * 64)
    os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test.apps.googleusercontent.com")
    os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
```

- [ ] **Step 2: Write failing test `tests/integration/test_health.py`**

```python
def test_healthz_returns_200(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
```

- [ ] **Step 3: Run test, expect FAIL**

```bash
pytest tests/integration/test_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: Create `app/routers/__init__.py`** (empty)

- [ ] **Step 5: Implement `app/routers/health.py`**

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 6: Implement `app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Investment Platform v2",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 7: Create `tests/integration/__init__.py`** (empty)

- [ ] **Step 8: Run test, expect PASS**

```bash
pytest tests/integration/test_health.py -v
```

Expected: 1 passed.

- [ ] **Step 9: Run dev server locally to smoke-test**

```bash
uvicorn app.main:app --reload --port 8080
# In another shell:
curl http://localhost:8080/healthz
# Expected: {"status":"ok","version":"0.1.0"}
# Ctrl+C
```

- [ ] **Step 10: Commit**

```bash
git add app/ tests/
git commit -m "feat(app): FastAPI skeleton with /healthz"
```

---

### Task 4: Dockerfile + local docker-compose

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.dev.yml`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/

EXPOSE 8080

# Cloud Run injects PORT; default 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

- [ ] **Step 2: Create `docker-compose.dev.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: investment_user
      POSTGRES_PASSWORD: dev_pw
      POSTGRES_DB: investment_v2
    ports:
      - "5433:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data

  app:
    build: .
    depends_on:
      - db
    environment:
      DB_URL: postgresql+psycopg://investment_user:dev_pw@db:5432/investment_v2
      JWT_SECRET: dev_secret_at_least_32_chars_long_xxxxxxxx
      GOOGLE_OAUTH_CLIENT_ID: dev-client.apps.googleusercontent.com
      ENVIRONMENT: dev
    ports:
      - "8080:8080"

volumes:
  pg_data:
```

- [ ] **Step 3: Build image locally to verify Dockerfile**

```bash
docker build -t investment-platform-v2:dev .
```

Expected: build succeeds.

- [ ] **Step 4: Smoke-test container (without DB needed for /healthz)**

```bash
docker run --rm -p 8080:8080 \
  -e DB_URL=postgresql+psycopg://x:x@localhost/x \
  -e JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
  -e GOOGLE_OAUTH_CLIENT_ID=x \
  investment-platform-v2:dev &
sleep 3
curl http://localhost:8080/healthz
docker stop $(docker ps -q --filter ancestor=investment-platform-v2:dev)
```

Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.dev.yml
git commit -m "chore(docker): Dockerfile + compose for local dev"
```

---

### Task 5: Cloud Build config + Artifact Registry setup

**Files:**
- Create: `cloudbuild.yaml`

- [ ] **Step 1: Create Artifact Registry repo (one-time, via gcloud)**

```bash
gcloud artifacts repositories create investment-platform-v2 \
  --repository-format=docker \
  --location=asia-east1 \
  --description="Investment Platform v2 images" \
  --project=paul-test-174403
```

Expected: `Created repository [investment-platform-v2]`.

If already exists: ignore "ALREADY_EXISTS" error.

- [ ] **Step 2: Create `cloudbuild.yaml`**

```yaml
options:
  logging: CLOUD_LOGGING_ONLY
  machineType: E2_HIGHCPU_8

steps:
  - id: build
    name: gcr.io/cloud-builders/docker
    args:
      - build
      - --tag=asia-east1-docker.pkg.dev/$PROJECT_ID/investment-platform-v2/app:$SHORT_SHA
      - --tag=asia-east1-docker.pkg.dev/$PROJECT_ID/investment-platform-v2/app:latest
      - .

  - id: push-sha
    name: gcr.io/cloud-builders/docker
    args:
      - push
      - asia-east1-docker.pkg.dev/$PROJECT_ID/investment-platform-v2/app:$SHORT_SHA

  - id: push-latest
    name: gcr.io/cloud-builders/docker
    args:
      - push
      - asia-east1-docker.pkg.dev/$PROJECT_ID/investment-platform-v2/app:latest

images:
  - asia-east1-docker.pkg.dev/$PROJECT_ID/investment-platform-v2/app:$SHORT_SHA
  - asia-east1-docker.pkg.dev/$PROJECT_ID/investment-platform-v2/app:latest
```

- [ ] **Step 3: Submit a build manually to verify**

```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --project=paul-test-174403 \
  --region=asia-east1
```

Expected: Build SUCCESS, image pushed to Artifact Registry.

- [ ] **Step 4: Commit**

```bash
git add cloudbuild.yaml
git commit -m "chore(cloud): Cloud Build config + Artifact Registry"
```

---

### Task 6: First Cloud Run deploy (hello world)

**Files:**
- None (commands only — script reference at end)
- Create: `scripts/deploy.sh`

- [ ] **Step 1: Generate production JWT secret**

```bash
PROD_JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
echo "$PROD_JWT_SECRET"  # save this for reference; we'll put it in Secret Manager
```

- [ ] **Step 2: Store JWT secret in Secret Manager**

```bash
echo -n "$PROD_JWT_SECRET" | gcloud secrets create JWT_SECRET \
  --replication-policy=automatic \
  --data-file=- \
  --project=paul-test-174403
```

If exists: `gcloud secrets versions add JWT_SECRET --data-file=- --project=paul-test-174403`.

- [ ] **Step 3: Create runtime service account**

```bash
gcloud iam service-accounts create cr-investment-v2 \
  --display-name="Cloud Run runtime SA for investment-platform-v2" \
  --project=paul-test-174403
```

Grant Secret Manager access:

```bash
gcloud projects add-iam-policy-binding paul-test-174403 \
  --member=serviceAccount:cr-investment-v2@paul-test-174403.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

- [ ] **Step 4: Create `scripts/deploy.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="paul-test-174403"
REGION="asia-east1"
SERVICE="investment-platform-v2"
IMAGE="asia-east1-docker.pkg.dev/${PROJECT_ID}/investment-platform-v2/app:latest"
SA="cr-investment-v2@${PROJECT_ID}.iam.gserviceaccount.com"

# DB_URL is plaintext for now (will move to Secret Manager in Task 7)
DB_URL_PLACEHOLDER="postgresql+psycopg://placeholder:placeholder@10.140.0.2:5432/investment_v2"

gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${SA}" \
  --allow-unauthenticated \
  --port=8080 \
  --min-instances=0 \
  --max-instances=3 \
  --cpu=1 \
  --memory=512Mi \
  --set-env-vars="ENVIRONMENT=prod,ALLOWED_ORIGINS=https://invest.paulfun.net,GOOGLE_OAUTH_CLIENT_ID=329908581117-0csnfufiij5h5oc6a8qah5uvnm447ppo.apps.googleusercontent.com,DB_URL=${DB_URL_PLACEHOLDER}" \
  --set-secrets="JWT_SECRET=JWT_SECRET:latest"

echo "Deployed. URL:"
gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)'
```

Make executable:

```bash
chmod +x scripts/deploy.sh
```

- [ ] **Step 5: Deploy**

```bash
./scripts/deploy.sh
```

Expected: Service URL printed.

- [ ] **Step 6: Smoke test deployed service**

```bash
SVC_URL=$(gcloud run services describe investment-platform-v2 --region=asia-east1 --project=paul-test-174403 --format='value(status.url)')
curl "${SVC_URL}/healthz"
```

Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 7: Commit**

```bash
git add scripts/deploy.sh
git commit -m "chore(deploy): Cloud Run deploy script + initial deploy"
```


---

## Phase 0b — Database Foundation (Tasks 7-15)

Goal: SQLAlchemy + all models + Alembic + initial migration applied + seed data. After this phase, `python scripts/init_db.py` against the prod DB creates every table and seeds industries.

---

### Task 7: SQLAlchemy engine + session factory

**Files:**
- Create: `app/db.py`
- Create: `tests/unit/test_db.py`

- [ ] **Step 1: Write failing test `tests/unit/test_db.py`**

```python
from sqlalchemy import text

from app.db import get_engine, session_scope


def test_engine_created():
    engine = get_engine()
    assert engine is not None
    assert "postgresql" in str(engine.url)


def test_session_scope_yields_session(monkeypatch):
    # smoke test with SQLite memory to avoid prod DB
    monkeypatch.setattr("app.db._engine", None)
    monkeypatch.setattr(
        "app.config.get_settings",
        lambda: type("S", (), {"db_url": "sqlite:///:memory:", "environment": "test"})(),
    )

    with session_scope() as s:
        result = s.execute(text("SELECT 1 AS x")).scalar_one()
        assert result == 1
```

- [ ] **Step 2: Run test, expect FAIL** — `pytest tests/unit/test_db.py -v`

Expected: `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Implement `app/db.py`**

```python
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            echo=settings.environment == "dev",
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    factory = get_session_factory()
    s = factory()
    try:
        yield s
    finally:
        s.close()
```

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/unit/test_db.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/unit/test_db.py
git commit -m "feat(db): engine + session factory + scope contextmanager"
```

---

### Task 8: Models base — DeclarativeBase + TimestampMixin

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `tests/unit/test_models_base.py`

- [ ] **Step 1: Write failing test `tests/unit/test_models_base.py`**

```python
from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class _Sample(Base, TimestampMixin):
    __tablename__ = "_sample"
    id: Mapped[str] = mapped_column(String, primary_key=True)


def test_timestamp_mixin_has_columns():
    cols = {c.name for c in _Sample.__table__.columns}
    assert "created_at" in cols
    assert "updated_at" in cols
    assert "deleted_at" in cols


def test_now_utc_helper():
    from app.models.base import now_utc

    assert now_utc().tzinfo is not None
    assert (now_utc() - datetime.now(UTC)).total_seconds() < 1
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
pytest tests/unit/test_models_base.py -v
```

Expected: ImportError on `app.models.base`.

- [ ] **Step 3: Create `app/models/__init__.py`** (empty)

- [ ] **Step 4: Implement `app/models/base.py`**

```python
from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Project-wide declarative base."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_models_base.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/models/__init__.py app/models/base.py tests/unit/test_models_base.py
git commit -m "feat(models): Base + TimestampMixin + now_utc"
```

---

### Task 9: User, AllowlistedEmail, RefreshToken models

**Files:**
- Create: `app/models/user.py`
- Create: `app/models/allowlisted_email.py`
- Create: `app/models/refresh_token.py`
- Create: `tests/unit/test_models_auth.py`

- [ ] **Step 1: Write failing test `tests/unit/test_models_auth.py`**

```python
from app.models.allowlisted_email import AllowlistedEmail
from app.models.refresh_token import RefreshToken
from app.models.user import User


def test_user_table_columns():
    cols = {c.name for c in User.__table__.columns}
    expected = {
        "id", "email", "google_sub", "display_name", "slug", "base_currency",
        "role", "password_hash", "is_active", "timezone", "metadata_json",
        "created_at", "updated_at", "deleted_at",
    }
    assert expected.issubset(cols)


def test_allowlisted_email_pk_is_email():
    pk_cols = [c.name for c in AllowlistedEmail.__table__.primary_key.columns]
    assert pk_cols == ["email"]


def test_refresh_token_has_user_fk():
    fks = {fk.column.table.name for c in RefreshToken.__table__.columns for fk in c.foreign_keys}
    assert "users" in fks
```

- [ ] **Step 2: Run test, expect FAIL** — `pytest tests/unit/test_models_auth.py -v`

- [ ] **Step 3: Implement `app/models/user.py`**

```python
import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TWD")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="USER")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Taipei")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
```

- [ ] **Step 4: Implement `app/models/allowlisted_email.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AllowlistedEmail(Base):
    __tablename__ = "allowlisted_emails"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Implement `app/models/refresh_token.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 6: Run test, expect PASS** — `pytest tests/unit/test_models_auth.py -v`

- [ ] **Step 7: Commit**

```bash
git add app/models/user.py app/models/allowlisted_email.py app/models/refresh_token.py tests/unit/test_models_auth.py
git commit -m "feat(models): User + AllowlistedEmail + RefreshToken"
```

---

### Task 10: Industry, Instrument, Account models

**Files:**
- Create: `app/models/industry.py`
- Create: `app/models/instrument.py`
- Create: `app/models/account.py`
- Create: `tests/unit/test_models_entities.py`

- [ ] **Step 1: Write failing test `tests/unit/test_models_entities.py`**

```python
from app.models.account import Account
from app.models.industry import Industry
from app.models.instrument import Instrument


def test_industry_columns():
    cols = {c.name for c in Industry.__table__.columns}
    assert {"id", "code", "name_zh", "name_en", "market_group"}.issubset(cols)


def test_instrument_unique_symbol_market():
    constraints = {c.name for c in Instrument.__table__.constraints if c.name}
    assert any("symbol" in name and "market" in name for name in constraints)


def test_account_belongs_to_user():
    fks = {fk.column.table.name for c in Account.__table__.columns for fk in c.foreign_keys}
    assert "users" in fks
```

- [ ] **Step 2: Run test, expect FAIL** — `pytest tests/unit/test_models_entities.py -v`

- [ ] **Step 3: Implement `app/models/industry.py`**

```python
import uuid
from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Industry(Base):
    __tablename__ = "industries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name_zh: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    market_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
```

- [ ] **Step 4: Implement `app/models/instrument.py`**

```python
import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Instrument(Base, TimestampMixin):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("symbol", "market", name="uq_instruments_symbol_market"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    market: Mapped[str | None] = mapped_column(String(16), nullable=True)
    industry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("industries.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
```

- [ ] **Step 5: Implement `app/models/account.py`**

```python
import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    external_account_no_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
```

- [ ] **Step 6: Run test, expect PASS** — `pytest tests/unit/test_models_entities.py -v`

- [ ] **Step 7: Commit**

```bash
git add app/models/industry.py app/models/instrument.py app/models/account.py tests/unit/test_models_entities.py
git commit -m "feat(models): Industry + Instrument + Account"
```

---

### Task 11: AuditLog model

**Files:**
- Create: `app/models/audit_log.py`
- Create: `tests/unit/test_models_audit.py`

- [ ] **Step 1: Write failing test `tests/unit/test_models_audit.py`**

```python
from app.models.audit_log import AuditLog


def test_audit_log_columns():
    cols = {c.name for c in AuditLog.__table__.columns}
    expected = {
        "id", "occurred_at", "actor_user_id", "actor_type", "action",
        "target_table", "target_id", "before", "after", "request_id", "ip",
    }
    assert expected.issubset(cols)


def test_audit_log_uses_bigint_pk():
    pk = AuditLog.__table__.primary_key.columns
    assert next(iter(pk)).name == "id"
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Implement `app/models/audit_log.py`**

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_table: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
```

- [ ] **Step 4: Run test, expect PASS** — `pytest tests/unit/test_models_audit.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/models/audit_log.py tests/unit/test_models_audit.py
git commit -m "feat(models): AuditLog"
```

---

### Task 12: Alembic init + env.py

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/.gitkeep`

- [ ] **Step 1: Run alembic init to scaffold (then customize)**

```bash
alembic init alembic
```

Note: this creates default `alembic.ini`, `alembic/env.py`, etc. We'll overwrite below.

- [ ] **Step 2: Replace `alembic.ini` with this minimal config**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
file_template = %%(rev)s_%%(slug)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Replace `alembic/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.models.base import Base

# Import all models so metadata is populated.
from app.models import (  # noqa: F401
    account,
    allowlisted_email,
    audit_log,
    industry,
    instrument,
    refresh_token,
    user,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Keep default `alembic/script.py.mako`** (no changes needed)

- [ ] **Step 5: Create empty `alembic/versions/.gitkeep`**

```bash
touch alembic/versions/.gitkeep
```

- [ ] **Step 6: Verify alembic recognizes config**

```bash
DB_URL='postgresql+psycopg://u:p@h/d' JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') GOOGLE_OAUTH_CLIENT_ID=x alembic current
```

Expected: prints "Current revision(s) for postgresql+psycopg://..." (may show empty if DB not connected — that's fine, we just want no config errors).

- [ ] **Step 7: Commit**

```bash
git add alembic.ini alembic/env.py alembic/script.py.mako alembic/versions/.gitkeep
git commit -m "chore(alembic): scaffold + env wired to settings + models"
```

---

### Task 13: Initial migration (all tables)

**Files:**
- Create: `alembic/versions/001_create_initial_schema.py`

- [ ] **Step 1: Auto-generate migration from models**

```bash
DB_URL='postgresql+psycopg://u:p@h/d' JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') GOOGLE_OAUTH_CLIENT_ID=x alembic revision --autogenerate -m "create_initial_schema"
```

The file will be created with a hash prefix. Rename to `001_create_initial_schema.py`:

```bash
ls alembic/versions/
# Rename the auto-generated file to 001_create_initial_schema.py
mv alembic/versions/<generated>_create_initial_schema.py alembic/versions/001_create_initial_schema.py
```

- [ ] **Step 2: Edit `alembic/versions/001_create_initial_schema.py` — set revision id to "001"**

Update the top:

```python
revision: str = "001"
down_revision: str | None = None
branch_labels = None
depends_on = None
```

- [ ] **Step 3: Hand-review the generated `upgrade()` body**

It should include `op.create_table()` for each: `users`, `allowlisted_emails`, `refresh_tokens`, `accounts`, `industries`, `instruments`, `audit_log`. If any are missing, add them by referencing the model definitions.

Add at the **start** of `upgrade()`:

```python
# Enable pgcrypto for gen_random_uuid (optional; we use uuid4 from app side)
op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
```

- [ ] **Step 4: Verify the `downgrade()` drops all tables in reverse order**

```python
def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("instruments")
    op.drop_table("industries")
    op.drop_table("accounts")
    op.drop_table("refresh_tokens")
    op.drop_table("allowlisted_emails")
    op.drop_table("users")
```

- [ ] **Step 5: Test migration locally against docker-compose Postgres**

```bash
docker compose -f docker-compose.dev.yml up -d db
sleep 3
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 001, create_initial_schema`

- [ ] **Step 6: Verify tables exist**

```bash
docker compose -f docker-compose.dev.yml exec db psql -U investment_user -d investment_v2 -c "\dt"
```

Expected: 7 tables listed (including alembic_version).

- [ ] **Step 7: Test downgrade roundtrip**

```bash
alembic downgrade base
alembic upgrade head
```

Expected: both succeed cleanly.

- [ ] **Step 8: Commit**

```bash
git add alembic/versions/001_create_initial_schema.py
git commit -m "feat(db): initial schema migration"
```

---

### Task 14: Industries seed (idempotent SQL fixture)

**Files:**
- Create: `scripts/seed_industries.sql`
- Create: `tests/integration/test_seed_industries.py`

- [ ] **Step 1: Create `scripts/seed_industries.sql`**

```sql
-- Idempotent seed for `industries` table.
-- Safe to run multiple times.

INSERT INTO industries (id, code, name_zh, name_en, market_group, metadata) VALUES
  (gen_random_uuid(), 'SEMICONDUCTOR',     '半導體',       'Semiconductor',         'TECH',     '{}'),
  (gen_random_uuid(), 'TECH_HARDWARE',     '科技硬體',     'Tech Hardware',         'TECH',     '{}'),
  (gen_random_uuid(), 'SOFTWARE',          '軟體',         'Software',              'TECH',     '{}'),
  (gen_random_uuid(), 'INTERNET',          '網際網路',     'Internet',              'TECH',     '{}'),
  (gen_random_uuid(), 'AI_INFRA',          'AI 基礎建設',  'AI Infrastructure',     'TECH',     '{}'),
  (gen_random_uuid(), 'FINANCE',           '金融',         'Finance',               'FINANCE',  '{}'),
  (gen_random_uuid(), 'BANKING',           '銀行',         'Banking',               'FINANCE',  '{}'),
  (gen_random_uuid(), 'INSURANCE',         '保險',         'Insurance',             'FINANCE',  '{}'),
  (gen_random_uuid(), 'REIT',              'REIT',         'REIT',                  'FINANCE',  '{}'),
  (gen_random_uuid(), 'HEALTHCARE',        '醫療保健',     'Healthcare',            'HEALTH',   '{}'),
  (gen_random_uuid(), 'BIOTECH',           '生技',         'Biotechnology',         'HEALTH',   '{}'),
  (gen_random_uuid(), 'PHARMA',            '製藥',         'Pharmaceuticals',       'HEALTH',   '{}'),
  (gen_random_uuid(), 'ENERGY',            '能源',         'Energy',                'ENERGY',   '{}'),
  (gen_random_uuid(), 'UTILITIES',         '公用事業',     'Utilities',             'ENERGY',   '{}'),
  (gen_random_uuid(), 'INDUSTRIALS',       '工業',         'Industrials',           'INDUSTRY', '{}'),
  (gen_random_uuid(), 'MATERIALS',         '原物料',       'Materials',             'INDUSTRY', '{}'),
  (gen_random_uuid(), 'CONSUMER_DISC',     '非必需消費',   'Consumer Discretionary','CONSUMER', '{}'),
  (gen_random_uuid(), 'CONSUMER_STAPLES',  '必需消費',     'Consumer Staples',      'CONSUMER', '{}'),
  (gen_random_uuid(), 'AUTO',              '汽車',         'Automotive',            'CONSUMER', '{}'),
  (gen_random_uuid(), 'TELECOM',           '電信',         'Telecommunications',    'TELECOM',  '{}'),
  (gen_random_uuid(), 'MEDIA',             '媒體娛樂',     'Media & Entertainment', 'TELECOM',  '{}'),
  (gen_random_uuid(), 'REAL_ESTATE',       '房地產',       'Real Estate',           'RE',       '{}'),
  (gen_random_uuid(), 'TRANSPORTATION',    '運輸',         'Transportation',        'INDUSTRY', '{}'),
  (gen_random_uuid(), 'AEROSPACE',         '航太國防',     'Aerospace & Defense',   'INDUSTRY', '{}'),
  (gen_random_uuid(), 'CRYPTO_NATIVE',     '加密原生',     'Crypto Native',         'CRYPTO',   '{}'),
  (gen_random_uuid(), 'GOLD_PRECIOUS',     '黃金與貴金屬', 'Gold & Precious Metals','COMMODITY','{}'),
  (gen_random_uuid(), 'FX',                '外匯',         'Foreign Exchange',      'FX',       '{}'),
  (gen_random_uuid(), 'GOVT_BOND',         '政府公債',     'Government Bonds',      'BOND',     '{}'),
  (gen_random_uuid(), 'CORP_BOND',         '公司債',       'Corporate Bonds',       'BOND',     '{}'),
  (gen_random_uuid(), 'CASH_EQUIV',        '現金等價物',   'Cash & Equivalents',    'CASH',     '{}')
ON CONFLICT (code) DO NOTHING;
```

- [ ] **Step 2: Write failing test `tests/integration/test_seed_industries.py`**

This test needs a real DB. Skip if no DB URL set.

```python
import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db import get_engine

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Integration test requires INTEGRATION_DB_URL env var",
)


def _run_seed(db_url: str):
    subprocess.run(
        ["psql", db_url, "-f", str(Path("scripts/seed_industries.sql"))],
        check=True,
    )


def test_seed_idempotent(monkeypatch):
    db_url = os.environ["INTEGRATION_DB_URL"]
    monkeypatch.setenv("DB_URL", db_url)

    _run_seed(db_url)
    _run_seed(db_url)  # second run should not duplicate

    engine = get_engine()
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM industries")).scalar_one()
        assert n >= 30
```

- [ ] **Step 3: Run seed against docker-compose DB to verify**

```bash
docker compose -f docker-compose.dev.yml exec -T db psql -U investment_user -d investment_v2 < scripts/seed_industries.sql
docker compose -f docker-compose.dev.yml exec db psql -U investment_user -d investment_v2 -c "SELECT COUNT(*) FROM industries;"
```

Expected: count >= 30.

- [ ] **Step 4: Run again to verify idempotency**

```bash
docker compose -f docker-compose.dev.yml exec -T db psql -U investment_user -d investment_v2 < scripts/seed_industries.sql
docker compose -f docker-compose.dev.yml exec db psql -U investment_user -d investment_v2 -c "SELECT COUNT(*) FROM industries;"
```

Expected: same count (no duplicates).

- [ ] **Step 5: Run integration test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_seed_industries.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/seed_industries.sql tests/integration/test_seed_industries.py
git commit -m "feat(seed): industries fixture (30 entries, idempotent)"
```

---

### Task 15: init_db.py script + first admin user

**Files:**
- Create: `scripts/init_db.py`
- Create: `tests/integration/test_init_db.py`

- [ ] **Step 1: Write failing test `tests/integration/test_init_db.py`**

```python
import os
import subprocess

import pytest
from sqlalchemy import text

from app.db import get_engine

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Integration test requires INTEGRATION_DB_URL env var",
)


def test_init_db_creates_admin(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    monkeypatch.setenv("FIRST_ADMIN_EMAIL", "pin0513@gmail.com")

    subprocess.run(
        ["python", "scripts/init_db.py"],
        check=True,
        env={**os.environ, "FIRST_ADMIN_EMAIL": "pin0513@gmail.com"},
    )

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT email, role, slug FROM users WHERE email = :e"),
            {"e": "pin0513@gmail.com"},
        ).first()
        assert row is not None
        assert row.role == "ADMIN"
        assert row.slug  # non-empty
```

- [ ] **Step 2: Run test, expect FAIL** (script doesn't exist)

- [ ] **Step 3: Implement `scripts/init_db.py`**

```python
"""
Idempotent DB initialization:
  1. Ensure pgcrypto extension
  2. Run alembic upgrade head
  3. Seed industries
  4. Create first admin user from FIRST_ADMIN_EMAIL
"""

from __future__ import annotations

import logging
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

from app.config import get_settings
from app.db import session_scope
from app.models.allowlisted_email import AllowlistedEmail
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("init_db")


def run_alembic() -> None:
    log.info("Running alembic upgrade head...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"], capture_output=True, text=True
    )
    if result.returncode != 0:
        log.error("alembic failed: %s", result.stderr)
        sys.exit(1)
    log.info("alembic OK")


def run_seed_industries() -> None:
    seed_file = Path(__file__).parent / "seed_industries.sql"
    sql = seed_file.read_text()
    with session_scope() as s:
        s.execute(text(sql))
    log.info("Industries seed OK")


def slugify_email(email: str) -> str:
    return email.split("@", 1)[0].lower().replace(".", "_").replace("+", "_")


def ensure_first_admin() -> None:
    settings = get_settings()
    email = settings.first_admin_email
    if not email:
        log.warning("FIRST_ADMIN_EMAIL not set; skipping admin creation")
        return

    with session_scope() as s:
        existing = s.query(User).filter(User.email == email).one_or_none()
        if existing:
            log.info("Admin user %s already exists", email)
            return

        slug = slugify_email(email)
        user = User(
            id=uuid.uuid4(),
            email=email,
            slug=slug,
            display_name=email.split("@")[0],
            role="ADMIN",
            is_active=True,
            base_currency="TWD",
            timezone="Asia/Taipei",
        )
        s.add(user)
        s.flush()

        # Add to allowlist
        s.merge(AllowlistedEmail(email=email, invited_by=user.id, notes="auto-seeded admin"))

        log.info("Created admin user %s (slug=%s)", email, slug)


def main() -> None:
    log.info("DB URL: %s", get_settings().db_url[:40] + "...")
    run_alembic()
    run_seed_industries()
    ensure_first_admin()
    log.info("init_db complete")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run init_db against docker-compose DB**

```bash
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
FIRST_ADMIN_EMAIL=pin0513@gmail.com \
python scripts/init_db.py
```

Expected: logs "alembic OK", "Industries seed OK", "Created admin user pin0513@gmail.com".

- [ ] **Step 5: Run again to verify idempotency**

```bash
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
FIRST_ADMIN_EMAIL=pin0513@gmail.com \
python scripts/init_db.py
```

Expected: logs "Admin user pin0513@gmail.com already exists" (no duplicate).

- [ ] **Step 6: Run integration test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_init_db.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/init_db.py tests/integration/test_init_db.py
git commit -m "feat(init): init_db script (migrate + seed + first admin)"
```


---

## Phase 0c — Auth (Tasks 16-23)

Goal: Working JWT auth — POST /auth/login, /auth/refresh, /auth/logout, /auth/me, /auth/google. Three auth flows (browser cookie, CLI bearer, service JWT) all verified by one shared `get_current_user` dependency.

---

### Task 16: Security utilities (JWT + bcrypt)

**Files:**
- Create: `app/security.py`
- Create: `tests/unit/test_security.py`

- [ ] **Step 1: Write failing test `tests/unit/test_security.py`**

```python
import uuid

import pytest
from jose import JWTError

from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_refresh_token,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    plain = "super-secret-pw"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(
        subject=str(user_id), email="x@y.z", role="USER", scope="user"
    )
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["email"] == "x@y.z"
    assert claims["role"] == "USER"
    assert claims["scope"] == "user"
    assert "jti" in claims


def test_access_token_expiry_rejected():
    token = create_access_token(
        subject="x", email="x@y.z", role="USER", scope="user", expires_in_minutes=-1
    )
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_refresh_token_format():
    raw = new_refresh_token()
    assert len(raw) >= 32

    h = hash_refresh_token(raw)
    assert h != raw
    assert hash_refresh_token(raw) == h  # deterministic
```

- [ ] **Step 2: Run test, expect FAIL** — `pytest tests/unit/test_security.py -v`

- [ ] **Step 3: Implement `app/security.py`**

```python
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(
    *,
    subject: str,
    email: str,
    role: str,
    scope: str = "user",
    expires_in_minutes: int | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    minutes = expires_in_minutes if expires_in_minutes is not None else settings.access_token_minutes
    claims: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def new_refresh_token() -> str:
    """Return a raw refresh token (URL-safe random)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    """SHA256 hash for DB storage."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test, expect PASS** — `pytest tests/unit/test_security.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/unit/test_security.py
git commit -m "feat(security): JWT encode/decode + bcrypt + refresh hashing"
```

---

### Task 17: Pydantic auth schemas

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/auth.py`
- Create: `tests/unit/test_schemas_auth.py`

- [ ] **Step 1: Write failing test `tests/unit/test_schemas_auth.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)


def test_login_request_validates_email():
    LoginRequest(email="x@y.z", password="abc12345")
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="abc12345")


def test_login_request_min_password_len():
    with pytest.raises(ValidationError):
        LoginRequest(email="x@y.z", password="abc")


def test_token_response_shape():
    t = TokenResponse(access_token="a", refresh_token="b", expires_in=900)
    assert t.token_type == "Bearer"


def test_refresh_request_requires_token():
    with pytest.raises(ValidationError):
        RefreshRequest(refresh_token="")


def test_google_login_request():
    GoogleLoginRequest(id_token="abc")


def test_user_out_fields():
    import uuid

    UserOut(
        id=uuid.uuid4(),
        email="x@y.z",
        slug="x",
        role="USER",
        base_currency="TWD",
        display_name=None,
    )
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Create `app/schemas/__init__.py`** (empty)

- [ ] **Step 4: Implement `app/schemas/auth.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="access token TTL in seconds")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    slug: str
    role: str
    base_currency: str
    display_name: str | None
```

- [ ] **Step 5: Run test, expect PASS** — `pytest tests/unit/test_schemas_auth.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/schemas/ tests/unit/test_schemas_auth.py
git commit -m "feat(schemas): auth schemas (login, refresh, token, user)"
```

---

### Task 18: Auth repositories

**Files:**
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/user.py`
- Create: `app/repositories/refresh_token.py`
- Create: `app/repositories/allowlisted_email.py`
- Create: `tests/integration/test_repositories_auth.py`

- [ ] **Step 1: Write failing integration test `tests/integration/test_repositories_auth.py`**

```python
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db import session_scope
from app.models.user import User
from app.repositories.allowlisted_email import AllowlistedEmailRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def fresh_user(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"test-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"test{uuid.uuid4().hex[:8]}",
            role="USER",
        )
        s.add(u)
        s.flush()
        yield u
        s.rollback()


def test_user_repository_get_by_email(monkeypatch, fresh_user):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    with session_scope() as s:
        repo = UserRepository(s)
        found = repo.get_by_email(fresh_user.email)
        assert found is not None
        assert found.id == fresh_user.id


def test_refresh_token_repository_create_and_revoke(monkeypatch, fresh_user):
    with session_scope() as s:
        repo = RefreshTokenRepository(s)
        rt = repo.create(
            user_id=fresh_user.id,
            token_hash="hash1",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        assert rt.id

        repo.revoke(rt.id)
        s.flush()
        s.refresh(rt)
        assert rt.revoked_at is not None


def test_allowlist_repository_check(monkeypatch):
    with session_scope() as s:
        repo = AllowlistedEmailRepository(s)
        # admin is auto-seeded in init_db
        assert repo.is_allowed("pin0513@gmail.com") is True
        assert repo.is_allowed("not-allowed@x.z") is False
```

- [ ] **Step 2: Create `app/repositories/__init__.py`** (empty)

- [ ] **Step 3: Implement `app/repositories/user.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session):
        self.s = session

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.s.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        return self.s.execute(stmt).scalar_one_or_none()

    def get_by_google_sub(self, sub: str) -> User | None:
        stmt = select(User).where(User.google_sub == sub, User.deleted_at.is_(None))
        return self.s.execute(stmt).scalar_one_or_none()

    def create(self, user: User) -> User:
        self.s.add(user)
        self.s.flush()
        return user
```

- [ ] **Step 4: Implement `app/repositories/refresh_token.py`**

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: Session):
        self.s = session

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.s.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> RefreshToken:
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
        self.s.add(rt)
        self.s.flush()
        return rt

    def revoke(self, token_id: uuid.UUID) -> None:
        rt = self.s.get(RefreshToken, token_id)
        if rt:
            rt.revoked_at = datetime.now(UTC)

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
        for rt in self.s.execute(stmt).scalars():
            rt.revoked_at = datetime.now(UTC)
```

- [ ] **Step 5: Implement `app/repositories/allowlisted_email.py`**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.allowlisted_email import AllowlistedEmail


class AllowlistedEmailRepository:
    def __init__(self, session: Session):
        self.s = session

    def is_allowed(self, email: str) -> bool:
        return self.s.get(AllowlistedEmail, email) is not None

    def add(self, email: str, invited_by, notes: str | None = None) -> AllowlistedEmail:
        entry = AllowlistedEmail(email=email, invited_by=invited_by, notes=notes)
        self.s.merge(entry)
        return entry
```

- [ ] **Step 6: Run integration test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_repositories_auth.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/repositories/ tests/integration/test_repositories_auth.py
git commit -m "feat(repo): UserRepository + RefreshTokenRepository + AllowlistedEmailRepository"
```

---

### Task 19: Auth service (login, refresh, logout)

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/auth.py`
- Create: `tests/integration/test_auth_service.py`

- [ ] **Step 1: Write failing integration test `tests/integration/test_auth_service.py`**

```python
import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password
from app.services.auth import AuthService, InvalidCredentialsError

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def user_with_password():
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"svc-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"svc{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        yield u


def test_login_returns_tokens(monkeypatch, user_with_password):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    with session_scope() as s:
        svc = AuthService(s)
        result = svc.login_password(email=user_with_password.email, password="good-password")
        assert result.access_token
        assert result.refresh_token
        assert result.expires_in > 0


def test_login_bad_password_raises(monkeypatch, user_with_password):
    with session_scope() as s:
        svc = AuthService(s)
        with pytest.raises(InvalidCredentialsError):
            svc.login_password(email=user_with_password.email, password="wrong")


def test_refresh_rotates_token(monkeypatch, user_with_password):
    with session_scope() as s:
        svc = AuthService(s)
        first = svc.login_password(email=user_with_password.email, password="good-password")

        s.commit()  # persist first refresh token

    with session_scope() as s:
        svc = AuthService(s)
        second = svc.refresh(first.refresh_token)
        assert second.refresh_token != first.refresh_token
        assert second.access_token != first.access_token
```

- [ ] **Step 2: Create `app/services/__init__.py`** (empty)

- [ ] **Step 3: Implement `app/services/auth.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(self, session: Session):
        self.s = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.settings = get_settings()

    def _issue_pair(self, user, user_agent: str | None = None, ip: str | None = None) -> TokenPair:
        access = create_access_token(
            subject=str(user.id),
            email=user.email,
            role=user.role,
            scope="user" if user.role != "SERVICE" else "service",
        )
        raw_refresh = new_refresh_token()
        expires = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days)
        self.refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=expires,
            user_agent=user_agent,
            ip=ip,
        )
        return TokenPair(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=self.settings.access_token_minutes * 60,
        )

    def login_password(
        self, *, email: str, password: str, user_agent: str | None = None, ip: str | None = None
    ) -> TokenPair:
        user = self.users.get_by_email(email)
        if user is None or not user.is_active or not user.password_hash:
            raise InvalidCredentialsError("Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")
        return self._issue_pair(user, user_agent=user_agent, ip=ip)

    def login_google(
        self, *, user, user_agent: str | None = None, ip: str | None = None
    ) -> TokenPair:
        """Caller is responsible for verifying the Google id_token."""
        if not user.is_active:
            raise InvalidCredentialsError("User inactive")
        return self._issue_pair(user, user_agent=user_agent, ip=ip)

    def refresh(self, raw_refresh: str) -> TokenPair:
        h = hash_refresh_token(raw_refresh)
        rt = self.refresh_tokens.get_by_hash(h)
        if rt is None or rt.revoked_at is not None:
            raise InvalidRefreshTokenError("Refresh token invalid or revoked")
        if rt.expires_at < datetime.now(UTC):
            raise InvalidRefreshTokenError("Refresh token expired")

        user = self.users.get_by_id(rt.user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError("User inactive")

        # Rotate: revoke old, issue new
        self.refresh_tokens.revoke(rt.id)
        return self._issue_pair(user)

    def logout(self, raw_refresh: str) -> None:
        h = hash_refresh_token(raw_refresh)
        rt = self.refresh_tokens.get_by_hash(h)
        if rt is not None:
            self.refresh_tokens.revoke(rt.id)
```

- [ ] **Step 4: Run integration test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_auth_service.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/auth.py app/services/__init__.py tests/integration/test_auth_service.py
git commit -m "feat(auth): AuthService — login + refresh + logout with rotation"
```

---

### Task 20: Google ID token verification

**Files:**
- Modify: `app/services/auth.py:1-15` (add Google verifier)
- Create: `tests/unit/test_google_verify.py`

- [ ] **Step 1: Write failing test `tests/unit/test_google_verify.py`**

```python
from unittest.mock import patch

import pytest

from app.services.auth import GoogleIdTokenVerifier, GoogleVerifyError


def test_verify_returns_payload_on_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client.apps.googleusercontent.com")
    fake_payload = {
        "sub": "1234567890",
        "email": "x@y.z",
        "email_verified": True,
        "name": "X Y",
        "aud": "client.apps.googleusercontent.com",
    }
    with patch("app.services.auth.id_token.verify_oauth2_token", return_value=fake_payload):
        v = GoogleIdTokenVerifier()
        out = v.verify("fake.id.token")
        assert out["email"] == "x@y.z"
        assert out["sub"] == "1234567890"


def test_verify_rejects_unverified_email(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client.apps.googleusercontent.com")
    fake_payload = {
        "sub": "1234567890",
        "email": "x@y.z",
        "email_verified": False,
        "aud": "client.apps.googleusercontent.com",
    }
    with patch("app.services.auth.id_token.verify_oauth2_token", return_value=fake_payload):
        v = GoogleIdTokenVerifier()
        with pytest.raises(GoogleVerifyError):
            v.verify("fake.id.token")
```

- [ ] **Step 2: Add to `app/services/auth.py`** (append at top after existing imports)

Modify imports section:

```python
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
```

Add classes near the bottom of the file:

```python
class GoogleVerifyError(Exception):
    pass


class GoogleIdTokenVerifier:
    def __init__(self):
        self.settings = get_settings()

    def verify(self, raw_token: str) -> dict:
        try:
            payload = id_token.verify_oauth2_token(
                raw_token,
                google_requests.Request(),
                self.settings.google_oauth_client_id,
            )
        except Exception as e:
            raise GoogleVerifyError(f"Token verification failed: {e}") from e

        if not payload.get("email_verified"):
            raise GoogleVerifyError("Email not verified by Google")

        return payload
```

- [ ] **Step 3: Run test, expect PASS** — `pytest tests/unit/test_google_verify.py -v`

- [ ] **Step 4: Commit**

```bash
git add app/services/auth.py tests/unit/test_google_verify.py
git commit -m "feat(auth): GoogleIdTokenVerifier"
```

---

### Task 21: get_current_user dependency

**Files:**
- Create: `app/dependencies.py`
- Create: `tests/unit/test_dependencies.py`

- [ ] **Step 1: Write failing test `tests/unit/test_dependencies.py`**

```python
import uuid

import pytest
from fastapi import HTTPException

from app.dependencies import _parse_auth_token


def test_parse_bearer_header():
    sub = uuid.uuid4()
    from app.security import create_access_token

    token = create_access_token(subject=str(sub), email="x@y.z", role="USER")
    claims = _parse_auth_token(f"Bearer {token}", cookie=None)
    assert claims["sub"] == str(sub)


def test_parse_cookie_when_no_header():
    sub = uuid.uuid4()
    from app.security import create_access_token

    token = create_access_token(subject=str(sub), email="x@y.z", role="USER")
    claims = _parse_auth_token(None, cookie=token)
    assert claims["sub"] == str(sub)


def test_no_credentials_raises_401():
    with pytest.raises(HTTPException) as ei:
        _parse_auth_token(None, None)
    assert ei.value.status_code == 401


def test_malformed_header_raises_401():
    with pytest.raises(HTTPException) as ei:
        _parse_auth_token("NotBearer xxx", None)
    assert ei.value.status_code == 401
```

- [ ] **Step 2: Implement `app/dependencies.py`**

```python
from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.security import decode_access_token


def _parse_auth_token(
    authorization: str | None, cookie: str | None
) -> dict:
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed Authorization header",
            )
        token = authorization[len("Bearer "):]
    elif cookie:
        token = cookie
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
        )

    try:
        return decode_access_token(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: Annotated[str | None, Cookie(alias="__session")] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User:
    claims = _parse_auth_token(authorization, session)

    user_id_str = claims.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Token missing subject")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid subject") from e

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_service(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "SERVICE":
        raise HTTPException(status_code=403, detail="Service role required")
    return user
```

- [ ] **Step 3: Run unit test, expect PASS** — `pytest tests/unit/test_dependencies.py -v`

- [ ] **Step 4: Commit**

```bash
git add app/dependencies.py tests/unit/test_dependencies.py
git commit -m "feat(deps): get_current_user (Bearer + cookie) + role gates"
```

---

### Task 22: Auth router (login, refresh, logout, me, google)

**Files:**
- Create: `app/routers/auth.py`
- Modify: `app/main.py` (mount auth router)
- Create: `tests/integration/test_auth_api.py`

- [ ] **Step 1: Write failing test `tests/integration/test_auth_api.py`**

```python
import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def user_with_pw():
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"api-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"api{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        yield u


def test_login_endpoint(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "Bearer"


def test_me_endpoint(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    access = r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["email"] == user_with_pw.email


def test_refresh_endpoint(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    refresh = r.json()["refresh_token"]

    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_logout_revokes(client, user_with_pw):
    r = client.post(
        "/auth/login",
        json={"email": user_with_pw.email, "password": "good-password"},
    )
    refresh = r.json()["refresh_token"]

    r = client.post("/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 204

    # Reuse should now fail
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401
```

- [ ] **Step 2: Implement `app/routers/auth.py`**

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.allowlisted_email import AllowlistedEmailRepository
from app.repositories.user import UserRepository
from app.schemas.auth import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth import (
    AuthService,
    GoogleIdTokenVerifier,
    GoogleVerifyError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(email: str) -> str:
    return email.split("@", 1)[0].lower().replace(".", "_").replace("+", "_")


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    svc = AuthService(db)
    try:
        pair = svc.login_password(
            email=body.email,
            password=body.password,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    db.commit()
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/google", response_model=TokenResponse)
def login_google(
    body: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    verifier = GoogleIdTokenVerifier()
    try:
        payload = verifier.verify(body.id_token)
    except GoogleVerifyError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    users = UserRepository(db)
    allowlist = AllowlistedEmailRepository(db)
    email = payload["email"]

    user = users.get_by_google_sub(payload["sub"]) or users.get_by_email(email)

    if user is None:
        if not allowlist.is_allowed(email):
            raise HTTPException(status_code=403, detail="Email not allowed")
        user = User(
            id=uuid.uuid4(),
            email=email,
            google_sub=payload["sub"],
            display_name=payload.get("name"),
            slug=_slugify(email),
            role="USER",
            is_active=True,
        )
        users.create(user)
    elif user.google_sub is None:
        user.google_sub = payload["sub"]
        db.flush()

    svc = AuthService(db)
    try:
        pair = svc.login_google(
            user=user,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    db.commit()

    # Also set session cookie for browser
    response.set_cookie(
        key="__session",
        value=pair.access_token,
        max_age=pair.expires_in,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    try:
        pair = svc.refresh(body.refresh_token)
    except InvalidRefreshTokenError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    db.commit()
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    svc = AuthService(db)
    svc.logout(body.refresh_token)
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut.model_validate(user)
```

- [ ] **Step 3: Modify `app/main.py` — mount auth router**

Edit `app/main.py`, in `create_app()` add after `app.include_router(health.router)`:

```python
from app.routers import auth as auth_router
...
app.include_router(auth_router.router)
```

Or modify the existing import line near the top:

```python
from app.routers import auth as auth_router, health
```

And then in `create_app()`:

```python
app.include_router(health.router)
app.include_router(auth_router.router)
```

- [ ] **Step 4: Run integration test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_auth_api.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/routers/auth.py app/main.py tests/integration/test_auth_api.py
git commit -m "feat(auth): /auth/login + /auth/refresh + /auth/logout + /auth/me + /auth/google"
```

---

### Task 23: Audit log writer + request_id middleware

**Files:**
- Create: `app/audit.py`
- Create: `tests/unit/test_audit.py`
- Modify: `app/main.py` (add request_id middleware)

- [ ] **Step 1: Write failing test `tests/unit/test_audit.py`**

```python
import os
import uuid

import pytest
from sqlalchemy import select

from app.audit import AuditWriter
from app.db import session_scope
from app.models.audit_log import AuditLog

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


def test_audit_writer_writes_row(monkeypatch):
    monkeypatch.setenv("DB_URL", os.environ["INTEGRATION_DB_URL"])
    request_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    with session_scope() as s:
        writer = AuditWriter(s, request_id=request_id, actor_user_id=actor_id, ip="1.2.3.4")
        writer.record(
            action="INSERT",
            target_table="accounts",
            target_id=uuid.uuid4(),
            before=None,
            after={"name": "test"},
        )

    with session_scope() as s:
        rows = s.execute(
            select(AuditLog).where(AuditLog.request_id == request_id)
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.action == "INSERT"
        assert row.target_table == "accounts"
        assert row.after == {"name": "test"}
```

- [ ] **Step 2: Implement `app/audit.py`**

```python
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditWriter:
    def __init__(
        self,
        session: Session,
        *,
        request_id: uuid.UUID | None,
        actor_user_id: uuid.UUID | None,
        actor_type: str = "USER",
        ip: str | None = None,
    ):
        self.s = session
        self.request_id = request_id
        self.actor_user_id = actor_user_id
        self.actor_type = actor_type
        self.ip = ip

    def record(
        self,
        *,
        action: str,
        target_table: str | None = None,
        target_id: uuid.UUID | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        entry = AuditLog(
            actor_user_id=self.actor_user_id,
            actor_type=self.actor_type,
            action=action,
            target_table=target_table,
            target_id=target_id,
            before=before,
            after=after,
            request_id=self.request_id,
            ip=self.ip,
        )
        self.s.add(entry)
```

- [ ] **Step 3: Add request_id middleware in `app/main.py`**

Add after `app.add_middleware(CORSMiddleware, ...)`:

```python
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response


app.add_middleware(RequestIdMiddleware)
```

Note: place above where you `include_router` calls.

- [ ] **Step 4: Run integration test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/unit/test_audit.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/audit.py app/main.py tests/unit/test_audit.py
git commit -m "feat(audit): AuditWriter + request_id middleware"
```


---

## Phase 0d — CRUD endpoints (Tasks 24-27)

Goal: Working `/api/v1/accounts` and `/api/v1/instruments` with full CRUD, plus admin invite endpoint. All mutations write audit_log.

---

### Task 24: Error handler + error schema

**Files:**
- Create: `app/errors.py`
- Create: `app/schemas/errors.py`
- Modify: `app/main.py` (register handlers)
- Create: `tests/integration/test_errors.py`

- [ ] **Step 1: Write failing test `tests/integration/test_errors.py`**

```python
def test_404_returns_structured_error(client):
    r = client.get("/api/v1/nonexistent-route")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body["error"]
```

- [ ] **Step 2: Implement `app/schemas/errors.py`**

```python
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
```

- [ ] **Step 3: Implement `app/errors.py`**

```python
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBody, ErrorResponse

log = logging.getLogger("errors")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _build(code: str, message: str, request_id: str | None, details: dict | None = None) -> dict:
    return ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details)
    ).model_dump(mode="json")


async def http_exception_handler(request: Request, exc: HTTPException):
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE",
    }
    code = code_map.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_build(code, str(exc.detail), _request_id(request)),
    )


async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_build(
            "VALIDATION_ERROR",
            "Request body validation failed",
            _request_id(request),
            details={"errors": exc.errors()},
        ),
    )


async def unhandled_handler(request: Request, exc: Exception):
    log.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_build("INTERNAL_ERROR", "Internal server error", _request_id(request)),
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(Exception, unhandled_handler)
```

- [ ] **Step 4: Modify `app/main.py`** — register handlers in `create_app()`

Add import:

```python
from app import errors
```

Inside `create_app()` after middleware:

```python
errors.install(app)
```

- [ ] **Step 5: Run test, expect PASS** — `pytest tests/integration/test_errors.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/errors.py app/schemas/errors.py app/main.py tests/integration/test_errors.py
git commit -m "feat(errors): structured error responses + global handlers"
```

---

### Task 25: Account schemas + repository + service + router

**Files:**
- Create: `app/schemas/account.py`
- Create: `app/repositories/account.py`
- Create: `app/services/account.py`
- Create: `app/routers/accounts.py`
- Modify: `app/main.py` (mount /api/v1/accounts)
- Create: `tests/integration/test_accounts_api.py`

- [ ] **Step 1: Implement `app/schemas/account.py`**

```python
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    account_type: str = Field(min_length=1, max_length=32)
    provider: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    external_account_no_last4: str | None = Field(default=None, min_length=1, max_length=4)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    external_account_no_last4: str | None = Field(default=None, min_length=1, max_length=4)
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    account_type: str
    provider: str | None
    currency: str | None
    external_account_no_last4: str | None
    is_active: bool
    metadata: dict[str, Any] = Field(alias="metadata_json")
```

- [ ] **Step 2: Implement `app/repositories/account.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account


class AccountRepository:
    def __init__(self, session: Session):
        self.s = session

    def list_for_user(self, user_id: uuid.UUID, include_deleted: bool = False) -> list[Account]:
        stmt = select(Account).where(Account.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Account.deleted_at.is_(None))
        return list(self.s.execute(stmt).scalars())

    def get_for_user(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account | None:
        stmt = select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.deleted_at.is_(None),
        )
        return self.s.execute(stmt).scalar_one_or_none()

    def create(self, account: Account) -> Account:
        self.s.add(account)
        self.s.flush()
        return account

    def soft_delete(self, account: Account) -> None:
        from datetime import UTC, datetime

        account.deleted_at = datetime.now(UTC)
```

- [ ] **Step 3: Implement `app/services/account.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.account import Account
from app.repositories.account import AccountRepository
from app.schemas.account import AccountCreate, AccountUpdate


class AccountNotFoundError(Exception):
    pass


class AccountService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = AccountRepository(session)
        self.audit = audit

    def list(self, user_id: uuid.UUID) -> list[Account]:
        return self.repo.list_for_user(user_id)

    def get(self, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        acc = self.repo.get_for_user(user_id, account_id)
        if acc is None:
            raise AccountNotFoundError(str(account_id))
        return acc

    def create(self, user_id: uuid.UUID, payload: AccountCreate) -> Account:
        acc = Account(
            id=uuid.uuid4(),
            user_id=user_id,
            name=payload.name,
            account_type=payload.account_type,
            provider=payload.provider,
            currency=payload.currency,
            external_account_no_last4=payload.external_account_no_last4,
            metadata_json=payload.metadata,
            is_active=True,
        )
        self.repo.create(acc)
        self.audit.record(
            action="INSERT",
            target_table="accounts",
            target_id=acc.id,
            after={
                "name": acc.name,
                "account_type": acc.account_type,
                "provider": acc.provider,
                "currency": acc.currency,
            },
        )
        return acc

    def update(self, user_id: uuid.UUID, account_id: uuid.UUID, payload: AccountUpdate) -> Account:
        acc = self.get(user_id, account_id)
        before = {
            "name": acc.name, "provider": acc.provider, "currency": acc.currency,
            "external_account_no_last4": acc.external_account_no_last4,
            "is_active": acc.is_active, "metadata": dict(acc.metadata_json or {}),
        }
        if payload.name is not None: acc.name = payload.name
        if payload.provider is not None: acc.provider = payload.provider
        if payload.currency is not None: acc.currency = payload.currency
        if payload.external_account_no_last4 is not None:
            acc.external_account_no_last4 = payload.external_account_no_last4
        if payload.is_active is not None: acc.is_active = payload.is_active
        if payload.metadata is not None: acc.metadata_json = payload.metadata

        self.audit.record(
            action="UPDATE",
            target_table="accounts",
            target_id=acc.id,
            before=before,
            after={
                "name": acc.name, "provider": acc.provider, "currency": acc.currency,
                "external_account_no_last4": acc.external_account_no_last4,
                "is_active": acc.is_active, "metadata": dict(acc.metadata_json or {}),
            },
        )
        return acc

    def delete(self, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        acc = self.get(user_id, account_id)
        self.repo.soft_delete(acc)
        self.audit.record(
            action="DELETE",
            target_table="accounts",
            target_id=acc.id,
            before={"name": acc.name},
        )
```

- [ ] **Step 4: Implement `app/routers/accounts.py`**

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.services.account import AccountNotFoundError, AccountService

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


def _audit_writer(request: Request, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None)
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
        ip=request.client.host if request.client else None,
    )


@router.get("", response_model=list[AccountOut])
def list_accounts(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    # Audit reads not needed; service.list does not record
    audit = _audit_writer(None, user, db)  # placeholder; not used in list
    svc = AccountService(db, audit)
    return [AccountOut.model_validate(a) for a in svc.list(user.id)]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    payload: AccountCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = AccountService(db, _audit_writer(request, user, db))
    acc = svc.create(user.id, payload)
    db.commit()
    return AccountOut.model_validate(acc)


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = AccountService(db, audit)
    try:
        acc = svc.get(user.id, account_id)
    except AccountNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return AccountOut.model_validate(acc)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = AccountService(db, _audit_writer(request, user, db))
    try:
        acc = svc.update(user.id, account_id, payload)
    except AccountNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    return AccountOut.model_validate(acc)


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: uuid.UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = AccountService(db, _audit_writer(request, user, db))
    try:
        svc.delete(user.id, account_id)
    except AccountNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
```

- [ ] **Step 5: Modify `app/main.py`** — mount accounts router

Add import:

```python
from app.routers import accounts
```

In `create_app()`:

```python
app.include_router(accounts.router)
```

- [ ] **Step 6: Write integration test `tests/integration/test_accounts_api.py`**

```python
import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def user_token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"acc-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"acc{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email

    r = client.post("/auth/login", json={"email": email, "password": "good-password"})
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_account(client, user_token):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "永豐證券", "account_type": "BROKER_STOCK", "currency": "TWD"},
        headers=_h(user_token),
    )
    assert r.status_code == 201
    acc_id = r.json()["id"]

    r = client.get("/api/v1/accounts", headers=_h(user_token))
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert "永豐證券" in names


def test_get_and_update_account(client, user_token):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "玉山", "account_type": "BANK", "currency": "TWD"},
        headers=_h(user_token),
    )
    acc_id = r.json()["id"]

    r = client.patch(
        f"/api/v1/accounts/{acc_id}",
        json={"name": "玉山銀行"},
        headers=_h(user_token),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "玉山銀行"


def test_delete_account_returns_204(client, user_token):
    r = client.post(
        "/api/v1/accounts",
        json={"name": "Binance", "account_type": "CRYPTO_EXCHANGE"},
        headers=_h(user_token),
    )
    acc_id = r.json()["id"]

    r = client.delete(f"/api/v1/accounts/{acc_id}", headers=_h(user_token))
    assert r.status_code == 204

    r = client.get(f"/api/v1/accounts/{acc_id}", headers=_h(user_token))
    assert r.status_code == 404


def test_unauthorized_returns_401(client):
    r = client.get("/api/v1/accounts")
    assert r.status_code == 401
```

- [ ] **Step 7: Run integration test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_accounts_api.py -v
```

Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add app/schemas/account.py app/repositories/account.py app/services/account.py app/routers/accounts.py app/main.py tests/integration/test_accounts_api.py
git commit -m "feat(accounts): full CRUD with audit log"
```

---

### Task 26: Instrument schemas + repository + service + router

**Files:**
- Create: `app/schemas/instrument.py`
- Create: `app/repositories/instrument.py`
- Create: `app/services/instrument.py`
- Create: `app/routers/instruments.py`
- Modify: `app/main.py`
- Create: `tests/integration/test_instruments_api.py`

- [ ] **Step 1: Implement `app/schemas/instrument.py`**

```python
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InstrumentCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    currency: str = Field(min_length=3, max_length=3)
    market: str | None = Field(default=None, max_length=16)
    industry_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    asset_class: str
    name: str | None
    currency: str
    market: str | None
    industry_id: uuid.UUID | None
    is_active: bool
    metadata: dict[str, Any] = Field(alias="metadata_json")
```

- [ ] **Step 2: Implement `app/repositories/instrument.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.instrument import Instrument


class InstrumentRepository:
    def __init__(self, session: Session):
        self.s = session

    def search(
        self, q: str | None = None, asset_class: str | None = None, limit: int = 50
    ) -> list[Instrument]:
        stmt = select(Instrument).where(Instrument.is_active.is_(True))
        if asset_class:
            stmt = stmt.where(Instrument.asset_class == asset_class)
        if q:
            like = f"%{q.upper()}%"
            stmt = stmt.where(
                (Instrument.symbol.ilike(like)) | (Instrument.name.ilike(like))
            )
        stmt = stmt.limit(limit)
        return list(self.s.execute(stmt).scalars())

    def get_by_symbol_market(self, symbol: str, market: str | None) -> Instrument | None:
        stmt = select(Instrument).where(Instrument.symbol == symbol)
        if market is not None:
            stmt = stmt.where(Instrument.market == market)
        return self.s.execute(stmt).scalar_one_or_none()

    def get_by_id(self, instrument_id: uuid.UUID) -> Instrument | None:
        return self.s.get(Instrument, instrument_id)

    def create(self, inst: Instrument) -> Instrument:
        self.s.add(inst)
        self.s.flush()
        return inst
```

- [ ] **Step 3: Implement `app/services/instrument.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.models.instrument import Instrument
from app.repositories.instrument import InstrumentRepository
from app.schemas.instrument import InstrumentCreate


class DuplicateInstrumentError(Exception):
    pass


class InstrumentService:
    def __init__(self, session: Session, audit: AuditWriter):
        self.s = session
        self.repo = InstrumentRepository(session)
        self.audit = audit

    def search(self, q=None, asset_class=None, limit=50):
        return self.repo.search(q=q, asset_class=asset_class, limit=limit)

    def get(self, instrument_id: uuid.UUID) -> Instrument | None:
        return self.repo.get_by_id(instrument_id)

    def get_by_symbol(self, symbol: str, market: str | None = None) -> Instrument | None:
        return self.repo.get_by_symbol_market(symbol, market)

    def create(self, payload: InstrumentCreate) -> Instrument:
        existing = self.repo.get_by_symbol_market(payload.symbol, payload.market)
        if existing:
            raise DuplicateInstrumentError(
                f"Instrument {payload.symbol} on {payload.market} already exists"
            )

        inst = Instrument(
            id=uuid.uuid4(),
            symbol=payload.symbol,
            asset_class=payload.asset_class,
            name=payload.name,
            currency=payload.currency,
            market=payload.market,
            industry_id=payload.industry_id,
            metadata_json=payload.metadata,
            is_active=True,
        )
        self.repo.create(inst)
        self.audit.record(
            action="INSERT",
            target_table="instruments",
            target_id=inst.id,
            after={
                "symbol": inst.symbol,
                "asset_class": inst.asset_class,
                "currency": inst.currency,
                "market": inst.market,
            },
        )
        return inst
```

- [ ] **Step 4: Implement `app/routers/instruments.py`**

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.audit import AuditWriter
from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.instrument import InstrumentCreate, InstrumentOut
from app.services.instrument import DuplicateInstrumentError, InstrumentService

router = APIRouter(prefix="/api/v1/instruments", tags=["instruments"])


def _audit(request: Request, user: User, db: Session) -> AuditWriter:
    rid = getattr(request.state, "request_id", None)
    return AuditWriter(
        db,
        request_id=uuid.UUID(rid) if rid else None,
        actor_user_id=user.id,
        actor_type="USER",
        ip=request.client.host if request.client else None,
    )


@router.get("", response_model=list[InstrumentOut])
def search_instruments(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(default=None),
    asset_class: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = InstrumentService(db, audit)
    return [InstrumentOut.model_validate(i) for i in svc.search(q=q, asset_class=asset_class, limit=limit)]


@router.post("", response_model=InstrumentOut, status_code=201)
def create_instrument(
    payload: InstrumentCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    svc = InstrumentService(db, _audit(request, user, db))
    try:
        inst = svc.create(payload)
    except DuplicateInstrumentError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return InstrumentOut.model_validate(inst)


@router.get("/{symbol}", response_model=InstrumentOut)
def get_instrument(
    symbol: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    market: str | None = Query(default=None),
):
    audit = AuditWriter(db, request_id=None, actor_user_id=user.id)
    svc = InstrumentService(db, audit)
    inst = svc.get_by_symbol(symbol, market)
    if inst is None:
        raise HTTPException(404, f"Instrument {symbol} not found")
    return InstrumentOut.model_validate(inst)
```

- [ ] **Step 5: Modify `app/main.py`**

Add import & include:

```python
from app.routers import instruments
...
app.include_router(instruments.router)
```

- [ ] **Step 6: Integration test `tests/integration/test_instruments_api.py`**

```python
import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"inst-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"inst{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email
    return client.post(
        "/auth/login", json={"email": email, "password": "good-password"}
    ).json()["access_token"]


def _h(t): return {"Authorization": f"Bearer {t}"}


def test_create_and_get_instrument(client, token):
    suffix = uuid.uuid4().hex[:6].upper()
    r = client.post(
        "/api/v1/instruments",
        json={
            "symbol": f"TST{suffix}",
            "asset_class": "STOCK",
            "name": "Test Co.",
            "currency": "USD",
            "market": "NASDAQ",
            "metadata": {"sector": "tech"},
        },
        headers=_h(token),
    )
    assert r.status_code == 201

    r = client.get(f"/api/v1/instruments/TST{suffix}?market=NASDAQ", headers=_h(token))
    assert r.status_code == 200
    assert r.json()["symbol"] == f"TST{suffix}"
    assert r.json()["metadata"]["sector"] == "tech"


def test_duplicate_instrument_returns_409(client, token):
    suffix = uuid.uuid4().hex[:6].upper()
    body = {
        "symbol": f"DUP{suffix}",
        "asset_class": "STOCK",
        "currency": "USD",
        "market": "NASDAQ",
    }
    r = client.post("/api/v1/instruments", json=body, headers=_h(token))
    assert r.status_code == 201

    r = client.post("/api/v1/instruments", json=body, headers=_h(token))
    assert r.status_code == 409


def test_search_instruments(client, token):
    suffix = uuid.uuid4().hex[:6].upper()
    client.post(
        "/api/v1/instruments",
        json={"symbol": f"SRCH{suffix}", "asset_class": "STOCK", "currency": "USD"},
        headers=_h(token),
    )
    r = client.get(f"/api/v1/instruments?q=SRCH{suffix}", headers=_h(token))
    assert r.status_code == 200
    syms = [i["symbol"] for i in r.json()]
    assert f"SRCH{suffix}" in syms
```

- [ ] **Step 7: Run test, expect 3 passed**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_instruments_api.py -v
```

- [ ] **Step 8: Commit**

```bash
git add app/schemas/instrument.py app/repositories/instrument.py app/services/instrument.py app/routers/instruments.py app/main.py tests/integration/test_instruments_api.py
git commit -m "feat(instruments): search + create + get with duplicate detection"
```

---

### Task 27: Admin router (invite + service token)

**Files:**
- Create: `app/schemas/admin.py`
- Create: `app/routers/admin.py`
- Create: `scripts/generate_service_token.py`
- Modify: `app/main.py`
- Create: `tests/integration/test_admin_api.py`

- [ ] **Step 1: Implement `app/schemas/admin.py`**

```python
from pydantic import BaseModel, EmailStr, Field


class InviteRequest(BaseModel):
    email: EmailStr
    notes: str | None = Field(default=None, max_length=500)


class InviteResponse(BaseModel):
    email: str
    status: str = "invited"


class ServiceTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    expires_in_minutes: int = Field(default=129600, gt=0, le=525600)  # default 90 days


class ServiceTokenResponse(BaseModel):
    name: str
    access_token: str
    expires_in_minutes: int
```

- [ ] **Step 2: Implement `app/routers/admin.py`**

```python
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.repositories.allowlisted_email import AllowlistedEmailRepository
from app.repositories.user import UserRepository
from app.schemas.admin import (
    InviteRequest,
    InviteResponse,
    ServiceTokenRequest,
    ServiceTokenResponse,
)
from app.security import create_access_token

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/invite", response_model=InviteResponse, status_code=201)
def invite(
    payload: InviteRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    repo = AllowlistedEmailRepository(db)
    repo.add(email=str(payload.email), invited_by=admin.id, notes=payload.notes)
    db.commit()
    return InviteResponse(email=str(payload.email))


@router.post("/service-tokens", response_model=ServiceTokenResponse, status_code=201)
def mint_service_token(
    payload: ServiceTokenRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    # Find or create SERVICE user named by payload.name
    users = UserRepository(db)
    email = f"service-{payload.name.lower()}@invest.local"
    user = users.get_by_email(email)
    if user is None:
        user = User(
            id=uuid.uuid4(),
            email=email,
            slug=f"svc-{payload.name.lower()}",
            display_name=payload.name,
            role="SERVICE",
            is_active=True,
        )
        users.create(user)

    token = create_access_token(
        subject=str(user.id),
        email=user.email,
        role="SERVICE",
        scope="service",
        expires_in_minutes=payload.expires_in_minutes,
    )
    db.commit()
    return ServiceTokenResponse(
        name=payload.name,
        access_token=token,
        expires_in_minutes=payload.expires_in_minutes,
    )
```

- [ ] **Step 3: Implement `scripts/generate_service_token.py`**

```python
"""
Generate a long-lived JWT for Cloud Scheduler use (run by admin).

Usage:
  python scripts/generate_service_token.py <name> [<minutes>]
"""
import sys
import uuid

from app.db import session_scope
from app.models.user import User
from app.repositories.user import UserRepository
from app.security import create_access_token


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_service_token.py <name> [<minutes>]", file=sys.stderr)
        sys.exit(2)

    name = sys.argv[1]
    minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 129_600  # 90 days

    email = f"service-{name.lower()}@invest.local"
    with session_scope() as s:
        users = UserRepository(s)
        user = users.get_by_email(email)
        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=email,
                slug=f"svc-{name.lower()}",
                display_name=name,
                role="SERVICE",
                is_active=True,
            )
            users.create(user)
            s.commit()
            user = users.get_by_email(email)
        assert user is not None

        token = create_access_token(
            subject=str(user.id),
            email=user.email,
            role="SERVICE",
            scope="service",
            expires_in_minutes=minutes,
        )

    print(token)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Modify `app/main.py`** — mount admin router

```python
from app.routers import admin
...
app.include_router(admin.router)
```

- [ ] **Step 5: Integration test `tests/integration/test_admin_api.py`**

```python
import os
import uuid

import pytest

from app.db import session_scope
from app.models.user import User
from app.security import hash_password

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB_URL"),
    reason="Requires INTEGRATION_DB_URL",
)


@pytest.fixture
def admin_token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"admin-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"admin{uuid.uuid4().hex[:8]}",
            role="ADMIN",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email
    return client.post(
        "/auth/login", json={"email": email, "password": "good-password"}
    ).json()["access_token"]


@pytest.fixture
def user_token(client):
    with session_scope() as s:
        u = User(
            id=uuid.uuid4(),
            email=f"u-{uuid.uuid4().hex[:8]}@x.z",
            slug=f"u{uuid.uuid4().hex[:8]}",
            role="USER",
            password_hash=hash_password("good-password"),
            is_active=True,
        )
        s.add(u)
        s.commit()
        email = u.email
    return client.post(
        "/auth/login", json={"email": email, "password": "good-password"}
    ).json()["access_token"]


def test_admin_invite(client, admin_token):
    r = client.post(
        "/api/v1/admin/invite",
        json={"email": f"new-{uuid.uuid4().hex[:8]}@x.z"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "invited"


def test_invite_requires_admin(client, user_token):
    r = client.post(
        "/api/v1/admin/invite",
        json={"email": "x@y.z"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 403


def test_mint_service_token(client, admin_token):
    r = client.post(
        "/api/v1/admin/service-tokens",
        json={"name": "scheduler-test", "expires_in_minutes": 60},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert body["name"] == "scheduler-test"
```

- [ ] **Step 6: Run test**

```bash
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest tests/integration/test_admin_api.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add app/schemas/admin.py app/routers/admin.py app/main.py scripts/generate_service_token.py tests/integration/test_admin_api.py
git commit -m "feat(admin): invite + service-token endpoints"
```


---

## Phase 0e — CI/CD + Production Deploy + Docs (Tasks 28-32)

Goal: Code lints, tests, builds, deploys automatically on push to main. Production DB schema applied. Smoke test passes from public URL. Docs in place.

---

### Task 28: GitHub Actions CI (lint + test on PR)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: investment_user
          POSTGRES_PASSWORD: dev_pw
          POSTGRES_DB: investment_v2
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
          cache: pip

      - run: pip install -r requirements-dev.txt

      - name: Ruff lint
        run: ruff check .

      - name: Ruff format check
        run: ruff format --check .

      - name: Mypy
        run: mypy app/

      - name: Apply migrations
        env:
          DB_URL: postgresql+psycopg://investment_user:dev_pw@localhost:5432/investment_v2
          JWT_SECRET: ci_secret_at_least_32_chars_xxxxxxxx
          GOOGLE_OAUTH_CLIENT_ID: ci.apps.googleusercontent.com
          FIRST_ADMIN_EMAIL: ci-admin@example.com
        run: python scripts/init_db.py

      - name: Run tests
        env:
          DB_URL: postgresql+psycopg://investment_user:dev_pw@localhost:5432/investment_v2
          INTEGRATION_DB_URL: postgresql+psycopg://investment_user:dev_pw@localhost:5432/investment_v2
          JWT_SECRET: ci_secret_at_least_32_chars_xxxxxxxx
          GOOGLE_OAUTH_CLIENT_ID: ci.apps.googleusercontent.com
        run: pytest -v
```

- [ ] **Step 2: Commit + push to a feature branch + open PR to verify**

```bash
git add .github/workflows/ci.yml
git commit -m "chore(ci): GitHub Actions CI (lint + test)"
git push origin HEAD
```

Open a PR on GitHub (use `gh pr create` or browser). Verify CI runs and passes.

If GitHub repo doesn't exist yet, create it:

```bash
gh repo create pin0513/investment-platform-v2 --public --source=. --remote=origin --push
```

- [ ] **Step 3: Verify CI passes on the open PR**

```bash
gh pr checks
```

Expected: all green.

---

### Task 29: GitHub Actions deploy (push image + Cloud Run deploy on main)

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Configure Workload Identity Federation (one-time)**

```bash
PROJECT_ID=paul-test-174403
PROJECT_NUMBER=329908581117
POOL_ID=github-pool
PROVIDER_ID=github-provider

gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" --location=global --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" --location=global \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Allow the GitHub repo to impersonate a deploy service account
gcloud iam service-accounts create gh-deploy --display-name="GitHub Actions deployer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:gh-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/run.admin

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:gh-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/artifactregistry.writer

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:gh-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/iam.serviceAccountUser

gcloud iam service-accounts add-iam-policy-binding \
  "gh-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/pin0513/investment-platform-v2"

# Print the WIF provider full name
echo "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
```

Save the WIF provider full name printed above — needed for the workflow.

- [ ] **Step 2: Create `.github/workflows/deploy.yml`**

```yaml
name: Deploy

on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

env:
  PROJECT_ID: paul-test-174403
  REGION: asia-east1
  SERVICE: investment-platform-v2
  IMAGE_NAME: asia-east1-docker.pkg.dev/paul-test-174403/investment-platform-v2/app

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: projects/329908581117/locations/global/workloadIdentityPools/github-pool/providers/github-provider
          service_account: gh-deploy@paul-test-174403.iam.gserviceaccount.com

      - uses: google-github-actions/setup-gcloud@v2

      - name: Configure docker for Artifact Registry
        run: gcloud auth configure-docker asia-east1-docker.pkg.dev --quiet

      - name: Build image
        run: |
          docker build \
            -t ${{ env.IMAGE_NAME }}:${{ github.sha }} \
            -t ${{ env.IMAGE_NAME }}:latest \
            .

      - name: Push image
        run: |
          docker push ${{ env.IMAGE_NAME }}:${{ github.sha }}
          docker push ${{ env.IMAGE_NAME }}:latest

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy ${{ env.SERVICE }} \
            --image=${{ env.IMAGE_NAME }}:${{ github.sha }} \
            --region=${{ env.REGION }} \
            --service-account=cr-investment-v2@${{ env.PROJECT_ID }}.iam.gserviceaccount.com \
            --allow-unauthenticated \
            --port=8080 \
            --min-instances=0 \
            --max-instances=3 \
            --cpu=1 \
            --memory=512Mi \
            --quiet
```

- [ ] **Step 3: Commit + push to main, verify deploy**

```bash
git add .github/workflows/deploy.yml
git commit -m "chore(cd): GitHub Actions auto-deploy to Cloud Run on main"
git push origin main
gh run watch
```

Expected: deploy workflow succeeds. Cloud Run gets the new image.

---

### Task 30: Wire prod DB_URL secret + run init_db on Cloud Run

**Files:**
- Modify: `Dockerfile` (run init_db on startup, optional)
- Modify: `scripts/deploy.sh` (use Secret Manager DB_URL)

- [ ] **Step 1: Create prod DB and user on the GCP VM**

SSH into `paul-ubuntu` VM, then run inside the postgres container:

```bash
gcloud compute ssh paul-ubuntu --zone=asia-east1-a --project=paul-test-174403

# Inside VM
sudo docker exec -i paulfun-postgres psql -U postgres <<SQL
CREATE DATABASE investment_v2;
CREATE USER investment_v2_user WITH PASSWORD 'GENERATED-40-CHARS-HERE';
GRANT ALL ON DATABASE investment_v2 TO investment_v2_user;
\c investment_v2
GRANT ALL ON SCHEMA public TO investment_v2_user;
SQL

# Exit
exit
```

Generate the password locally first:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(30))'
```

- [ ] **Step 2: Store DB_URL in Secret Manager**

```bash
INTERNAL_DB_URL="postgresql+psycopg://investment_v2_user:<password-from-step-1>@10.140.0.2:5432/investment_v2"
echo -n "$INTERNAL_DB_URL" | gcloud secrets create DB_URL \
  --replication-policy=automatic \
  --data-file=- \
  --project=paul-test-174403
```

If exists: `gcloud secrets versions add DB_URL --data-file=- --project=paul-test-174403`.

- [ ] **Step 3: Update `scripts/deploy.sh`** — replace placeholder with Secret Manager binding

Replace the `--set-env-vars="...,DB_URL=${DB_URL_PLACEHOLDER}" --set-secrets="JWT_SECRET=JWT_SECRET:latest"` line with:

```bash
  --set-env-vars="ENVIRONMENT=prod,ALLOWED_ORIGINS=https://invest.paulfun.net,GOOGLE_OAUTH_CLIENT_ID=329908581117-0csnfufiij5h5oc6a8qah5uvnm447ppo.apps.googleusercontent.com,FIRST_ADMIN_EMAIL=pin0513@gmail.com" \
  --set-secrets="JWT_SECRET=JWT_SECRET:latest,DB_URL=DB_URL:latest" \
  --vpc-egress=all-traffic \
  --network=default \
  --subnet=default \
```

(VPC egress is required to reach the VM internal IP `10.140.0.2`.)

- [ ] **Step 4: Add Cloud Run Job for one-off init_db**

```bash
gcloud run jobs create init-db-v2 \
  --image=asia-east1-docker.pkg.dev/paul-test-174403/investment-platform-v2/app:latest \
  --region=asia-east1 \
  --project=paul-test-174403 \
  --service-account=cr-investment-v2@paul-test-174403.iam.gserviceaccount.com \
  --set-env-vars="GOOGLE_OAUTH_CLIENT_ID=329908581117-0csnfufiij5h5oc6a8qah5uvnm447ppo.apps.googleusercontent.com,FIRST_ADMIN_EMAIL=pin0513@gmail.com" \
  --set-secrets="JWT_SECRET=JWT_SECRET:latest,DB_URL=DB_URL:latest" \
  --vpc-egress=all-traffic \
  --network=default \
  --subnet=default \
  --command=python \
  --args=scripts/init_db.py
```

If exists: `gcloud run jobs update init-db-v2 ...`.

- [ ] **Step 5: Run init_db once**

```bash
gcloud run jobs execute init-db-v2 \
  --region=asia-east1 \
  --project=paul-test-174403 \
  --wait
```

Expected: logs end with `init_db complete`.

- [ ] **Step 6: Redeploy the service (refresh env vars/secrets)**

```bash
./scripts/deploy.sh
```

- [ ] **Step 7: Commit script update**

```bash
git add scripts/deploy.sh
git commit -m "chore(deploy): wire DB_URL secret + VPC egress + init_db job"
```

---

### Task 31: E2E smoke test against deployed environment

**Files:**
- Create: `tests/integration/test_e2e_smoke.py`
- Create: `scripts/smoke.sh`

- [ ] **Step 1: Create `scripts/smoke.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://investment-platform-v2-329908581117.asia-east1.run.app}"

echo "==> Smoke test against $BASE_URL"

echo "1) /healthz"
curl -sf "$BASE_URL/healthz" | python3 -m json.tool

echo
echo "2) /api/v1/accounts without auth (expect 401)"
status=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/accounts" || echo "$?")
if [ "$status" != "401" ]; then
  echo "Expected 401, got $status"
  exit 1
fi
echo "OK"

echo
echo "3) error envelope on 404 /api/v1/nope"
curl -s "$BASE_URL/api/v1/nope" | python3 -c "import json, sys; d = json.load(sys.stdin); assert d['error']['code'] == 'NOT_FOUND', d"
echo "OK"

echo
echo "All smoke checks passed."
```

Make executable: `chmod +x scripts/smoke.sh`

- [ ] **Step 2: Get the actual Cloud Run URL**

```bash
gcloud run services describe investment-platform-v2 --region=asia-east1 --project=paul-test-174403 --format='value(status.url)'
```

- [ ] **Step 3: Run smoke test**

```bash
BASE_URL="$(gcloud run services describe investment-platform-v2 --region=asia-east1 --project=paul-test-174403 --format='value(status.url)')" ./scripts/smoke.sh
```

Expected: all three checks pass.

- [ ] **Step 4: Manually verify login flow with a test user**

Create a one-off password user via Cloud Run Job:

```bash
gcloud run jobs create one-off-create-test-user \
  --image=asia-east1-docker.pkg.dev/paul-test-174403/investment-platform-v2/app:latest \
  --region=asia-east1 --project=paul-test-174403 \
  --service-account=cr-investment-v2@paul-test-174403.iam.gserviceaccount.com \
  --set-secrets="JWT_SECRET=JWT_SECRET:latest,DB_URL=DB_URL:latest" \
  --set-env-vars="GOOGLE_OAUTH_CLIENT_ID=x" \
  --vpc-egress=all-traffic --network=default --subnet=default \
  --command=python --args="-c","
import uuid
from app.db import session_scope
from app.models.user import User
from app.security import hash_password
with session_scope() as s:
    s.add(User(id=uuid.uuid4(), email='smoke@invest.local', slug='smoke', role='USER', password_hash=hash_password('smoke-pw-12345'), is_active=True))
"
gcloud run jobs execute one-off-create-test-user --region=asia-east1 --project=paul-test-174403 --wait
```

Then test login:

```bash
curl -X POST "$BASE_URL/auth/login" \
  -H 'content-type: application/json' \
  -d '{"email":"smoke@invest.local","password":"smoke-pw-12345"}'
```

Expected: `{"access_token":"...","refresh_token":"...","token_type":"Bearer","expires_in":900}`

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke.sh
git commit -m "chore(smoke): post-deploy smoke script"
```

---

### Task 32: Docs (CLAUDE.md, AGENTS.md, api.md, data-model.md) + v0.1 tag

**Files:**
- Create: `CLAUDE.md`
- Create: `AGENTS.md`
- Create: `docs/api.md`
- Create: `docs/data-model.md`

- [ ] **Step 1: Create `CLAUDE.md`**

```markdown
# CLAUDE.md — investment-platform-v2

This file gives Claude (and any agent) what they need to operate this repo.

## What this is

Multi-asset portfolio platform. Supports TW/US stocks, ETFs, mutual funds, crypto (multi-exchange), bank deposits (TWD/USD/foreign currency). Uses a **Generic Instrument + JSONB metadata** schema and an **immutable transaction ledger** with `holdings` as a materialized view.

**Server runs zero LLM calls.** AI-generated weekly reports come from Claude Code on the user's machine, uploaded via `POST /api/v1/reports`.

## Architecture (P0)

Single FastAPI service on Cloud Run, region `asia-east1`. Backed by PostgreSQL 16 in shared `paulfun-postgres` container, DB `investment_v2`.

```
/healthz             health
/auth/*              login / refresh / logout / me / google
/api/v1/accounts     CRUD (audit logged)
/api/v1/instruments  search + create + get
/api/v1/admin/*      invite + service-token (admin only)
```

## Three auth modes, one JWT

| Caller | How |
|---|---|
| Browser | Google Sign-In → `__session` cookie + Bearer JWT |
| CLI / Claude Code MCP | `POST /auth/login` → `Authorization: Bearer <jwt>` |
| Cloud Scheduler | Long-lived service-account JWT minted via `/api/v1/admin/service-tokens` |

All three go through `get_current_user` in `app/dependencies.py`.

## Layout

- `app/main.py` — wire-up
- `app/config.py` — Settings (pydantic-settings)
- `app/db.py` — engine + session
- `app/security.py` — JWT, bcrypt
- `app/dependencies.py` — get_db, get_current_user, require_admin
- `app/audit.py` — AuditWriter (every mutation writes audit_log)
- `app/errors.py` — global exception handlers
- `app/models/` — SQLAlchemy
- `app/schemas/` — Pydantic v2
- `app/repositories/` — DB access
- `app/services/` — business logic
- `app/routers/` — FastAPI routers

Services are called by routers and (later) MCP tools. **Don't call DB from routers directly** — go through service.

## Common ops

```bash
# Local dev
docker compose -f docker-compose.dev.yml up -d db
DB_URL=postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2 \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x FIRST_ADMIN_EMAIL=pin0513@gmail.com \
python scripts/init_db.py

uvicorn app.main:app --reload

# Run all tests
pytest -v

# Deploy
./scripts/deploy.sh

# Smoke
BASE_URL=$(gcloud run services describe investment-platform-v2 --region=asia-east1 --format='value(status.url)') ./scripts/smoke.sh
```

## Conventions

- SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped[]`)
- Pydantic v2
- All time columns are `TIMESTAMPTZ`, stored UTC
- `metadata` reserved name → SQLAlchemy property `metadata_json` mapped to column `metadata` (JSONB)
- Soft delete via `deleted_at`
- enums as `VARCHAR(32)` (no PG enum types)
- Every mutation writes `audit_log` via `AuditWriter`

## Reference

- Spec: `docs/superpowers/specs/2026-05-12-investment-platform-v2-design.md`
- Plan: `docs/superpowers/plans/2026-05-12-p0-foundations.md`
- API doc: `docs/api.md`
- Data model: `docs/data-model.md`
```

- [ ] **Step 2: Create `AGENTS.md`**

```markdown
# AGENTS.md — operation guide

This repo is designed to be operated primarily by AI agents (Claude Code via MCP in P4).

## P0 (current phase): REST only

Until P4 (MCP server) ships, agents interact through REST:

1. Acquire JWT: `POST /auth/login {email, password}` → `access_token`
2. Use `Authorization: Bearer <access_token>` on subsequent calls
3. Refresh near expiry: `POST /auth/refresh {refresh_token}`

## Curl recipes

```bash
BASE=https://investment-platform-v2-329908581117.asia-east1.run.app

# Login
TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H 'content-type: application/json' \
  -d '{"email":"...","password":"..."}' | jq -r .access_token)

# List my accounts
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/accounts"

# Add an account
curl -s -X POST "$BASE/api/v1/accounts" \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"name":"永豐證券","account_type":"BROKER_STOCK","currency":"TWD"}'

# Add an instrument
curl -s -X POST "$BASE/api/v1/instruments" \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"symbol":"2330.TW","asset_class":"STOCK","name":"台積電","currency":"TWD","market":"TPE"}'
```

## Things NOT to do

- Don't call DB directly — use the API
- Don't bypass `get_current_user`
- Don't mutate `holdings` directly — that's a materialized view from `transactions` (P1 onward)
- Don't store credentials in this repo
```

- [ ] **Step 3: Create `docs/api.md`**

```markdown
# API Reference — v0.1 (P0)

Base URL: `https://invest.paulfun.net/api/v1` (production)
Auth: `Authorization: Bearer <jwt>` or `__session` cookie

## Endpoints shipped in P0

### Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | TokenResponse |
| POST | `/auth/google` | `{id_token}` | TokenResponse + sets `__session` cookie |
| POST | `/auth/refresh` | `{refresh_token}` | TokenResponse (rotates) |
| POST | `/auth/logout` | `{refresh_token}` | 204 |
| GET | `/auth/me` | — | UserOut |

### Accounts (auth required)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/accounts` | list (self) |
| POST | `/api/v1/accounts` | create |
| GET | `/api/v1/accounts/{id}` | detail |
| PATCH | `/api/v1/accounts/{id}` | update |
| DELETE | `/api/v1/accounts/{id}` | soft delete (204) |

### Instruments (auth required)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/instruments?q=&asset_class=&limit=` | search |
| POST | `/api/v1/instruments` | create |
| GET | `/api/v1/instruments/{symbol}?market=` | detail |

### Admin (ADMIN role required)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/admin/invite` | add email to allowlist |
| POST | `/api/v1/admin/service-tokens` | mint long-lived JWT |

### Error format

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "...",
    "request_id": "uuid",
    "details": {...}
  }
}
```
```

- [ ] **Step 4: Create `docs/data-model.md`**

```markdown
# Data Model — v0.1 (P0)

See full design in `docs/superpowers/specs/2026-05-12-investment-platform-v2-design.md`.

Tables shipped in P0:

| Table | Purpose |
|---|---|
| `users` | accounts + roles + slug |
| `allowlisted_emails` | who can sign up via Google |
| `refresh_tokens` | revocable refresh JWTs (hashed) |
| `accounts` | broker / bank / exchange wallets |
| `instruments` | Generic Instrument (CASH/STOCK/ETF/FUND/CRYPTO/...) |
| `industries` | seeded industry taxonomy |
| `audit_log` | every mutation |

P1 adds: `transactions`, `holdings`, `price_history`, `quotes`, `exchange_rates`, `snapshots`, `news_items`, `instrument_tags`, `instrument_metadata_history`, `reports`.
```

- [ ] **Step 5: Commit docs**

```bash
git add CLAUDE.md AGENTS.md docs/api.md docs/data-model.md
git commit -m "docs: CLAUDE.md + AGENTS.md + api.md + data-model.md"
```

- [ ] **Step 6: Tag v0.1**

```bash
git tag -a v0.1.0 -m "P0: Foundations — auth + CRUD + Cloud Run deploy"
git push origin v0.1.0
```

- [ ] **Step 7: Final verification — full test suite + smoke**

```bash
# Local
INTEGRATION_DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
DB_URL='postgresql+psycopg://investment_user:dev_pw@localhost:5433/investment_v2' \
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
GOOGLE_OAUTH_CLIENT_ID=x \
pytest -v

# Production
BASE_URL=$(gcloud run services describe investment-platform-v2 --region=asia-east1 --project=paul-test-174403 --format='value(status.url)') ./scripts/smoke.sh
```

Expected: all tests pass + smoke passes.

P0 is complete. Next: P1 (Core Mutation Path — transactions, holdings, portfolio summary, MCP tools subset).

---

## Self-Review (final)

### Spec coverage check

| Spec section | Covered by |
|---|---|
| §2 Architecture overview | Tasks 3, 6, 22, 25-27 (FastAPI + monolith deploy) |
| §3.1 Naming conventions | Documented in plan header + applied across Tasks 8-11 |
| §3.3 users / allowlist / refresh_tokens | Task 9 |
| §3.3 accounts | Task 10 |
| §3.3 industries | Task 10 + seed in Task 14 |
| §3.3 instruments | Task 10 |
| §3.3 audit_log | Task 11 |
| §3.3 transactions / holdings / price_history / etc. | **Deferred to P1** (out of P0 scope) |
| §3.4 Migration conventions | Task 12-13 |
| §4 Auth (JWT 3 entrypoints) | Tasks 16, 19-22 |
| §5.1 Endpoints — Auth, Accounts, Instruments, Admin | Tasks 22, 25-27 |
| §5.1 Endpoints — Transactions / Holdings / Portfolio / Reports / News / Jobs | **Deferred to P1+** |
| §5.2 Error format | Task 24 |
| §6 Reader UI | **Deferred to P2** |
| §7 MCP Tools | **Deferred to P4** |
| §8 Scheduler | **Deferred to P3** |
| §9 Report lifecycle | **Deferred to P4** |
| §10 Onboarding wizard | **Deferred to P6** (UI) |
| §10.1 init_db.py | Task 15 |
| §11 Deploy architecture | Tasks 5-6, 29-30 |
| §12 Observability — /healthz | Task 3 |
| §12 Observability — /metrics, audit_log query, alerts | partial: audit_log writer Task 23; metrics/alerts deferred |
| §13 AI-readable repo | Task 32 |

Confirmed P0 scope: foundations only (auth + CRUD + audit + deploy). Deferred items will be picked up by subsequent phase plans.

### Placeholder scan

Searched plan for: `TBD`, `TODO`, `implement later`, `fill in`, `add appropriate`, `handle edge cases`, `similar to`. None present in instructional steps. (The plan does say "deferred to P1/P2/etc." which are explicit phase boundaries, not placeholders.)

### Type consistency check

- `AuditWriter(session, request_id=..., actor_user_id=..., actor_type=..., ip=...)` — same signature in Tasks 23, 25, 26, 27 ✓
- `AccountService(session, audit)` — consistent in Task 25 ✓
- `InstrumentService(session, audit)` — consistent in Task 26 ✓
- `User.metadata_json` (col `metadata`) — same pattern in Tasks 9, 10 ✓
- `AccountOut` uses `Field(alias="metadata_json")` — matches model attribute ✓
- `decode_access_token` returns `dict[str, Any]` — consumed in `get_current_user` (Task 21) ✓
- `create_access_token(subject, email, role, scope, expires_in_minutes)` — same kwargs across Tasks 16, 19, 27 ✓
- `new_refresh_token` / `hash_refresh_token` — naming consistent ✓

No drift found.

