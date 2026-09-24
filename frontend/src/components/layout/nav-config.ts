import {
  LayoutDashboard,
  Layers,
  UploadCloud,
  ClipboardCheck,
  AlertTriangle,
  BarChart3,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    name: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
    description: "System overview and batch activity",
  },
  {
    name: "Batches",
    href: "/batches",
    icon: Layers,
    description: "Reconciliation runs and decision records",
  },
  {
    name: "Upload",
    href: "/upload",
    icon: UploadCloud,
    description: "Submit ledger and settlement CSV files",
  },
  {
    name: "Reviews",
    href: "/reviews",
    icon: ClipboardCheck,
    description: "Human review queue and approvals",
  },
  {
    name: "Exceptions",
    href: "/exceptions",
    icon: AlertTriangle,
    description: "Root-cause intelligence for unresolved items",
  },
  {
    name: "Model Evaluation",
    href: "/model-evaluation",
    icon: BarChart3,
    description: "Model performance, calibration, and routing metrics",
  },
];

/**
 * Determines whether a navigation item is currently active.
 *
 * Rules:
 * - "/" (Dashboard) is active only on exact root "/".
 * - "/batches" is active on "/batches", any nested "/batches/*", or "/decisions/*" (since decisions belong to batches).
 * - "/upload" is active on "/upload" and any nested "/upload/*".
 * - "/reviews" is active on "/reviews" and any nested "/reviews/*".
 * - "/exceptions" is active on "/exceptions" and any nested "/exceptions/*".
 */
export function isNavItemActive(href: string, pathname: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  if (href === "/batches") {
    return (
      pathname === "/batches" ||
      pathname.startsWith("/batches/") ||
      pathname.startsWith("/decisions")
    );
  }
  if (href === "/upload") {
    return pathname === "/upload" || pathname.startsWith("/upload/");
  }
  if (href === "/reviews") {
    return pathname === "/reviews" || pathname.startsWith("/reviews/");
  }
  if (href === "/exceptions") {
    return pathname === "/exceptions" || pathname.startsWith("/exceptions/");
  }
  if (href === "/model-evaluation") {
    return (
      pathname === "/model-evaluation" ||
      pathname.startsWith("/model-evaluation/")
    );
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
