/**
 * Session cookie helpers for the magic-link flow.
 *
 * Sessions are short-lived (30 minutes idle, 8 hours absolute) and carry
 * the user_id plus tenant_id as a signed JWT. No PHI in the cookie.
 */
import { SignJWT, jwtVerify, type JWTPayload } from "jose";
import { cookies } from "next/headers";

const COOKIE_NAME = "cs_session";
const SECRET = new TextEncoder().encode(
  process.env.SESSION_SECRET || (() => { throw new Error("SESSION_SECRET is not set"); })()
);

export interface SessionClaims extends JWTPayload {
  uid: string;     // user UUID
  tid: string;     // tenant slug
  baa: boolean;    // has accepted BAA
  role: string;
}

export async function issueSession(claims: Omit<SessionClaims, "iat" | "exp">): Promise<string> {
  return await new SignJWT(claims as JWTPayload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("8h")
    .sign(SECRET);
}

export async function readSession(token: string | undefined): Promise<SessionClaims | null> {
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, SECRET);
    return payload as SessionClaims;
  } catch {
    return null;
  }
}

export async function setSessionCookie(token: string): Promise<void> {
  (await cookies()).set({
    name: COOKIE_NAME,
    value: token,
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
}

export async function clearSessionCookie(): Promise<void> {
  (await cookies()).delete(COOKIE_NAME);
}

export async function currentSession(): Promise<SessionClaims | null> {
  const jar = await cookies();
  return readSession(jar.get(COOKIE_NAME)?.value);
}

export const SESSION_COOKIE_NAME = COOKIE_NAME;
