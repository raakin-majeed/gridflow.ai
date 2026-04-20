"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  label: string;
  icon: string;
};

const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: "[H]" },
  { href: "/forecast", label: "Forecast", icon: "[C]" },
  { href: "/simulator", label: "Simulator", icon: "[S]" },
  { href: "/anomalies", label: "Anomalies", icon: "[!]" },
  { href: "/analyst", label: "AI Analyst", icon: "[AI]" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col justify-between p-4">
      <div>
        <div className="mb-8 border-b border-[#1a2a1a] pb-4">
          <p className="text-lg font-bold text-[#00ff88]">GRIDFLOW AI</p>
          <p className="mt-1 text-xs text-[#cccccc]">India Grid Intelligence</p>
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 border-l-2 px-3 py-2 text-sm transition ${
                  active
                    ? "border-[#00ff88] text-[#00ff88]"
                    : "border-transparent text-[#cccccc] hover:text-white"
                }`}
              >
                <span className="w-9 text-xs">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
      <p className="text-xs text-[#cccccc]">POSOCO · 503 days · Prophet ML</p>
    </div>
  );
}
