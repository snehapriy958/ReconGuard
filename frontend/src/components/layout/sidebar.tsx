"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { NAV_ITEMS, isNavItemActive } from "./nav-config";
import { cn } from "@/lib/utils";

interface SidebarProps {
  className?: string;
  onNavigate?: () => void;
}

export function Sidebar({ className, onNavigate }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-slate-200 bg-white",
        className
      )}
      aria-label="Main Navigation"
    >
      {/* Brand Header */}
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-100 px-6">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-white shadow-xs">
          <ShieldCheck className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="flex flex-col">
          <span className="font-bold text-base tracking-tight text-slate-950">
            ReconGuard
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Reconciliation Engine
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          Platform
        </div>
        <nav className="space-y-1" aria-label="Sidebar">
          {NAV_ITEMS.map((item) => {
            const active = isNavItemActive(item.href, pathname);
            const Icon = item.icon;

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-slate-900",
                  active
                    ? "bg-slate-950 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors",
                    active
                      ? "text-white"
                      : "text-slate-400 group-hover:text-slate-700"
                  )}
                  aria-hidden="true"
                />
                <span className="truncate">{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* System Status Footer */}
      <div className="border-t border-slate-100 p-4">
        <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
            <span className="text-xs font-medium text-slate-700">
              Bounded Autonomy
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-4 text-slate-400">
            Automated + human oversight pipeline
          </p>
        </div>
      </div>
    </aside>
  );
}
