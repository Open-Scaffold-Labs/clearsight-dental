# Frontend Patch — Integration Guide

These files are designed to drop into an existing Next.js 15 (App Router) project that today uses Supabase Auth. The patch removes the Supabase dependency and replaces it with:

- **Magic-link authentication** backed by a Neon Postgres `users` + `magic_tokens` table
- **Signed JWT session cookie** (`cs_session`, 8h absolute, HS256)
- **BAA / CPA acceptance gate** — full-page interstitial that blocks `/app/analyze` until the logged-in user records acceptance for the current document versions
- **Shared-secret proxy** from the Vercel edge to the Fly.io GPU backend

## Install

From the root of the existing `clearsight-dental` repo:

```bash
# 1. Copy the patch files over the existing tree
cp -R clearsight-pilot-package/frontend-patch/src/lib/* src/lib/
cp -R clearsight-pilot-package/frontend-patch/src/components/* src/components/
cp -R clearsight-pilot-package/frontend-patch/src/app/api/* src/app/api/
cp clearsight-pilot-package/frontend-patch/src/middleware.ts src/middleware.ts

# 2. Install runtime dependencies
pnpm add @neondatabase/serverless jose resend
pnpm remove @supabase/supabase-js @supabase/ssr  # if present

# 3. Set environment variables per .env.example
cp clearsight-pilot-package/frontend-patch/.env.example .env.local
```

## Wire the gate

In `src/app/app/layout.tsx` (the authenticated app shell), render `PilotBanner` and `BAAGate`:

```tsx
import BAAGate from "@/components/BAAGate";
import PilotBanner from "@/components/PilotBanner";
import { currentSession } from "@/lib/session";
import { redirect } from "next/navigation";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await currentSession();
  if (!session) redirect("/login");

  return (
    <>
      <PilotBanner practiceName="DIA Basher DDS" />
      {!session.baa && (
        <BAAGate
          baaVersion={process.env.BAA_VERSION || "v1.0"}
          cpaVersion={process.env.CPA_VERSION || "v1.0"}
          practiceName="DIA Basher DDS"
          userEmail="<look up from session.uid>"
        />
      )}
      {children}
    </>
  );
}
```

## Publish the legal PDFs

Place the counsel-approved BAA and CPA PDFs under `public/legal/`:

```
public/legal/BAA-v1.0.pdf
public/legal/CPA-v1.0.pdf
```

These are the exact documents the BAA gate links to. Changing the versions requires a coordinated update of:

1. The PDF file in `public/legal/`
2. The `BAA_VERSION` / `CPA_VERSION` environment variables
3. A notice to existing users — the gate will re-appear once the version changes because no `baa_acceptance` row exists for the new pair

## Not in scope for this patch

- `/app/analyze` UI itself — assumed to already exist in the upstream repo and to `POST` a `FormData` with `image` + optional `modality` + `prompt` fields to `/api/analyze`
- `/login` page UI
- `/baa` route — the middleware redirects here; render `<BAAGate />` at the top of that route too, for users who hit a protected page before accepting
