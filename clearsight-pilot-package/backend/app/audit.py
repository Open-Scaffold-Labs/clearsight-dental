"""Append-only audit logging. Every PHI-touching operation writes here.

Never UPDATE or DELETE rows from within the application. Retention is
enforced by a scheduled job outside the application (see runbook § Retention).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID, uuid4

from .db import get_conn

log = logging.getLogger("clearsight.audit")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def write(
    *,
    action: str,
    tenant_id: str | None,
    user_id: UUID | None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    image_sha256: str | None = None,
    model_version: str | None = None,
    request_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    response_ms: int | None = None,
    status_code: int | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write a single audit row. Failures are logged but do not interrupt the calling request."""
    if request_id is None:
        request_id = uuid4()
    try:
        async with get_conn() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO audit_log
                      (tenant_id, user_id, action, resource_type, resource_id,
                       image_sha256, model_version, request_id, ip_address,
                       user_agent, response_ms, status_code, error_message, metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        tenant_id, user_id, action, resource_type, resource_id,
                        image_sha256, model_version, request_id, ip_address,
                        user_agent, response_ms, status_code, error_message,
                        psycopg_jsonb(metadata),
                    ),
                )
    except Exception:  # noqa: BLE001
        # A broken audit log is a clinical-safety issue, but the correct behavior
        # here is to log and continue: the upstream request must still return
        # something to the user, and the infrastructure layer's healthchecks
        # will surface persistent failures.
        log.exception("audit_insert_failed action=%s tenant=%s", action, tenant_id)


def psycopg_jsonb(value: dict | None):
    if value is None:
        return None
    import json
    from psycopg.types.json import Jsonb
    return Jsonb(value)
