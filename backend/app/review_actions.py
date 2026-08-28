"""
ReconLens — human review actions.

Core principle (spec section 16): MODEL_DECISION and FINAL_RESOLUTION are
different things. approve_review()/reject_review() never modify
decision.decision or decision.raw_probability/calibrated_probability — the
ML output is permanent history. Only decision.workflow_state (the current
operational status) and the ReviewTask advance.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.audit import record_event
from backend.app.models.review import ReviewTask
from backend.app.workflow.state_machine import transition, InvalidTransitionError


class ReviewNotFoundError(Exception):
    pass


class ReviewAlreadyResolvedError(Exception):
    pass


def _resolve(db: Session, review_id: str, reviewer_id: str, action: str, comment: str | None) -> ReviewTask:
    review = db.query(ReviewTask).filter(ReviewTask.id == review_id).first()
    if review is None:
        raise ReviewNotFoundError(f"No review task {review_id!r}")
    if review.status in ("APPROVED", "REJECTED"):
        raise ReviewAlreadyResolvedError(
            f"Review {review_id!r} is already resolved ({review.status}); "
            f"the original resolution is preserved, not overwritten."
        )

    decision = review.decision
    previous_workflow_state = decision.workflow_state

    if action == "APPROVE_MATCH":
        review.status = "APPROVED"
        decision.workflow_state = transition(decision.workflow_state, "APPROVED_BY_REVIEWER")
        event_type = "REVIEW_APPROVED"
    elif action == "REJECT_MATCH":
        review.status = "REJECTED"
        decision.workflow_state = transition(decision.workflow_state, "REJECTED_BY_REVIEWER")
        event_type = "REVIEW_REJECTED"
    else:
        raise ValueError(f"Unknown review action: {action!r}")

    review.resolved_at = datetime.now(timezone.utc)

    record_event(
        db, "REVIEW", review.id, event_type, actor_type="HUMAN", actor_id=reviewer_id,
        previous_state=previous_workflow_state, new_state=decision.workflow_state,
        payload={"action": action, "comment": comment,
                 "model_decision_preserved": decision.decision,  # explicit proof the ML decision wasn't touched
                 "model_calibrated_probability": decision.calibrated_probability},
    )
    db.commit()
    return review


def approve_review(db: Session, review_id: str, reviewer_id: str, comment: str | None = None) -> ReviewTask:
    return _resolve(db, review_id, reviewer_id, "APPROVE_MATCH", comment)


def reject_review(db: Session, review_id: str, reviewer_id: str, comment: str | None = None) -> ReviewTask:
    return _resolve(db, review_id, reviewer_id, "REJECT_MATCH", comment)
