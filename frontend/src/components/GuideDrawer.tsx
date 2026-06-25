import { useEffect, type ReactNode } from "react";

// Quick in-app user guide, opened from the header "?" button as a right-side
// drawer. Closes via the X, a backdrop click, or Esc.
export function GuideDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
    >
      <aside className="h-full w-full max-w-md overflow-y-auto bg-white shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-gray-200 bg-white px-5 py-3">
          <h2 className="text-base font-bold text-gray-900">User guide</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            ✕
          </button>
        </div>
        <div className="space-y-6 px-5 py-4 text-sm leading-relaxed text-gray-700">
          <Section title="1. Run a review">
            On <b>New Review</b>, drag each document into its slot: the label
            form, batch CoC, sterile CoC, and sterile lot record are required;
            the two release-verification documents are optional. The tool checks
            each file is the expected type and warns you before running if
            something looks mismatched. Click <b>Run checks</b>.
          </Section>
          <Section title="2. Read the verdict">
            You get an overall <b>APPROVE</b>, <b>APPROVE WITH FLAGS</b>, or{" "}
            <b>REJECT</b>, plus checks <b>A–G</b> — each marked PASS, FAIL, FLAG,
            or DEFERRED with a one-line reason. DEFERRED means a canonical value
            isn't configured yet (see <b>Rules</b>). Download the{" "}
            <b>approval bundle</b> or <b>discrepancy report</b> PDF to hand off.
          </Section>
          <Section title="3. History">
            The <b>History</b> tab lists past submissions and their verdicts; open
            any one to see its full scorecard again.
          </Section>
          <Section title="4. Train the tool">
            On <b>Training</b>, re-run a past batch and tell the tool how it did.
            Either rate each check by hand (correct / partial / wrong with a
            note), or turn on <b>I have the expected results</b>, enter the known
            verdict and per-check outcomes, and <b>Auto-score</b> in one click.
            The accuracy dashboard updates as you go.
          </Section>
          <Section title="5. Suggest rule improvements">
            From your disagreements, <b>Suggest improvements</b> drafts concrete,
            reviewable rule changes — it only suggests, nothing is applied
            automatically. (Requires an Anthropic API key on the server.)
          </Section>
          <Section title="6. Rules">
            The <b>Rules</b> tab is where you configure the data-driven checks.
            Each section (GTIN, description, IFU, static label content) has an
            Active/Deferred toggle and fields for its reference values — turn one
            on and a previously DEFERRED check starts running for real. Leave it
            off and the reviewer keeps signing off on it manually. Every change is
            recorded in the audit log.
          </Section>
        </div>
      </aside>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 text-sm font-semibold text-gray-900">{title}</h3>
      <p>{children}</p>
    </section>
  );
}
