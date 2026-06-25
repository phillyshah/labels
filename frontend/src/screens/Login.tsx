import { useState } from "react";
import { login as apiLogin, ApiError } from "../lib/api";

export function Login({
  onAuthenticated,
}: {
  onAuthenticated: (token: string, role: string) => void;
}) {
  // V1 uses a single shared password; email is captured but ignored (placeholder for the
  // per-reviewer Supabase Auth swap, and used by the Playwright e2e harness).
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      const res = await apiLogin(password);
      onAuthenticated(res.token, res.role);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setError("incorrect password");
      } else {
        setError("could not reach the server — try again");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-100 px-4">
      <div className="w-full max-w-sm rounded-lg border border-gray-300 bg-white p-6 shadow-sm">
        <h1 className="mb-1 text-lg font-bold text-gray-900">Label Approval</h1>
        <p className="mb-5 text-sm text-gray-600">
          Internal quality review tool. Enter the shared password.
        </p>
        <label
          htmlFor="email"
          className="mb-1 block text-sm font-medium text-gray-700"
        >
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-3 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
        />
        <label
          htmlFor="password"
          className="mb-1 block text-sm font-medium text-gray-700"
        >
          Password
        </label>
        <input
          id="password"
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          className="mb-3 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
        />
        {error && (
          <p className="mb-3 text-sm font-medium text-red-700" role="alert">
            {error}
          </p>
        )}
        <button
          onClick={submit}
          disabled={busy || !password}
          className="w-full rounded bg-gray-900 px-3 py-2 text-sm font-semibold text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </div>
    </div>
  );
}
