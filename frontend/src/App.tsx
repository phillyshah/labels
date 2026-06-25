import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import {
  clearSession,
  getToken,
  getVersion,
  setSession,
  setUnauthorizedHandler,
} from "./lib/api";
import type { VersionInfo } from "./lib/types";
import { Login } from "./screens/Login";
import { Header } from "./components/Header";
import { NewReview } from "./screens/NewReview";
import { Scorecard } from "./screens/Scorecard";
import { History } from "./screens/History";
import { Rules } from "./screens/Rules";
import { Training } from "./screens/Training";

export default function App() {
  const navigate = useNavigate();
  const [token, setToken] = useState<string | null>(() => getToken());
  const [version, setVersion] = useState<VersionInfo | null>(null);

  useEffect(() => {
    getVersion()
      .then(setVersion)
      .catch(() => setVersion(null));
  }, []);

  // Any 401 from the API client clears the session and drops us to Login.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null);
      navigate("/new");
    });
  }, [navigate]);

  const handleAuthenticated = useCallback(
    (newToken: string, role: string) => {
      setSession(newToken, role);
      setToken(newToken);
      navigate("/new");
    },
    [navigate],
  );

  const handleLogout = useCallback(() => {
    clearSession();
    setToken(null);
    navigate("/new");
  }, [navigate]);

  if (!token) {
    return <Login onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header onLogout={handleLogout} version={version} />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Navigate to="/new" replace />} />
          <Route path="/new" element={<NewReview />} />
          <Route path="/submissions/:id" element={<Scorecard />} />
          <Route path="/history" element={<History />} />
          <Route path="/training" element={<Training />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="*" element={<Navigate to="/new" replace />} />
        </Routes>
      </main>
      <footer className="border-t border-gray-200 py-3 text-center text-xs text-gray-400">
        Label Approval{version ? ` · v${version.version}` : ""}
      </footer>
    </div>
  );
}
