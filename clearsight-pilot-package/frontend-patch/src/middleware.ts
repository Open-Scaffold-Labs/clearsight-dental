/**
 * Route protection for the ClearSight Dental pilot.
 *
 * Enforces:
 *  1. Authenticated session for all /app/* routes
 *  2. BAA acceptance before any PHI-touching route (/app/analyze)
 *
 * This replaces the Supabase auth middleware in the upstream clearsight-dental
 * scaffold. Sessions are HMAC-signed JWTs in an httpOnly cookie; no third-party
 * auth vendor.
 */
import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

const SESSION_COOKIE = "cs_session";

const PUBLIC_ROUTES = new Set<string>([
  "/",
  "/login",
  "/baa",
  "/privacy",
  "/terms",
  "/favicon.ico",
]);

const PHI_ROUTES = ["/app/analyze"];

function isPublic(pathname: string): boolean {
  if (PUBLIC_ROUTES.has(pathname)) return true;
  if (pathname.startsWith("/api/auth")) return true;
  if (pathname.startsWith("/_next") || pathname.startsWith("/static")) return true;
  return false;
}

async function verify(token: string | undefined) {
  if (!token || !process.env.SESSION_SECRET) return null;
  try {
    const { payload } = await jwtVerify(
      token,
      new TextEncoder().encode(process.env.SESSION_SECRET)
    );
    return payload as { uid: string; tid: string; baa: boolean; role: string };
  } catch {
    return null;
  }
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (isPublic(pathname)) return NextResponse.next();

  const token = req.cookies.get(SESSION_COOKIE)?.value;
  const session = await verify(token);

  if (!session) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (PHI_ROUTES.some((p) => pathname.startsWith(p)) && !session.baa) {
    const url = req.nextUrl.clone();
    url.pathname = "/baa";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
