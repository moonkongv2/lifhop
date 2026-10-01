import { Link, Outlet } from "react-router";

function App() {
  return (
    <main>
      <h1>lifhop</h1>

      <nav>
        <Link to="/login">Login</Link>{" "}
        <Link to="/entries">Entries</Link>
        <Link to="/imports">가져오기</Link>
      </nav>

      <hr />

      <Outlet />
    </main>
  );
}

export default App;
