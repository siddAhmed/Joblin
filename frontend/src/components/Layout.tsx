import { useQuery } from "@tanstack/react-query";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { statsApi } from "@/api/stats";

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/matches": "Matches",
  "/jobs": "All Jobs",
  "/companies": "Companies",
  "/runs": "Runs",
  "/usage": "Usage",
  "/settings": "Settings",
};

export function Layout() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: statsApi.get, refetchInterval: 30000 });
  const location = useLocation();
  const title = Object.entries(TITLES).find(([k]) => location.pathname === k || location.pathname.startsWith(k + "/"))?.[1] ?? "Joblin";

  return (
    <div className="flex h-screen overflow-hidden bg-[#0d0d0d]">
      <Sidebar quarantineCount={stats?.quarantine_count ?? 0} />
      <main className="flex flex-col flex-1 overflow-hidden">
        <Topbar title={title} />
        <div className="flex-1 overflow-auto p-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
