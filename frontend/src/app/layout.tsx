import type { Metadata } from "next";
import "./globals.css";

// Deliberately NOT using next/font/google here: it requires build-time
// network access to fonts.googleapis.com, which isn't guaranteed in every
// build environment (this sandbox can't reach it, and neither can some CI
// or offline setups). A system font stack has zero external dependency and
// still looks clean for a finance-operations product — the same reasoning
// as the sentence-transformers fallback in the ML pipeline (see
// docs/architecture.md Phase 2 notes): don't make a demo depend on network
// access it doesn't strictly need.

export const metadata: Metadata = {
  title: "ReconGuard",
  description: "AI-powered multi-source financial reconciliation",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
