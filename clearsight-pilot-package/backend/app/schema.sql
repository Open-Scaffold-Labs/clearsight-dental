-- ClearSight Dental — Pilot Postgres Schema
-- Apply with:  psql "$DATABASE_URL" -f app/schema.sql
--
-- Design notes:
-- - Append-only audit_log (no UPDATE/DELETE in the application; retention via scheduled purge by age only)
-- - SHA-256 of uploaded images is stored; raw image bytes are NOT stored in Postgres (blob storage only)
-- - Tenant isolation is application-enforced for now; production will add Postgres row-level security

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------
-- Tenants (one per practice)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id               TEXT PRIMARY KEY,           -- slug: "dia-basher-dds"
    name             TEXT NOT NULL,
    practice_email   TEXT NOT NULL,
    baa_signed_at    TIMESTAMPTZ,                -- NULL = BAA not yet countersigned; sign-ins blocked
    cpa_signed_at    TIMESTAMPTZ,                -- Clinical Pilot Agreement
    pilot_started_at TIMESTAMPTZ,
    pilot_ends_at    TIMESTAMPTZ,
    retention_days   INTEGER NOT NULL DEFAULT 30,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------
-- Users (per tenant; magic-link auth only)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    email           CITEXT,                                -- install citext extension if you want CI email
    role            TEXT NOT NULL CHECK (role IN ('practice-lead','clinician','staff','admin','suspended')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ,
    UNIQUE (tenant_id, email)
);
-- If the citext extension isn't available in your Postgres, swap CITEXT -> TEXT above.

-- -----------------------------------------------------------------
-- Magic-link auth tokens (one-time, 10-minute expiry)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS magic_tokens (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    TEXT NOT NULL,                           -- SHA-256 of the token; raw token never stored
    expires_at    TIMESTAMPTZ NOT NULL,
    used_at       TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS magic_tokens_user_ix ON magic_tokens (user_id, expires_at);

-- -----------------------------------------------------------------
-- BAA acceptance log (per-user attestation that they reviewed the BAA before first use)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS baa_acceptance (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    tenant_id    TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    baa_version  TEXT NOT NULL,                            -- "v1.0"
    cpa_version  TEXT NOT NULL,
    ip_address   INET,
    user_agent   TEXT,
    accepted_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS baa_acceptance_user_ix ON baa_acceptance (user_id, accepted_at DESC);

-- -----------------------------------------------------------------
-- Audit log (APPEND-ONLY — no UPDATEs, no row-level DELETEs)
-- Retention enforced by scheduled job by audit_log.ts < now() - retention_days
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id             BIGSERIAL PRIMARY KEY,
    ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
    tenant_id      TEXT,
    user_id        UUID,
    action         TEXT NOT NULL,                          -- 'analyze','login','logout','baa_accept', ...
    resource_type  TEXT,                                   -- 'image','session', ...
    resource_id    TEXT,
    image_sha256   TEXT,                                   -- hash of the analyzed image, if any
    model_version  TEXT,                                   -- 'oralgpt-omni-7b@<sha>'
    request_id     UUID,
    ip_address     INET,
    user_agent     TEXT,
    response_ms    INTEGER,
    status_code    INTEGER,
    error_message  TEXT,
    metadata       JSONB
);
CREATE INDEX IF NOT EXISTS audit_log_ts_ix       ON audit_log (ts DESC);
CREATE INDEX IF NOT EXISTS audit_log_tenant_ix   ON audit_log (tenant_id, ts DESC);
CREATE INDEX IF NOT EXISTS audit_log_action_ix   ON audit_log (action, ts DESC);

-- Revoke UPDATE/DELETE from the application role to enforce append-only
-- (adjust role name to match your Neon/Supabase setup)
-- REVOKE UPDATE, DELETE ON audit_log FROM app_role;

-- -----------------------------------------------------------------
-- Analysis runs (metadata only; image bytes in blob storage)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_runs (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    image_sha256   TEXT NOT NULL,
    image_modality TEXT,                                   -- 'opg','periapical','ceph','intraoral','other'
    model_version  TEXT NOT NULL,
    prompt         TEXT,
    response       JSONB,
    response_ms    INTEGER,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at   TIMESTAMPTZ,
    purged_at      TIMESTAMPTZ                             -- set when PHI is purged from blob storage
);
CREATE INDEX IF NOT EXISTS analysis_runs_tenant_ix ON analysis_runs (tenant_id, started_at DESC);

COMMIT;
