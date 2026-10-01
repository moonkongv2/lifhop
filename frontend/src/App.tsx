import { Link, Outlet } from "react-router";

function App() {
  return (
    <main>
      <h1>lifhop</h1>

      <nav>
        <Link to="/login">Login</Link>{" "}
        <Link to="/entries">Entries</Link>
        <Link to="/imports">Import</Link>
      </nav>

      <hr />

      <Outlet />
    </main>
  );
}

export default App;
