import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "./index.css";

import ImportsPage from "./pages/ImportsPage";
import ImportJobPage from "./pages/ImportJobPage";
import SourcesPage from "./pages/SourcesPage";
import App from "./App";
import ConversationsPage from "./pages/ConversationsPage";
import ConversationPage from "./pages/ConversationPage";
import LoginPage from "./pages/LoginPage";
import EntryListPage from "./pages/EntryListPage";
import EntrySearchPage from "./pages/EntrySearchPage";
import EntryCreatePage from "./pages/EntryCreatePage";
import EntryDetailPage from "./pages/EntryDetailPage";
import CodexSessionPage from "./pages/CodexSessionPage";
import GitHubRepositoryPage from "./pages/GitHubRepositoryPage";
import PassagePage from "./pages/PassagePage";

const queryClient = new QueryClient();

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { path: "citations", element: <PassagePage /> },
      { path: "conversations", element: <ConversationsPage /> },
      { path: "conversations/:id", element: <ConversationPage /> },
      { path: "passages/:id", element: <PassagePage /> },
      { path: "semantic/slices/:id", element: <PassagePage semantic /> },
      { path: "repositories/github", element: <GitHubRepositoryPage /> },
      { path: "sessions/codex", element: <CodexSessionPage /> },
      { path: "search", element: <EntrySearchPage /> },
      { path: "sources", element: <SourcesPage /> },
      { path: "imports", element: <ImportsPage /> },
      { path: "import-jobs/:id", element: <ImportJobPage /> },
      {
        path: "login",
        element: <LoginPage />,
      },
      {
        path: "entries",
        element: <EntryListPage />,
      },
      {
        path: "entries/new",
        element: <EntryCreatePage />,
      },
      {
        path: "entries/:id",
        element: <EntryDetailPage />,
      },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);
