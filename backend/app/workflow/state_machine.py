"""
ReconLens — workflow state machine.

Invalid transitions raise InvalidTransitionError rather than silently
succeeding or being ignored — a workflow bug that silently allows an
illegal state change is worse than one that crashes loudly.
"""


class InvalidTransitionError(Exception):
    pass


# Every valid (from_state -> {allowed to_states}) edge, listed explicitly —
# no wildcard "anything can go anywhere" fallback.
VALID_TRANSITIONS = {
    "PENDING": {"PROCESSING", "FAILED"},
    "PROCESSING": {"AUTO_MATCHED", "NEEDS_REVIEW", "LIKELY_NO_MATCH", "FAILED"},
    "AUTO_MATCHED": set(),               # terminal — an auto-match is not further reviewed in Phase 5
    "NEEDS_REVIEW": {"APPROVED_BY_REVIEWER", "REJECTED_BY_REVIEWER"},
    "APPROVED_BY_REVIEWER": set(),       # terminal
    "REJECTED_BY_REVIEWER": set(),       # terminal
    "LIKELY_NO_MATCH": {"EXCEPTION"},    # every likely-no-match becomes an explicit exception, not silence
    "EXCEPTION": set(),                  # terminal (Phase 5 scope — no exception-resolution workflow yet)
    "FAILED": set(),                     # terminal
}

TERMINAL_STATES = {s for s, targets in VALID_TRANSITIONS.items() if not targets}


# Batches have their own, simpler lifecycle — genuinely different states
# from decisions (a batch doesn't become "AUTO_MATCHED"; individual
# decisions within it do). Kept as an explicit, separate machine rather
# than overloading the decision-level vocabulary, which was the source of
# a real bug caught while running the first end-to-end batch (see
# docs/workflow.md "Important Failures").
BATCH_VALID_TRANSITIONS = {
    "CREATED": {"PROCESSING", "FAILED"},
    "PROCESSING": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
}


def transition_batch(current_state: str, target_state: str) -> str:
    if current_state not in BATCH_VALID_TRANSITIONS:
        raise InvalidTransitionError(f"Unknown batch state: {current_state!r}")
    allowed = BATCH_VALID_TRANSITIONS[current_state]
    if target_state not in allowed:
        raise InvalidTransitionError(
            f"Invalid batch transition: {current_state!r} -> {target_state!r}. "
            f"Allowed from {current_state!r}: {sorted(allowed) or '(none — terminal state)'}"
        )
    return target_state


def transition(current_state: str, target_state: str) -> str:
    """Returns target_state if the transition is valid; raises otherwise."""
    if current_state not in VALID_TRANSITIONS:
        raise InvalidTransitionError(f"Unknown current state: {current_state!r}")
    allowed = VALID_TRANSITIONS[current_state]
    if target_state not in allowed:
        raise InvalidTransitionError(
            f"Invalid transition: {current_state!r} -> {target_state!r}. "
            f"Allowed from {current_state!r}: {sorted(allowed) or '(none — terminal state)'}"
        )
    return target_state


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES
