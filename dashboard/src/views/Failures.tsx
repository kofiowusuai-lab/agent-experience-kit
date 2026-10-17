import {TriangleAlert} from "lucide-react";
import type {Failure} from "../types";
import {useData} from "../api";
import {date,words,Notice} from "../shared";
export default function Failures({ team }: { team: string }) {
  const q = useData<{ items: Failure[]; total: number }>(
    "/failures?team_id=" + encodeURIComponent(team),
  );
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Failure patterns</h2>
        <span className="muted">Normalized event categories</span>
      </div>
      <Notice {...q} empty={q.data?.items.length === 0} />
      {!q.loading && !q.error && q.data && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Failure category</th>
                <th>Events</th>
                <th>Affected runs</th>
                <th>Last observed</th>
              </tr>
            </thead>
            <tbody>
              {q.data.items.map((f) => (
                <tr key={f.code}>
                  <td>
                    <span className="failure-label">
                      <TriangleAlert size={16} />
                      {words(f.code)}
                    </span>
                  </td>
                  <td className="mono">{f.count}</td>
                  <td className="mono">{f.affected_runs}</td>
                  <td>{date(f.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
