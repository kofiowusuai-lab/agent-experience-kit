import {TriangleAlert} from "lucide-react";
import type {Overview} from "../types";
import {useData} from "../api";
import {date,words,Notice} from "../shared";
export default function OverviewView({ team }: { team: string }) {
  const q = useData<Overview>("/overview?team_id=" + encodeURIComponent(team));
  if (q.loading || q.error || !q.data) return <Notice {...q} />;
  const d = q.data;
  const max = Math.max(1, ...d.activity.map((a) => a.events));
  return (
    <>
      <div className="metrics">
        {[
          {
            label: "Reported runs",
            value: d.runs.total,
            detail: `${d.runs.running} running · ${d.runs.pending} pending`,
          },
          {
            label: "Completed",
            value: d.runs.completed,
            detail: "Reported completed state",
          },
          {
            label: "Needs review",
            value: d.unreviewed_failures,
            detail: `${d.runs.failed} failed runs`,
            warning: true,
          },
          {
            label: "Reporting agents",
            value: d.agents.active,
            detail: `${d.agents.total} total · received in last 24h`,
          },
        ].map((m) => (
          <section
            className={"metric " + (m.warning ? "warning" : "")}
            key={m.label}
          >
            <span>{m.label}</span>
            <strong>{m.value}</strong>
            <small>{m.detail}</small>
          </section>
        ))}
      </div>
      <div className="insights">
        <section className="panel activity-panel">
          <div className="panel-heading">
            <h2>Receipt activity</h2>
            <span className="muted">
              Last 7 UTC days · {d.events_total} events total
            </span>
          </div>
          <div
            className="chart"
            role="img"
            aria-label={d.activity
              .map(
                (a) =>
                  `${a.date}: ${a.events} received events, ${a.failures} failures`,
              )
              .join("; ")}
          >
            {d.activity.map((a) => (
              <div className="bar-column" key={a.date}>
                <span className="bar-number">{a.events}</span>
                <div className="bar-space">
                  <div
                    className="bar"
                    style={{
                      height: `${Math.max(2, (a.events / max) * 100)}%`,
                    }}
                  />
                </div>
                <small>{a.date.slice(5)}</small>
              </div>
            ))}
          </div>
          <div className="receipt">
            <span className="dot" />
            Latest receipt <strong>{date(d.latest_ingestion_at)}</strong>
          </div>
        </section>
        <section className="panel patterns-panel">
          <div className="panel-heading">
            <h2>Failure signals</h2>
            <TriangleAlert size={18} />
          </div>
          {d.failures.length ? (
            d.failures.slice(0, 4).map((f) => (
              <div className="failure-signal" key={f.code}>
                <span>{words(f.code)}</span>
                <b>{f.count}</b>
              </div>
            ))
          ) : (
            <p className="muted">No normalized failure events received.</p>
          )}
          <p className="caption">
            Counts reflect reported failure events, not inferred causes.
          </p>
        </section>
      </div>
    </>
  );
}
