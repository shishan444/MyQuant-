import {
  createBrowserRouter,
  Navigate,
  RouterProvider,
} from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppLayout } from "@/components/layout/AppLayout";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Lab } from "@/pages/Lab";
import { Evolution } from "@/pages/Evolution";
import { Strategies } from "@/pages/Strategies";
import { Trading } from "@/pages/Trading";
import { DataManagement } from "@/pages/DataManagement";
import { Settings } from "@/pages/Settings";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/lab" replace /> },
      { path: "/lab", element: <ErrorBoundary><Lab /></ErrorBoundary> },
      { path: "/evolution", element: <ErrorBoundary><Evolution /></ErrorBoundary> },
      { path: "/strategies", element: <ErrorBoundary><Strategies /></ErrorBoundary> },
      { path: "/trading", element: <ErrorBoundary><Trading /></ErrorBoundary> },
      { path: "/data", element: <ErrorBoundary><DataManagement /></ErrorBoundary> },
      { path: "/settings", element: <ErrorBoundary><Settings /></ErrorBoundary> },
    ],
  },
]);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
