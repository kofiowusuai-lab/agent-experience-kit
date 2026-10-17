export type Me = {
  organization: { id: string; name: string; demo: boolean };
  actor: { label: string; role: string };
  teams: { id: string; name: string }[];
  csrf_token: string;
};
export type Run = {
  id: string;
  run_id: string;
  agent: string;
  team_name: string;
  status: string;
  step_count: number;
  completed_steps: number;
  attempts: number;
  last_received_at: string;
  review_count: number;
};
export type Review = {
  id: string;
  run_id: string;
  run_label: string;
  team_name: string;
  outcome: string;
  note: string;
  reviewer: string;
  created_at: string;
};
export type Step = {
  id: string;
  state: string;
  attempts: number;
  approved: boolean;
  checks: unknown;
  artifact_hashes: unknown;
};
export type Event = {
  id: string;
  kind: string;
  sequence: number;
  occurred_at: string;
  received_at: string;
  payload: Record<string, unknown>;
};
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type Overview = {
  runs: {
    total: number;
    completed: number;
    failed: number;
    running: number;
    pending: number;
  };
  agents: { total: number; active: number };
  unreviewed_failures: number;
  latest_ingestion_at: string | null;
  events_total: number;
  activity: { date: string; events: number; failures: number }[];
  failures: { code: string; count: number }[];
};
export type Failure = {
  code: string;
  count: number;
  affected_runs: number;
  last_seen: string;
};
