import {ChevronLeft,ChevronRight,TriangleAlert} from "lucide-react";
import type {Run} from "./types";
export const date = (s: string | null | undefined) =>
  s
    ? new Date(s).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "No events received";
export const words = (s: string) => s.replaceAll("_", " ");
export function State({ value }: { value: string }) {
  return (
    <span className={"badge " + value}>
      <i />
      {words(value)}
    </span>
  );
}
export function Ribbon({ run }: { run: Run }) {
  const n = Math.min(run.step_count, 16);
  return (
    <div
      className="ribbon"
      aria-label={`${run.completed_steps} of ${run.step_count} steps completed`}
    >
      {Array.from({ length: n }, (_, i) => (
        <span
          key={i}
          className={
            i < run.completed_steps
              ? "complete"
              : i === run.completed_steps
                ? run.status
                : ""
          }
        />
      ))}
      <small>
        {run.completed_steps}/{run.step_count}
      </small>
    </div>
  );
}
export function Notice({
  loading,
  error,
  retry,
  empty,
}: {
  loading?: boolean;
  error?: string;
  retry?: () => void;
  empty?: boolean;
}) {
  if (loading)
    return (
      <div className="notice" role="status">
        Loading audit records…
      </div>
    );
  if (error)
    return (
      <div className="notice error" role="alert">
        <TriangleAlert size={20} />
        <span>{error}</span>
        <button onClick={retry}>Retry</button>
      </div>
    );
  if (empty)
    return (
      <div className="notice">
        No records match these filters. Try another team or search.
      </div>
    );
  return null;
}
export function Pagination({
  total,
  offset,
  setOffset,
}: {
  total: number;
  offset: number;
  setOffset: (n: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {total
          ? `${offset + 1}–${Math.min(offset + 10, total)} of ${total}`
          : "0 records"}
      </span>
      <button
        aria-label="Previous page"
        disabled={!offset}
        onClick={() => setOffset(Math.max(0, offset - 10))}
      >
        <ChevronLeft size={16} />
      </button>
      <button
        aria-label="Next page"
        disabled={offset + 10 >= total}
        onClick={() => setOffset(offset + 10)}
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
