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

    setLoading(true);
    setError("");

    try {
      const form = new URLSearchParams();
      form.append("username", email);
      form.append("password", password);

      const response = await fetch("/api/auth/login", {
        method: "POST",
        body: form,
      });

      if (!response.ok) {
        throw new Error("로그인에 실패했어.");
      }

      const data: TokenResponse = await response.json();

      queryClient.clear();
      localStorage.setItem("access_token", data.access_token);

      navigate("/entries");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "알 수 없는 오류가 발생했어."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h2>Login</h2>

      <form onSubmit={handleSubmit}>
        <div>
          <label>
            Email
            <input
              type="email"
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
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "로그인 중..." : "로그인"}
        </button>
      </form>

      {error && <p>{error}</p>}
    </>
  );
}

export default LoginPage;
