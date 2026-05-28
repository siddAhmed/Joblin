import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const NAV = [
  { label: "Dashboard", icon: "◼", path: "/" },
  { label: "Matches", icon: "★", path: "/matches" },
  { label: "All Jobs", icon: "≡", path: "/jobs" },
  { label: "Companies", icon: "⊞", path: "/companies", warn: true },
  { label: "Runs", icon: "▶", path: "/runs" },
  { label: "Usage", icon: "◈", path: "/usage" },
  { label: "Settings", icon: "⚙", path: "/settings" },
] as const;

export function Sidebar({ quarantineCount = 0 }: { quarantineCount?: number }) {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sidebar_collapsed") === "true";
  });

  useEffect(() => {
    localStorage.setItem("sidebar_collapsed", String(collapsed));
  }, [collapsed]);

  if (collapsed) {
    return (
      <aside className="flex flex-col items-center w-11 bg-[#111] border-r border-[#1e1e1e] shrink-0 py-3">
        <div className="flex flex-col items-center pb-3 border-b border-[#1e1e1e] w-full mb-2 gap-1.5">
          <img src="/joblin_mascot.png" alt="Joblin" className="w-7 h-7 rounded object-contain" />
          <button onClick={() => setCollapsed(false)} title="Expand sidebar"
            className="text-[#555] hover:text-[#888] text-xs border border-[#2a2a2a] rounded w-7 h-5 flex items-center justify-center">
            &rsaquo;
          </button>
        </div>
        {NAV.map((item) => (
          <NavLink key={item.path} to={item.path} end={item.path === "/"}
            title={item.label}
            className={({ isActive }) =>
              cn("w-8 h-7 flex items-center justify-center rounded text-sm mb-0.5 relative",
                isActive ? "bg-[#1a1a1a] text-[#e5e5e5]" : "text-[#555] hover:text-[#888]")
            }
          >
            {item.icon}
            {"warn" in item && item.warn && quarantineCount > 0 && (
              <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-orange-500" />
            )}
          </NavLink>
        ))}
      </aside>
    );
  }

  return (
    <aside className="flex flex-col w-44 bg-[#111] border-r border-[#1e1e1e] shrink-0 py-3">
      <div className="flex items-center justify-between px-3 pb-3 border-b border-[#1e1e1e] mb-2">
        <div className="flex items-center gap-1.5">
          <img src="/joblin_mascot.png" alt="Joblin" className="w-6 h-6 rounded object-contain" />
          <span className="font-bold text-sm text-[#e5e5e5]">Job<span className="text-[#4e9eff]">lin</span></span>
        </div>
        <button onClick={() => setCollapsed(true)}
          className="text-[#555] hover:text-[#888] text-xs border border-[#2a2a2a] rounded w-5 h-5 flex items-center justify-center">
          &lsaquo;
        </button>
      </div>
      {NAV.map((item) => (
        <NavLink key={item.path} to={item.path} end={item.path === "/"}
          className={({ isActive }) =>
            cn("flex items-center gap-2 px-3 py-1.5 text-xs",
              isActive
                ? "text-[#e5e5e5] bg-[#1a1a1a] border-l-2 border-[#4e9eff] pl-[10px]"
                : "text-[#666] hover:text-[#999]")
          }
        >
          <span className="w-3.5 text-center">{item.icon}</span>
          {item.label}
          {"warn" in item && item.warn && quarantineCount > 0 && (
            <span className="ml-auto bg-orange-900/50 text-orange-400 text-[10px] px-1 rounded-full">{quarantineCount}</span>
          )}
        </NavLink>
      ))}
      <div className="mt-auto px-3 pt-2 border-t border-[#1a1a1a] text-[9px] text-[#444]">Joblin</div>
    </aside>
  );
}
