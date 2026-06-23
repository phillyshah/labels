import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import {
  clearSession,
  getToken,
  setSession,
  setUnauthorizedHandler,
} from "./lib/api";
import { Login } from "./screens/Login";
import { Header } from "./components/Header";
import { NewReview } from "./screens/NewReview";
import { Scorecard } from "./screens/Scorecard";
import { History } from "./screens/History";
import { Rules } from "./screens/Rules";

export default function App() {
  const navigate = useNavigate();
  const [token, setToken] = useState<string | null>(() => getToken());

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
    <div className="min-h-screen">
      <Header onLogout={handleLogout} />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/new" replace />} />
          <Route path="/new" element={<NewReview />} />
          <Route path="/submissions/:id" element={<Scorecard />} />
          <Route path="/history" element={<History />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="*" element={<Navigate to="/new" replace />} />
        </Routes>
      </main>
    </div>
  );
}
