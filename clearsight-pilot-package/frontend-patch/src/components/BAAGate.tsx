/**
 * BAAGate — full-page interstitial that blocks PHI-touching UI until the
 * currently signed-in user records BAA + Clinical Pilot Agreement acceptance.
 *
 * Render this in /app/layout.tsx around the app shell, or wrap individual
 * protected pages. The middleware (src/middleware.ts) also enforces the gate
 * on the server side — this component is the client-side UX, not the
 * authorization boundary.
 */
"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

interface Props {
  baaVersion: string;
  cpaVersion: string;
  practiceName: string;
  userEmail: string;
}

export default function BAAGate({
  baaVersion,
  cpaVersion,
  practiceName,
  userEmail,
}: Props) {
  const [readBaa, setReadBaa] = useState(false);
  const [readCpa, setReadCpa] = useState(false);
  const [agreeBaa, setAgreeBaa] = useState(false);
  const [agreeCpa, setAgreeCpa] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const router = useRouter();
  const params = useSearchParams();

  const canSubmit = readBaa && readCpa && agreeBaa && agreeCpa && !submitting;

  async function handleAccept() {
    setSubmitting(true);
    setErr(null);
    try {
      const res = await fetch("/api/baa/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baa_version: baaVersion, cpa_version: cpaVersion }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || "Acceptance failed; please try again.");
      }
      const next = params.get("next") || "/app";
      router.replace(next);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
      <div className="w-full max-w-2xl overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="bg-indigo-600 px-8 py-5 text-white">
          <h1 className="text-lg font-semibold">Before you continue</h1>
          <p className="text-sm text-indigo-100">
            ClearSight Dental is in a pilot — not a commercial release.
          </p>
        </div>

        <div className="px-8 py-6 text-sm text-slate-700">
          <p className="mb-4">
            Hello <span className="font-medium">{userEmail}</span> — because
            ClearSight Dental will process protected health information on behalf
            of <span className="font-medium">{practiceName}</span>, HIPAA requires
            us to have a signed Business Associate Agreement (BAA) and a Clinical
            Pilot Agreement (CPA) in place before you analyze any patient images.
          </p>
          <p className="mb-4">
            The two documents below are the versions your practice executed
            before enrollment in the pilot. Please review each and confirm that
            you have read it. The app will not load analysis screens until both
            confirmations are recorded against your user account.
          </p>

          <Document
            title={`Business Associate Agreement — ${baaVersion}`}
            href={`/legal/BAA-${baaVersion}.pdf`}
            read={readBaa}
            onRead={() => setReadBaa(true)}
          />
          <label className="mb-5 flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={agreeBaa}
              disabled={!readBaa}
              onChange={(e) => setAgreeBaa(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              I have reviewed the Business Associate Agreement ({baaVersion}) and
              confirm that I am authorized to attest to its acceptance on behalf
              of {practiceName}.
            </span>
          </label>

          <Document
            title={`Clinical Pilot Agreement — ${cpaVersion}`}
            href={`/legal/CPA-${cpaVersion}.pdf`}
            read={readCpa}
            onRead={() => setReadCpa(true)}
          />
          <label className="mb-5 flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={agreeCpa}
              disabled={!readCpa}
              onChange={(e) => setAgreeCpa(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              I have reviewed the Clinical Pilot Agreement ({cpaVersion}) and
              understand that ClearSight Dental output is for clinician review
              only and is not a diagnosis or treatment recommendation.
            </span>
          </label>

          {err && (
            <div className="mb-4 rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              {err}
            </div>
          )}

          <div className="flex items-center justify-end gap-3">
            <a
              href="/logout"
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Sign out
            </a>
            <button
              onClick={handleAccept}
              disabled={!canSubmit}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {submitting ? "Recording…" : "Accept and continue"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Document({
  title,
  href,
  read,
  onRead,
}: {
  title: string;
  href: string;
  read: boolean;
  onRead: () => void;
}) {
  return (
    <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-medium text-slate-900">{title}</div>
          <div className="text-xs text-slate-500">Opens in a new tab</div>
        </div>
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          onClick={onRead}
          className={`rounded-md px-3 py-1.5 text-xs font-medium ${
            read
              ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
              : "bg-indigo-600 text-white hover:bg-indigo-700"
          }`}
        >
          {read ? "Reviewed" : "Open document"}
        </a>
      </div>
    </div>
  );
}
