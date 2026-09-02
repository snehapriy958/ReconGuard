export function StateTransition({
  previousState,
  newState,
}: {
  previousState: string | null;
  newState: string | null;
}) {
  // Only renders a transition when BOTH real values are present — never
  // implies a transition happened (e.g. "NEEDS_REVIEW became AUTO_MATCHED")
  // when the persisted event doesn't actually carry both states.
  if (!previousState || !newState) return null;
  return (
    <div className="mt-1 flex items-center gap-2 font-mono text-xs text-slate-500">
      <span>{previousState}</span>
      <span className="text-slate-300">→</span>
      <span className="font-medium text-slate-700">{newState}</span>
    </div>
  );
}
