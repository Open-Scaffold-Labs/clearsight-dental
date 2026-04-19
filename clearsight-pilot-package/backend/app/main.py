"""ClearSight Dental — Pilot Backend (FastAPI).

Endpoints:
  GET  /healthz   — liveness + model identity (runbook Step 6 smoke test)
  GET  /readyz    — readiness (DB reachable, model loaded)
  GET  /metrics   — Prometheus exposition
  POST /analyze   — run OralAgent + OralGPT-Omni on an uploaded image

Auth: shared-secret bearer token between Vercel frontend and this backend.
      End-user auth is handled at the Vercel edge (magic-link + session cookie);
      the edge calls this service with its own long-lived secret.

Every PHI-touching request writes an audit row before returning.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from . import audit
from .config import settings
from .db import init_pool, close_pool, get_conn
from .oral_agent_client import OralAgentClient, ModelNotReady

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("clearsight.main")

# ------------------------------------------------------------------
# Prometheus metrics
# ------------------------------------------------------------------
REQ_COUNT = Counter(
    "clearsight_requests_total",
    "Total API requests",
    ["endpoint", "status"],
)
ANALYZE_LATENCY = Histogram(
    "clearsight_analyze_seconds",
    "End-to-end /analyze latency (seconds)",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

# ------------------------------------------------------------------
# Lifespan: initialize DB pool + load model once at boot
# ------------------------------------------------------------------
agent: OralAgentClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    log.info("startup: initializing database pool")
    await init_pool()

    log.info("startup: loading model %s from %s", settings.model_name, settings.model_dir)
    agent = OralAgentClient(
        model_dir=settings.model_dir,
        model_name=settings.model_name,
        max_concurrent=settings.max_concurrent,
    )
    try:
        await agent.load()
        log.info("startup: model ready")
    except Exception:  # noqa: BLE001
        # Do not crash the container — /readyz will report not-ready and Fly.io
        # will keep the machine alive so we can inspect logs.
        log.exception("startup: model failed to load; /readyz will return 503")
    yield
    log.info("shutdown: closing database pool")
    await close_pool()
    if agent is not None:
        await agent.aclose()


app = FastAPI(
    title="ClearSight Dental — Pilot Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,  # edge uses a shared secret, not a browser cookie
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)


# ------------------------------------------------------------------
# Shared-secret auth (edge -> backend)
# ------------------------------------------------------------------
def _check_shared_secret(authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    presented = authorization.split(" ", 1)[1].strip()
    # constant-time compare
    import hmac
    if not hmac.compare_digest(presented, settings.shared_api_secret):
        raise HTTPException(status_code=401, detail="invalid bearer token")


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------
@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    """Liveness probe. Returns 200 as long as the process is up.

    Runbook Step 6 expected shape:
      {"status":"ok","model":"oralgpt-omni-7b","version":"0.1.0"}
    """
    REQ_COUNT.labels(endpoint="healthz", status="200").inc()
    return {
        "status": "ok",
        "model": settings.model_name,
        "version": app.version,
    }


@app.get("/readyz")
async def readyz() -> JSONResponse:
    """Readiness probe. 200 only if DB reachable AND model loaded."""
    db_ok = False
    model_ok = agent is not None and agent.is_ready()
    try:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()
        db_ok = True
    except Exception:  # noqa: BLE001
        log.exception("readyz: database not reachable")

    status = "ok" if (db_ok and model_ok) else "not_ready"
    code = 200 if status == "ok" else 503
    REQ_COUNT.labels(endpoint="readyz", status=str(code)).inc()
    return JSONResponse(
        status_code=code,
        content={"status": status, "db": db_ok, "model": model_ok},
    )


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.post("/analyze")
async def analyze(
    request: Request,
    image: UploadFile = File(...),
    modality: str = Form("opg"),
    prompt: str | None = Form(None),
    tenant_id: str | None = Form(None),
    user_id: str | None = Form(None),
    authorization: str | None = Header(None),
    x_request_id: str | None = Header(None),
) -> JSONResponse:
    """Analyze a dental image.

    The frontend (Vercel edge) is the real authn/authz boundary. This endpoint
    trusts the caller only to the extent that it presents the shared secret;
    the edge is responsible for attaching the authenticated tenant_id and
    user_id from its own session store.
    """
    _check_shared_secret(authorization)

    if agent is None or not agent.is_ready():
        REQ_COUNT.labels(endpoint="analyze", status="503").inc()
        raise HTTPException(status_code=503, detail="model not ready")

    # Basic input hygiene — the edge already does its own validation.
    if image.content_type not in {"image/jpeg", "image/png", "application/dicom"}:
        REQ_COUNT.labels(endpoint="analyze", status="415").inc()
        raise HTTPException(status_code=415, detail=f"unsupported content-type: {image.content_type}")

    tenant = tenant_id or settings.pilot_tenant_id
    try:
        user_uuid: UUID | None = UUID(user_id) if user_id else None
    except ValueError:
        REQ_COUNT.labels(endpoint="analyze", status="400").inc()
        raise HTTPException(status_code=400, detail="user_id must be a UUID")

    try:
        request_id = UUID(x_request_id) if x_request_id else uuid4()
    except ValueError:
        request_id = uuid4()

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    image_bytes = await image.read()
    if not image_bytes:
        REQ_COUNT.labels(endpoint="analyze", status="400").inc()
        raise HTTPException(status_code=400, detail="empty image")
    sha256 = hashlib.sha256(image_bytes).hexdigest()

    t0 = time.monotonic()
    status_code = 200
    error_message: str | None = None
    response_payload: dict[str, Any] = {}

    try:
        with ANALYZE_LATENCY.time():
            result = await agent.analyze(
                image_bytes=image_bytes,
                content_type=image.content_type or "image/jpeg",
                modality=modality,
                prompt=prompt,
            )
        response_payload = {
            "request_id": str(request_id),
            "model": settings.model_name,
            "modality": modality,
            "findings": result.get("findings", []),
            "raw": result.get("raw"),
        }
    except ModelNotReady:
        status_code = 503
        error_message = "model not ready"
    except asyncio.TimeoutError:
        status_code = 504
        error_message = "inference timeout"
    except Exception as e:  # noqa: BLE001
        status_code = 500
        error_message = type(e).__name__
        log.exception("analyze_failed request_id=%s", request_id)

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # Audit first, then respond. Audit failures are logged but do not block.
    await audit.write(
        action="analyze",
        tenant_id=tenant,
        user_id=user_uuid,
        resource_type="image",
        resource_id=sha256,
        image_sha256=sha256,
        model_version=settings.model_name,
        request_id=request_id,
        ip_address=client_ip,
        user_agent=user_agent,
        response_ms=elapsed_ms,
        status_code=status_code,
        error_message=error_message,
        metadata={"modality": modality, "content_type": image.content_type},
    )

    REQ_COUNT.labels(endpoint="analyze", status=str(status_code)).inc()
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=error_message or "error")

    # Persist metadata-only record of the analysis run.
    try:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO analysis_runs
                      (tenant_id, user_id, image_sha256, image_modality,
                       model_version, prompt, response, response_ms, completed_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
                    """,
                    (
                        tenant, user_uuid, sha256, modality,
                        settings.model_name, prompt,
                        audit.psycopg_jsonb(response_payload),
                        elapsed_ms,
                    ),
                )
    except Exception:  # noqa: BLE001
        log.exception("analysis_runs_insert_failed request_id=%s", request_id)

    return JSONResponse(status_code=200, content=response_payload)
