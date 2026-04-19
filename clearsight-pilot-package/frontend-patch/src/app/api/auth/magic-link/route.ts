/**
 * POST /api/auth/magic-link
 *
 * Request a magic-link email. Returns 200 whether or not the email exists
 * (prevents account enumeration). A one-time token is generated, its SHA-256
 * hash is stored with a 10-minute expiry, and the raw token is emailed via
 * Resend.
 */
import { NextRequest, NextResponse } from "next/server";
import { Resend } from "resend";
import { sql, sha256Hex } from "@/lib/db";

export const runtime = "nodejs";

const resend = new Resend(process.env.RESEND_API_KEY);
const FROM = process.env.RESEND_FROM || "ClearSight Dental <noreply@clearsight-dental.com>";

function randomToken(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const email = String(body.email || "").trim().toLowerCase();
  if (!email || !email.includes("@")) {
    return NextResponse.json({ error: "email required" }, { status: 400 });
  }

  // Look up user by email. Do NOT create users from this endpoint — that is
  // an admin-only operation to prevent self-service enrollment into the pilot.
  const rows = (await sql`
    SELECT id, tenant_id, role FROM users
    WHERE email = ${email} AND role <> 'suspended'
    LIMIT 1
  `) as Array<{ id: string; tenant_id: string; role: string }>;

  if (rows.length === 0) {
    // Silent success — do not reveal whether the email is enrolled.
    return NextResponse.json({ ok: true });
  }
  const user = rows[0];

  const token = randomToken();
  const tokenHash = await sha256Hex(token);
  const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

  await sql`
    INSERT INTO magic_tokens (user_id, token_hash, expires_at)
    VALUES (${user.id}, ${tokenHash}, ${expiresAt.toISOString()})
  `;

  const origin = process.env.NEXT_PUBLIC_APP_ORIGIN || req.nextUrl.origin;
  const link = `${origin}/api/auth/verify?token=${encodeURIComponent(token)}`;

  try {
    await resend.emails.send({
      from: FROM,
      to: email,
      subject: "Your ClearSight Dental sign-in link",
      text: [
        "Click the link below to sign in to ClearSight Dental.",
        "",
        link,
        "",
        "The link expires in 10 minutes and can be used once.",
        "If you did not request this, you can ignore this email.",
      ].join("\n"),
    });
  } catch (e) {
    console.error("magic_link_send_failed", e);
    // Still return 200 to the client — we do not want to leak send failures
    // to an unauthenticated caller. Admins will see the failure in logs.
  }

  return NextResponse.json({ ok: true });
}
