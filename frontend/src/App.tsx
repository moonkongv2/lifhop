import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { clearSession, useAccessToken } from "./utils/session";
import { NavLink, Link, Outlet, useLocation, useNavigate } from "react-router";
import Icon from "./components/Icon";
import { resolveEntryContext } from "./utils/entryNavigation";

function App() {
  const location = useLocation();
  const token = useAccessToken();
  const cache = useQueryClient();
  const navigate = useNavigate();
  useEffect(() => {
    if (!token) {
      cache.clear();
      if (location.pathname !== "/login") navigate("/login", { replace: true });
    }
  }, [token, cache, navigate, location.pathname]);
  const activeView = location.pathname.startsWith("/entries/") || location.pathname === "/sessions/codex" || location.pathname === "/repositories/github"
    ? resolveEntryContext(location.search, location.state).pathname : location.pathname;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="app-header">
        <Link className="brand" to="/entries" aria-label="lifhop home">
          <span className="brand-mark"><Icon name="archive" /></span>
          <span>lifhop<span className="brand-caption">Your personal archive</span></span>
        </Link>
        <nav className="main-nav" aria-label="Main navigation">
          <Link to="/entries" className={activeView === "/entries" ? "active" : ""} aria-current={activeView === "/entries" ? "page" : undefined}><Icon name="archive" />Entries</Link>
          <Link to="/search" className={activeView === "/search" ? "active" : ""} aria-current={activeView === "/search" ? "page" : undefined}><Icon name="search" />Search</Link>
          <NavLink to="/imports" className={({ isActive }) => isActive || location.pathname.startsWith("/import-jobs/") ? "active" : ""}><Icon name="import" />Import</NavLink>
          <NavLink to="/sources"><Icon name="sources" />Sources</NavLink>
        </nav>
        {token ? <button className="account-link" onClick={() => { clearSession(); cache.clear(); navigate("/login", { replace: true }); }}>Logout</button>
          : <NavLink className="account-link" to="/login">Login</NavLink>}
      </header>
      <main id="main-content" className="app-content" tabIndex={-1}><Outlet /></main>
      <footer className="app-footer">A little context, kept for later.<span>lifhop · Personal archive</span></footer>
    </div>
  );
}
export default App;
