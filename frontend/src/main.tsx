import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "./index.css";

import App from "./App";
import LoginPage from "./pages/LoginPage";
import EntryListPage from "./pages/EntryListPage";
import EntryCreatePage from "./pages/EntryCreatePage";
import EntryDetailPage from "./pages/EntryDetailPage";

const queryClient = new QueryClient();

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
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
