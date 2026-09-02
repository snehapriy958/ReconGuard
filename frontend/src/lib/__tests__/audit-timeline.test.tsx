import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { eventCategory, eventTitle, eventSummary } from "../audit-event-display";
import { StateTransition } from "@/components/decision/state-transition";
import { AuditEventCard } from "@/components/decision/audit-event-card";
import { AuditTimeline } from "@/components/decision/audit-timeline";
import type { AuditEventItem } from "@/lib/api-types";

function makeEvent(overrides: Partial<AuditEventItem>): AuditEventItem {
  return {
    event_id: "EVT-0001",
    event_type: "MODEL_EVALUATED",
    actor_type: "MODEL",
    actor_id: null,
    previous_state: null,
    new_state: null,
    payload: null,
    timestamp: "2026-01-01T10:00:00Z",
    ...overrides,
  };
}

describe("audit-event-display", () => {
  it("categorizes real event types correctly", () => {
    expect(eventCategory("MODEL_EVALUATED")).toBe("MODEL");
    expect(eventCategory("REVIEW_APPROVED")).toBe("HUMAN");
    expect(eventCategory("EXCEPTION_CREATED")).toBe("EXCEPTION");
    expect(eventCategory("BATCH_CREATED")).toBe("SYSTEM");
    expect(eventCategory("AUTO_MATCH_CREATED")).toBe("WORKFLOW");
  });

  it("handles an unrecognized event type honestly, not as a guessed category", () => {
    expect(eventCategory("SOMETHING_NEW")).toBe("UNKNOWN");
    expect(eventTitle("SOMETHING_NEW")).toMatch(/Unrecognized event/);
  });

  it("builds a summary only from fields actually present in the payload", () => {
    const withFields = eventSummary(
      makeEvent({ payload: { decision: "NEEDS_REVIEW", calibrated_probability: 0.71 } })
    );
    expect(withFields).toContain("NEEDS_REVIEW");
    expect(withFields).toContain("71%");

    const withoutFields = eventSummary(makeEvent({ payload: {} }));
    expect(withoutFields).toBe("Model evaluation recorded.");
  });
});

describe("StateTransition", () => {
  it("renders both states when present", () => {
    render(<StateTransition previousState="NEEDS_REVIEW" newState="APPROVED_BY_REVIEWER" />);
    expect(screen.getByText("NEEDS_REVIEW")).toBeInTheDocument();
    expect(screen.getByText("APPROVED_BY_REVIEWER")).toBeInTheDocument();
  });

  it("renders nothing when either state is missing, rather than a fabricated transition", () => {
    const { container } = render(<StateTransition previousState={null} newState="APPROVED_BY_REVIEWER" />);
    expect(container.firstChild).toBeNull();
  });
});

describe("AuditEventCard", () => {
  it("renders the real category, title, and timestamp", () => {
    render(<AuditEventCard event={makeEvent({ event_type: "REVIEW_APPROVED", actor_type: "HUMAN", actor_id: "priya" })} />);
    expect(screen.getByText("HUMAN")).toBeInTheDocument();
    expect(screen.getByText("Reviewer approved")).toBeInTheDocument();
    expect(screen.getByText(/human: priya/)).toBeInTheDocument();
  });

  it("shows the invariant-preservation banner ONLY when real payload fields support it", () => {
    render(
      <AuditEventCard
        event={makeEvent({
          event_type: "REVIEW_APPROVED",
          payload: { model_decision_preserved: "NEEDS_REVIEW", model_calibrated_probability: 0.71 },
        })}
      />
    );
    expect(screen.getByText(/Original ML output preserved/)).toBeInTheDocument();
    expect(screen.getByText("NEEDS_REVIEW")).toBeInTheDocument();
  });

  it("does not show the invariant banner when the payload lacks those fields", () => {
    render(<AuditEventCard event={makeEvent({ event_type: "REVIEW_APPROVED", payload: { comment: "ok" } })} />);
    expect(screen.queryByText(/Original ML output preserved/)).not.toBeInTheDocument();
  });

  it("does not show the invariant banner for non-review events even with similar-looking payload", () => {
    render(
      <AuditEventCard
        event={makeEvent({
          event_type: "MODEL_EVALUATED",
          payload: { model_decision_preserved: "X", model_calibrated_probability: 0.5 },
        })}
      />
    );
    expect(screen.queryByText(/Original ML output preserved/)).not.toBeInTheDocument();
  });

  it("hides technical payload by default behind a collapsed disclosure", () => {
    render(<AuditEventCard event={makeEvent({ payload: { foo: "bar" } })} />);
    const details = screen.getByText("Technical details").closest("details");
    expect(details).not.toHaveAttribute("open");
  });

  it("renders a real state transition when the event carries one", () => {
    render(
      <AuditEventCard
        event={makeEvent({ event_type: "REVIEW_TASK_CREATED", previous_state: "PROCESSING", new_state: "NEEDS_REVIEW" })}
      />
    );
    expect(screen.getByText("PROCESSING")).toBeInTheDocument();
    expect(screen.getByText("NEEDS_REVIEW")).toBeInTheDocument();
  });
});

describe("AuditTimeline", () => {
  it("renders events in the exact order provided, without re-sorting", () => {
    const events = [
      makeEvent({ event_id: "EVT-1", event_type: "BATCH_CREATED" }),
      makeEvent({ event_id: "EVT-2", event_type: "PROCESSING_STARTED", timestamp: "2020-01-01T00:00:00Z" }),
    ];
    render(<AuditTimeline events={events} />);
    const titles = screen.getAllByText(/Batch created|Processing started/);
    expect(titles[0].textContent).toBe("Batch created");
  });

  it("shows an honest empty state when there are no events", () => {
    render(<AuditTimeline events={[]} />);
    expect(screen.getByText("No audit events recorded yet.")).toBeInTheDocument();
  });
});
