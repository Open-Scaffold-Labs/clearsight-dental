/**
 * POST /api/analyze
 *
 * Proxies an image analysis request from the authenticated browser session
 * to the Fly.io GPU backend. The edge is the real authn/authz boundary:
 *  - Session cookie verified (middleware + currentSession)
 *  - BAA acceptance enforced (middleware)
 *  - tenant_id + user_id stamped on the request from the trusted session
 *
 * The backend receives only a shared secret plus those server-attested IDs.
 */
import { NextRequest, NextResponse } from "next/server";
import { currentSession } from "@/lib/session";

export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL;
const SHARED_API_SECRET = process.env.SHARED_API_SECRET;

export async function POST(req: NextRequest) {
  if (!BACKEND_URL || !SHARED_API_SECRET) {
    return NextResponse.json({ error: "backend not configured" }, { status: 500 });
  }

  const session = await currentSession();
  if (!session) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }
  if (!session.baa) {
    return NextResponse.json({ error: "baa_required" }, { status: 403 });
  }

  const incoming = await req.formData();
  const image = incoming.get("image");
  if (!(image instanceof File)) {
    return NextResponse.json({ error: "image field required" }, { status: 400 });
  }

  // Re-build the form on the server, stamping tenant/user from the session.
  const outgoing = new FormData();
  outgoing.set("image", image, image.name || "upload.jpg");
  const modality = String(incoming.get("modality") || "opg");
  outgoing.set("modality", modality);
  const prompt = incoming.get("prompt");
  if (typeof prompt === "string" && prompt.trim()) outgoing.set("prompt", prompt);
  outgoing.set("tenant_id", session.tid);
  outgoing.set("user_id", session.uid);

  const requestId = crypto.randomUUID();

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/analyze`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${SHARED_API_SECRET}`,
        "X-Request-Id": requestId,
      },
      body: outgoing,
    });
  } catch (e) {
    console.error("analyze_proxy_failed", e);
    return NextResponse.json({ error: "backend unreachable" }, { status: 502 });
  }

  const text = await upstream.text();
  let payload: unknown = text;
  try { payload = JSON.parse(text); } catch { /* keep as text */ }

  return NextResponse.json(payload, { status: upstream.status });
}
