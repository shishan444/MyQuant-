import { Outlet } from "react-router";
import { Sidebar } from "./Sidebar";
import { Header } from "./Sidebar";
import { Toaster } from "sonner";

export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          style: { width: "360px" },
          className: "glass-card",
        }}
      />
    </div>
  );
}
