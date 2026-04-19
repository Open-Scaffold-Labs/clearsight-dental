# ClearSight Dental — Pilot Build Package

This directory contains everything needed to stand up the **hosted pilot** of ClearSight Dental for one practice (Dia Basher DDS) using real OralAgent + OralGPT-Omni 7B on Fly.io GPU, fronted by a Vercel Next.js app, with PHI persistence on Neon Postgres.

The goal of this package is to replace the demo/Supabase/fake-analyzer scaffold with something that a real HIPAA-covered practice could actually touch — under a signed BAA and Clinical Pilot Agreement, under a 90-day pilot term, with full audit logging and 30-day PHI retention.

## What's in here

```
clearsight-pilot-package/
├── backend/                        Fly.io Python GPU service
│   ├── Dockerfile                  PyTorch 2.3.1 + CUDA 12.1, model baked in
│   ├── fly.toml                    A100-40GB machine, auto-suspend when idle
│   ├── requirements.txt            FastAPI, psycopg, transformers stack
│   ├── ORALAGENT_PINNED_COMMIT.txt Pin the vendored OralAgent sha here
│   ├── .env.example
│   ├── fixtures/README.md
│   └── app/
│       ├── __init__.py
│       ├── config.py               Pydantic Settings
│       ├── db.py                   psycopg AsyncConnectionPool
│       ├── audit.py                Append-only audit.write()
│       ├── oral_agent_client.py    OralGPT-Omni inference wrapper
│       ├── main.py                 FastAPI app (/healthz /readyz /analyze)
│       └── schema.sql              Postgres DDL (tenants, users, magic_tokens,
│                                   baa_acceptance, audit_log, analysis_runs)
└── frontend-patch/                 Drop-in patch to the Vercel Next.js app
    ├── .env.example
    ├── INTEGRATION.md              How to install into clearsight-dental
    └── src/
        ├── middleware.ts           Session + BAA-gate enforcement
        ├── lib/
        │   ├── db.ts               Neon serverless SQL client
        │   └── session.ts          HS256 JWT session cookie
        ├── components/
        │   ├── BAAGate.tsx         Full-page BAA+CPA acceptance interstitial
        │   └── PilotBanner.tsx     Persistent "pilot, not diagnostic" banner
        └── app/api/
            ├── auth/magic-link/route.ts   Email a one-time link
            ├── auth/verify/route.ts       Redeem link, set session cookie
            ├── baa/accept/route.ts        Record BAA+CPA acceptance
            └── analyze/route.ts           Proxy to Fly.io backend
```

Outside this directory but part of the same deliverable set (saved to the user's Desktop):

- `ClearSight_Pilot_BAA_v1.0.docx` — HIPAA Business Associate Agreement
- `ClearSight_Clinical_Pilot_Agreement_v1.0.docx` — Clinical Pilot Agreement
- `ClearSight_Hosted_Pilot_Deployment_Runbook_v1.0.docx` — 10-step deploy runbook
- `ClearSight_Pilot_Compliance_Baseline_v1.0.xlsx` — HIPAA controls + evidence + audit calendar

## What this does NOT do

- It does not bind the BAA or CPA. Both documents must be reviewed by healthcare counsel before a practice signs.
- It does not create any cloud accounts. The runbook has the user execute all provisioning steps (Fly.io, Vercel, Neon, Resend) so that every contract and every key is in the user's name, not Claude's.
- It does not purchase or bind cyber-liability insurance. The CPA requires a $5M cyber policy — the user must obtain that before go-live.
- It does not FDA-clear anything. The product is framed end-to-end as a non-diagnostic clinical support tool. That framing is reinforced in the BAA, the CPA, the UI banner, the BAA gate, and the API response wrapper.
- It does not replace the counsel review step. The BAA and CPA are drafts — good drafts, with the right HIPAA hooks — but they are not legal advice and must be reviewed by a lawyer admitted in the governing-law jurisdiction before execution.

## Path from here to a live URL

The detailed runbook (`ClearSight_Hosted_Pilot_Deployment_Runbook_v1.0.docx`) is the authoritative source, but the summary is:

1. Get both `*.docx` legal documents reviewed by counsel, get them executed by the practice, and export the approved PDFs to `public/legal/BAA-v1.0.pdf` and `public/legal/CPA-v1.0.pdf`.
2. Obtain a countersigned Fly.io BAA and Vercel Pro BAA. Confirm Neon BAA availability on the paid plan.
3. Provision Neon Postgres. Apply `backend/app/schema.sql`.
4. Download `OralGPT-Omni-7B-Instruct` from Hugging Face to local disk; clone OralAgent at a specific commit and record it in `ORALAGENT_PINNED_COMMIT.txt`.
5. `flyctl launch` the backend with the A100-40GB GPU profile in `fly.toml`. Set `DATABASE_URL`, `SHARED_API_SECRET`, `FRONTEND_ORIGIN` as Fly secrets.
6. `vercel deploy --prod` the patched Next.js frontend. Set the matching environment variables per `frontend-patch/.env.example`.
7. Create one tenant row for `dia-basher-dds` and one user row for Dr. Basher's email.
8. Smoke-test with `fixtures/sample-opg.jpg` (synthetic, non-PHI) via the runbook's Step 8 test plan.
9. Send the `*.vercel.app` URL to Dr. Basher only after (1)-(8) are done and counsel has signed off.

## Tenancy model

Per-practice tenant row. Single pilot tenant today; schema accommodates N tenants without modification. Tenant isolation is application-enforced in the pilot and will move to Postgres row-level security before the second tenant is onboarded.

## Data-handling summary

- Uploaded dental images are sent to the Fly.io backend over TLS, held in memory for inference, and written to short-lived blob storage (out of scope here — runbook covers the S3/R2 bucket).
- Raw image bytes are **not** stored in Postgres. Only the SHA-256 hash, modality, and structured findings are persisted.
- Audit log is append-only. Application DB role has no `UPDATE` or `DELETE` permission on `audit_log` (see `schema.sql` comment). Retention by scheduled job.
- Pilot retention default: 30 days for image bytes, 6 years for audit log (HIPAA minimum). Both are configurable per-tenant.
- No data is used to train or fine-tune models. The BAA and CPA both prohibit it.

## Cost envelope (pilot)

- Fly.io A100-40GB GPU machine: ~$1.50/hour while active; suspends to ~$0 when idle. Budget: $200-400/month for one low-volume pilot.
- Vercel Pro: $20/month base.
- Neon Pro: $19/month base.
- Resend: free tier covers pilot volume.
- Total: ~$250-450/month for one pilot practice, before counsel and insurance costs.
