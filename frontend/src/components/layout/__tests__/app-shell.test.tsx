import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { AppShell } from "../app-shell";
import { Breadcrumbs } from "../breadcrumbs";
import { isNavItemActive } from "../nav-config";

let mockPathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: vi.fn() }),
}));

describe("AppShell & Navigation", () => {
  beforeEach(() => {
    mockPathname = "/";
  });

  it("1. App shell renders children successfully", () => {
    render(
      <AppShell>
        <div data-testid="test-content">Page Content Loaded</div>
      </AppShell>
    );

    expect(screen.getByTestId("test-content")).toBeInTheDocument();
    expect(screen.getByText("Page Content Loaded")).toBeInTheDocument();
  });

  it("2. Main navigation items render with accessible labels and links", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    // Sidebar navigation
    const nav = screen.getByRole("navigation", { name: "Sidebar" });
    const links = within(nav).getAllByRole("link");

    expect(links).toHaveLength(6);
    expect(within(nav).getByRole("link", { name: /Dashboard/i })).toHaveAttribute("href", "/");
    expect(within(nav).getByRole("link", { name: /Batches/i })).toHaveAttribute("href", "/batches");
    expect(within(nav).getByRole("link", { name: /Upload/i })).toHaveAttribute("href", "/upload");
    expect(within(nav).getByRole("link", { name: /Reviews/i })).toHaveAttribute("href", "/reviews");
    expect(within(nav).getByRole("link", { name: /Exceptions/i })).toHaveAttribute("href", "/exceptions");
    expect(within(nav).getByRole("link", { name: /Model Evaluation/i })).toHaveAttribute("href", "/model-evaluation");
  });

  it("2b. Upload is correctly marked active on '/upload'", () => {
    mockPathname = "/upload";
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    const nav = screen.getByRole("navigation", { name: "Sidebar" });
    const uploadLink = within(nav).getByRole("link", { name: /Upload/i });
    const dashboardLink = within(nav).getByRole("link", { name: /Dashboard/i });

    expect(uploadLink).toHaveAttribute("aria-current", "page");
    expect(dashboardLink).not.toHaveAttribute("aria-current");
  });

  it("2c. Model Evaluation is correctly marked active on '/model-evaluation'", () => {
    mockPathname = "/model-evaluation";
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    const nav = screen.getByRole("navigation", { name: "Sidebar" });
    const modelEvalLink = within(nav).getByRole("link", { name: /Model Evaluation/i });
    const dashboardLink = within(nav).getByRole("link", { name: /Dashboard/i });

    expect(modelEvalLink).toHaveAttribute("aria-current", "page");
    expect(dashboardLink).not.toHaveAttribute("aria-current");
  });

  it("3. Dashboard is correctly marked active on '/'", () => {
    mockPathname = "/";
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    const nav = screen.getByRole("navigation", { name: "Sidebar" });
    const dashboardLink = within(nav).getByRole("link", { name: /Dashboard/i });
    const batchesLink = within(nav).getByRole("link", { name: /Batches/i });
    const uploadLink = within(nav).getByRole("link", { name: /Upload/i });
    const reviewsLink = within(nav).getByRole("link", { name: /Reviews/i });
    const exceptionsLink = within(nav).getByRole("link", { name: /Exceptions/i });
    const modelEvalLink = within(nav).getByRole("link", { name: /Model Evaluation/i });

    expect(dashboardLink).toHaveAttribute("aria-current", "page");
    expect(batchesLink).not.toHaveAttribute("aria-current");
    expect(uploadLink).not.toHaveAttribute("aria-current");
    expect(reviewsLink).not.toHaveAttribute("aria-current");
    expect(exceptionsLink).not.toHaveAttribute("aria-current");
    expect(modelEvalLink).not.toHaveAttribute("aria-current");
  });

  it("4. Batches is correctly active on batch routes (list and detail)", () => {
    const batchRoutes = [
      "/batches",
      "/batches/BATCH-2026-09",
      "/batches/BATCH-2026-09/decisions",
      "/decisions/DEC-001",
    ];

    for (const route of batchRoutes) {
      mockPathname = route;
      const { unmount } = render(
        <AppShell>
          <div>Content</div>
        </AppShell>
      );

      const nav = screen.getByRole("navigation", { name: "Sidebar" });
      const dashboardLink = within(nav).getByRole("link", { name: /Dashboard/i });
      const batchesLink = within(nav).getByRole("link", { name: /Batches/i });

      expect(batchesLink).toHaveAttribute("aria-current", "page");
      expect(dashboardLink).not.toHaveAttribute("aria-current");

      unmount();
    }
  });

  it("5. Reviews is correctly active on review routes", () => {
    const reviewRoutes = ["/reviews", "/reviews/REV-100"];

    for (const route of reviewRoutes) {
      mockPathname = route;
      const { unmount } = render(
        <AppShell>
          <div>Content</div>
        </AppShell>
      );

      const nav = screen.getByRole("navigation", { name: "Sidebar" });
      const reviewsLink = within(nav).getByRole("link", { name: /Reviews/i });
      const dashboardLink = within(nav).getByRole("link", { name: /Dashboard/i });

      expect(reviewsLink).toHaveAttribute("aria-current", "page");
      expect(dashboardLink).not.toHaveAttribute("aria-current");

      unmount();
    }
  });

  it("6. Exceptions is correctly active on exception routes", () => {
    const exceptionRoutes = ["/exceptions", "/exceptions/EXC-200"];

    for (const route of exceptionRoutes) {
      mockPathname = route;
      const { unmount } = render(
        <AppShell>
          <div>Content</div>
        </AppShell>
      );

      const nav = screen.getByRole("navigation", { name: "Sidebar" });
      const exceptionsLink = within(nav).getByRole("link", { name: /Exceptions/i });
      const dashboardLink = within(nav).getByRole("link", { name: /Dashboard/i });

      expect(exceptionsLink).toHaveAttribute("aria-current", "page");
      expect(dashboardLink).not.toHaveAttribute("aria-current");

      unmount();
    }
  });

  it("7. Mobile navigation opens and closes via button and escape key", () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    // Mobile nav drawer should initially be closed
    expect(screen.queryByRole("dialog", { name: "Mobile Navigation" })).not.toBeInTheDocument();

    // Trigger open
    const openBtn = screen.getByRole("button", { name: "Open navigation menu" });
    fireEvent.click(openBtn);

    // Mobile drawer should be visible
    const mobileDialog = screen.getByRole("dialog", { name: "Mobile Navigation" });
    expect(mobileDialog).toBeInTheDocument();

    // Within mobile drawer, navigation items are present
    const mobileNav = within(mobileDialog).getByRole("navigation", { name: "Mobile" });
    expect(within(mobileNav).getByRole("link", { name: /Dashboard/i })).toBeInTheDocument();

    // Close via close button
    const closeBtn = within(mobileDialog).getByRole("button", { name: "Close navigation menu" });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole("dialog", { name: "Mobile Navigation" })).not.toBeInTheDocument();

    // Re-open and close via Escape key
    fireEvent.click(openBtn);
    expect(screen.getByRole("dialog", { name: "Mobile Navigation" })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Mobile Navigation" })).not.toBeInTheDocument();
  });

  it("8. Navigation links point to actual existing routes", () => {
    mockPathname = "/";
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    const nav = screen.getByRole("navigation", { name: "Sidebar" });
    const expectedRoutes = ["/", "/batches", "/upload", "/reviews", "/exceptions", "/model-evaluation"];

    expectedRoutes.forEach((route) => {
      const link = within(nav).getByRole("link", {
        name: (content, element) => element?.getAttribute("href") === route,
      });
      expect(link).toHaveAttribute("href", route);
    });
  });

  it("9. Breadcrumbs render correctly for root and nested routes", () => {
    // Root
    mockPathname = "/";
    const { rerender } = render(<Breadcrumbs />);
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toHaveAttribute("aria-current", "page");

    // Upload route
    mockPathname = "/upload";
    rerender(<Breadcrumbs />);
    expect(screen.getByText("Upload")).toHaveAttribute("aria-current", "page");

    // Model Evaluation route
    mockPathname = "/model-evaluation";
    rerender(<Breadcrumbs />);
    expect(screen.getByText("Model Evaluation")).toHaveAttribute("aria-current", "page");

    // Nested batch route
    mockPathname = "/batches/BATCH-001";
    rerender(<Breadcrumbs />);
    expect(screen.getByRole("link", { name: "Batches" })).toHaveAttribute("href", "/batches");
    expect(screen.getByText("BATCH-001")).toHaveAttribute("aria-current", "page");

    // Nested decision route
    mockPathname = "/batches/BATCH-001/decisions";
    rerender(<Breadcrumbs />);
    expect(screen.getByRole("link", { name: "BATCH-001" })).toHaveAttribute("href", "/batches/BATCH-001");
    expect(screen.getByText("Decisions")).toHaveAttribute("aria-current", "page");

    // Nested review route
    mockPathname = "/reviews/REV-999";
    rerender(<Breadcrumbs />);
    expect(screen.getByRole("link", { name: "Reviews" })).toHaveAttribute("href", "/reviews");
    expect(screen.getByText("REV-999")).toHaveAttribute("aria-current", "page");

    // Nested exception route
    mockPathname = "/exceptions/EXC-777";
    rerender(<Breadcrumbs />);
    expect(screen.getByRole("link", { name: "Exceptions" })).toHaveAttribute("href", "/exceptions");
    expect(screen.getByText("EXC-777")).toHaveAttribute("aria-current", "page");
  });

  it("10. isNavItemActive helper handles exact vs nested matching accurately", () => {
    expect(isNavItemActive("/", "/")).toBe(true);
    expect(isNavItemActive("/", "/batches")).toBe(false);
    expect(isNavItemActive("/", "/reviews")).toBe(false);

    expect(isNavItemActive("/upload", "/upload")).toBe(true);
    expect(isNavItemActive("/upload", "/batches")).toBe(false);

    expect(isNavItemActive("/batches", "/batches")).toBe(true);
    expect(isNavItemActive("/batches", "/batches/BATCH-1")).toBe(true);
    expect(isNavItemActive("/batches", "/decisions/DEC-1")).toBe(true);
    expect(isNavItemActive("/batches", "/")).toBe(false);

    expect(isNavItemActive("/reviews", "/reviews")).toBe(true);
    expect(isNavItemActive("/reviews", "/reviews/REV-1")).toBe(true);
    expect(isNavItemActive("/reviews", "/batches")).toBe(false);

    expect(isNavItemActive("/exceptions", "/exceptions")).toBe(true);
    expect(isNavItemActive("/exceptions", "/exceptions/EXC-1")).toBe(true);
    expect(isNavItemActive("/exceptions", "/")).toBe(false);

    expect(isNavItemActive("/model-evaluation", "/model-evaluation")).toBe(true);
    expect(isNavItemActive("/model-evaluation", "/batches")).toBe(false);
  });
});
