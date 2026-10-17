import {words} from "../shared";
export default function Qa({ payload }: { payload: Record<string, unknown> }) {
  const qa = payload.qa as
    { passed?: boolean; defect_counts?: Record<string, number> } | undefined;
  if (!qa) return null;
  return (
    <div className="qa-summary">
      <strong>Automated QA: {qa.passed ? "passed" : "failed"}</strong>
      {qa.defect_counts &&
        Object.entries(qa.defect_counts).map(([k, v]) => (
          <span key={k}>
            {words(k)}: {v}
          </span>
        ))}
    </div>
  );
}
