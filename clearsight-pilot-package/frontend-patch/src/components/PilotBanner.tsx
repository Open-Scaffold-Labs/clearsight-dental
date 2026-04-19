/**
 * PilotBanner — persistent amber banner rendered at the top of every page
 * inside the authenticated app shell. Reinforces the "pilot, not diagnostic,
 * clinician review required" framing on every screen so a clinician never
 * forgets the context they are in.
 */
export default function PilotBanner({ practiceName }: { practiceName: string }) {
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <div>
          <span className="font-semibold">Pilot release.</span>{" "}
          ClearSight Dental output is a <em>non-diagnostic clinical support tool</em> —
          clinician review is required before any treatment decision. Not a substitute
          for professional judgment. BAA on file for {practiceName}.
        </div>
        <a
          href="/pilot-terms"
          className="whitespace-nowrap rounded-md border border-amber-400 bg-white px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
        >
          Pilot terms
        </a>
      </div>
    </div>
  );
}
