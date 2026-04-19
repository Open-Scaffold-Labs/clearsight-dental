/**
 * Postgres client for the Vercel edge (Neon serverless driver).
 *
 * Uses the HTTP transport which works on Vercel Edge Runtime. All writes
 * from the frontend go through here; PHI never lands on the Vercel side.
 */
import { neon } from "@neondatabase/serverless";

const url = process.env.DATABASE_URL;
if (!url) {
  throw new Error("DATABASE_URL is not set");
}

export const sql = neon(url);

/** SHA-256 hex helper — Web Crypto API, works on Edge and Node runtimes. */
export async function sha256Hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
