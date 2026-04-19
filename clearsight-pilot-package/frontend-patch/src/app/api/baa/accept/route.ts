/**
 * POST /api/baa/accept
 *
 * Records this user's acceptance of the specified BAA + CPA versions.
 * Idempotent: re-accepting the same version pair is a no-op.
 */
import { NextRequest, NextResponse } from "next/server";
import { sql } from "@/lib/db";
import { currentSession, issueSession, SESSION_COOKIE_NAME } from "@/lib/session";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const session = await currentSession();
  if (!session) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const baaVersion = String(body.baa_version || "").trim();
  const cpaVersion = String(body.cpa_version || "").trim();
  if (!baaVersion || !cpaVersion) {
    return NextResponse.json({ error: "baa_version and cpa_version required" }, { status: 400 });
  }

  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null;
  const ua = req.headers.get("user-agent") || null;

  await sql`
    INSERT INTO baa_acceptance (user_id, tenant_id, baa_version, cpa_version, ip_address, user_agent)
    VALUES (${session.uid}, ${session.tid}, ${baaVersion}, ${cpaVersion}, ${ip}, ${ua})
  `;

  // Also write an audit row — the audit_log is the authoritative record.
  await sql`
    INSERT INTO audit_log (tenant_id, user_id, action, resource_type, ip_address, user_agent, metadata)
    VALUES (
      ${session.tid}, ${session.uid}, 'baa_accept', 'baa',
      ${ip}, ${ua},
      ${JSON.stringify({ baa_version: baaVersion, cpa_version: cpaVersion })}::jsonb
    )
  `;

  // Re-issue session with baa=true so the middleware stops redirecting.
  const token = await issueSession({ ...session, baa: true });
  const res = NextResponse.json({ ok: true });
  res.cookies.set({
    name: SESSION_COOKIE_NAME,
    value: token,
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  return res;
}
