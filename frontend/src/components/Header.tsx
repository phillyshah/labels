import { NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { health } from "../lib/api";
import type { VersionInfo } from "../lib/types";
import { WhatsNew } from "./WhatsNew";
import { GuideDrawer } from "./GuideDrawer";

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    "px-3 py-2 text-sm font-medium rounded",
    isActive
      ? "bg-gray-900 text-white"
      : "text-gray-700 hover:bg-gray-200",
  ].join(" ");
}

export function Header({
  onLogout,
  version,
}: {
  onLogout: () => void;
  version: VersionInfo | null;
}) {
  const [status, setStatus] = useState<string | null>(null);
  const [rulesVersion, setRulesVersion] = useState<string | null>(null);
  const [whatsNewOpen, setWhatsNewOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);

  useEffect(() => {
    let active = true;
    health()
      .then((h) => {
        if (!active) return;
        setStatus(h?.status ?? "unknown");
        setRulesVersion(h?.rules_version ?? null);
      })
      .catch(() => active && setStatus("unreachable"));
    return () => {
      active = false;
    };
  }, []);

  const dotColor =
    status === "ok"
      ? "bg-green-500"
      : status === null
        ? "bg-gray-400"
        : "bg-red-500";

  return (
    <header className="border-b border-gray-300 bg-white">
      <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
        <div className="mr-4 font-bold text-gray-900">Label Approval</div>
        <nav className="flex gap-1">
          <NavLink to="/new" className={navClass}>
            New Review
          </NavLink>
          <NavLink to="/history" className={navClass}>
            History
          </NavLink>
          <NavLink to="/training" className={navClass}>
            Training
          </NavLink>
          <NavLink to="/rules" className={navClass}>
            Rules
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={() => setWhatsNewOpen(true)}
            className="rounded px-2 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100"
          >
            What's New{version ? ` · v${version.version}` : ""}
          </button>
          <button
            onClick={() => setGuideOpen(true)}
            aria-label="User guide"
            title="User guide"
            className="flex h-7 w-7 items-center justify-center rounded-full border border-gray-300 text-sm font-bold text-gray-600 hover:bg-gray-100"
          >
            ?
          </button>
          <span
            className="flex items-center gap-1.5 text-xs text-gray-600"
            title={`backend status: ${status ?? "checking"}${
              rulesVersion ? ` · rules ${rulesVersion}` : ""
            }`}
          >
            <span className={`h-2.5 w-2.5 rounded-full ${dotColor}`} />
            {status ?? "checking…"}
          </span>
          <button
            onClick={onLogout}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Log out
          </button>
        </div>
      </div>
      <WhatsNew
        open={whatsNewOpen}
        onClose={() => setWhatsNewOpen(false)}
        info={version}
      />
      <GuideDrawer open={guideOpen} onClose={() => setGuideOpen(false)} />
    </header>
  );
}
