"use client";

import { Menu, ShieldCheck } from "lucide-react";
import { Breadcrumbs } from "./breadcrumbs";

interface HeaderProps {
  onOpenMobileNav: () => void;
}

export function Header({ onOpenMobileNav }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white/95 px-4 sm:px-6 backdrop-blur-xs">
      {/* Mobile Menu Trigger & Mobile Brand */}
      <div className="flex items-center gap-3 md:hidden">
        <button
          type="button"
          onClick={onOpenMobileNav}
          aria-label="Open navigation menu"
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-slate-900"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>

        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-950 text-white shadow-xs">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          </div>
          <span className="font-bold text-sm tracking-tight text-slate-950">
            ReconGuard
          </span>
        </div>
      </div>

      {/* Desktop Breadcrumbs */}
      <div className="hidden md:flex md:items-center">
        <Breadcrumbs />
      </div>

      {/* Right context tag */}
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
          Financial Operations
        </span>
      </div>
    </header>
  );
}
