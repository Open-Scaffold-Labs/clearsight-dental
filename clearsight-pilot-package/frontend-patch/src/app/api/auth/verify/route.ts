/**
 * GET /api/auth/verify?token=...
 *
 * Consumes a magic-link token, issues a session cookie, and redirects to
 * /app (or /baa if the user has not yet accepted the current BAA/CPA).
 */
import { NextRequest, NextResponse } from "next/server";
import { sql, sha256Hex } from "@/lib/db";
import { issueSession, SESSION_COOKIE_NAME } from "@/lib/session";

export const runtime = "nodejs";

const BAA_VERSION = process.env.BAA_VERSION || "v1.0";
const CPA_VERSION = process.env.CPA_VERSION || "v1.0";

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("token") || "";
  if (!raw) {
    return NextResponse.redirect(new URL("/login?err=missing_token", req.url));
  }
  const tokenHash = await sha256Hex(raw);

  // Atomic single-use redemption: mark the token used only if it has not
  // already been used and has not expired.
  const rows = (await sql`
    UPDATE magic_tokens
    SET used_at = now()
    WHERE token_hash = ${tokenHash}
      AND used_at IS NULL
      AND expires_at > now()
    RETURNING user_id
  `) as Array<{ user_id: string }>;

  if (rows.length === 0) {
    return NextResponse.redirect(new URL("/login?err=invalid_or_expired", req.url));
  }
  const userId = rows[0].user_id;

  const userRows = (await sql`
    SELECT u.id, u.tenant_id, u.role,
           (
             SELECT 1 FROM baa_acceptance
             WHERE user_id = u.id
               AND baa_version = ${BAA_VERSION}
               AND cpa_version = ${CPA_VERSION}
             LIMIT 1
           ) AS has_baa
    FROM users u
    WHERE u.id = ${userId}
    LIMIT 1
  `) as Array<{ id: string; tenant_id: string; role: string; has_baa: number | null }>;

  if (userRows.length === 0) {
    return NextResponse.redirect(new URL("/login?err=user_not_found", req.url));
  }
  const u = userRows[0];

  await sql`UPDATE users SET last_login_at = now() WHERE id = ${u.id}`;

  const token = await issueSession({
    uid: u.id,
    tid: u.tenant_id,
    baa: Boolean(u.has_baa),
    role: u.role,
  });

  const res = NextResponse.redirect(new URL(u.has_baa ? "/app" : "/baa", req.url));
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
