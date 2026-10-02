import { assertCurrentSession, getAccessToken, setAccessToken } from "../utils/session";
import Icon from "../components/Icon";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router";

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (loading) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) || !password) {
      setError("Enter a valid email address and password."); return;
    }
    const previousToken = getAccessToken();
    setLoading(true);
    setError("");

    try {
      const form = new URLSearchParams();
      form.append("username", email.trim());
      form.append("password", password);

      const response = await fetch("/api/auth/login", {
        method: "POST",
        body: form,
      });

      if (!response.ok) {
        throw new Error("Login failed.");
      }

      const data: TokenResponse = await response.json();

      if (previousToken) assertCurrentSession(previousToken);
      else if (getAccessToken()) throw new Error("Your session has changed. Please try again.");
      queryClient.clear();
      setAccessToken(data.access_token);

      navigate("/entries");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel page-card login-card">
      <span className="brand-mark"><Icon name="archive" /></span>
      <p className="eyebrow">Welcome back</p>
      <h2>Login</h2>
      <p>Your records, right where you left them.</p>

      <form noValidate onSubmit={handleSubmit}>
        <div>
          <label>
            Email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
        </div>

        <div>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Logging in..." : "Log in"}
        </button>
      </form>

      {sessionStorage.getItem("session_notice") && <p role="alert">{sessionStorage.getItem("session_notice")}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export default LoginPage;
