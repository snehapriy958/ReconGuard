"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";

interface Crumb {
  label: string;
  href?: string;
  isMono?: boolean;
}

export function Breadcrumbs() {
  const pathname = usePathname();

  const crumbs: Crumb[] = [];

  if (pathname === "/") {
    crumbs.push({ label: "Dashboard" });
  } else if (pathname === "/upload") {
    crumbs.push({ label: "Upload" });
  } else if (pathname === "/batches") {
    crumbs.push({ label: "Batches" });
  } else if (pathname.startsWith("/batches/")) {
    const parts = pathname.split("/").filter(Boolean);
    // parts[0] is 'batches', parts[1] is batchId, parts[2] might be 'decisions'
    crumbs.push({ label: "Batches", href: "/batches" });
    if (parts[1]) {
      const batchId = decodeURIComponent(parts[1]);
      if (parts[2] === "decisions") {
        crumbs.push({ label: batchId, href: `/batches/${parts[1]}`, isMono: true });
        crumbs.push({ label: "Decisions" });
      } else {
        crumbs.push({ label: batchId, isMono: true });
      }
    }
  } else if (pathname.startsWith("/decisions/")) {
    const parts = pathname.split("/").filter(Boolean);
    crumbs.push({ label: "Batches", href: "/batches" });
    crumbs.push({ label: "Decisions" });
    if (parts[1]) {
      crumbs.push({ label: decodeURIComponent(parts[1]), isMono: true });
    }
  } else if (pathname === "/reviews") {
    crumbs.push({ label: "Reviews" });
  } else if (pathname.startsWith("/reviews/")) {
    const parts = pathname.split("/").filter(Boolean);
    crumbs.push({ label: "Reviews", href: "/reviews" });
    if (parts[1]) {
      crumbs.push({ label: decodeURIComponent(parts[1]), isMono: true });
    }
  } else if (pathname === "/exceptions") {
    crumbs.push({ label: "Exceptions" });
  } else if (pathname.startsWith("/exceptions/")) {
    const parts = pathname.split("/").filter(Boolean);
    crumbs.push({ label: "Exceptions", href: "/exceptions" });
    if (parts[1]) {
      crumbs.push({ label: decodeURIComponent(parts[1]), isMono: true });
    }
  } else if (pathname === "/model-evaluation") {
    crumbs.push({ label: "Model Evaluation" });
  } else {
    // Generic fallback for any other nested route
    const parts = pathname.split("/").filter(Boolean);
    crumbs.push({ label: "Dashboard", href: "/" });
    parts.forEach((p, idx) => {
      const isLast = idx === parts.length - 1;
      crumbs.push({
        label: p.charAt(0).toUpperCase() + p.slice(1),
        href: isLast ? undefined : `/${parts.slice(0, idx + 1).join("/")}`,
      });
    });
  }

  if (crumbs.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center space-x-1.5 text-xs text-slate-500">
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1;

          return (
            <li key={`${crumb.label}-${idx}`} className="flex items-center space-x-1.5">
              {idx > 0 && (
                <ChevronRight
                  className="h-3.5 w-3.5 text-slate-400 shrink-0"
                  aria-hidden="true"
                />
              )}
              {isLast || !crumb.href ? (
                <span
                  className={crumb.isMono ? "font-mono font-medium text-slate-900" : "font-medium text-slate-900"}
                  aria-current={isLast ? "page" : undefined}
                >
                  {crumb.label}
                </span>
              ) : (
                <Link
                  href={crumb.href}
                  className="transition-colors hover:text-slate-900 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-slate-900 rounded-xs"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
