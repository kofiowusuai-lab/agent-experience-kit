import {useEffect,useState} from "react";
import {ArrowUpRight,Search} from "lucide-react";
import type {Run,Page} from "../types";
import {useData} from "../api";
import {date,words,State,Ribbon,Notice,Pagination} from "../shared";
export default function Runs({ team, open }: { team: string; open: (id: string) => void }) {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(search);
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => setOffset(0), [team, status]);
  const q = useData<Page<Run>>(
    `/runs?${new URLSearchParams({ team_id: team, status, search: debounced, limit: "10", offset: String(offset) })}`,
  );
  return (
    <section className="panel runs">
      <div className="panel-heading">
        <div>
          <h2>Run register</h2>
          <span className="muted">Current state, as reported by agents</span>
        </div>
        <div className="filters">
          <label className="search">
            <Search size={16} />
            <input
              aria-label="Search runs or agents"
              placeholder="Search runs or agents"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All states</option>
            {["running", "failed", "pending", "completed"].map((s) => (
              <option key={s} value={s}>
                {words(s)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <Notice {...q} empty={q.data?.total === 0} />
      {!q.loading && !q.error && !!q.data?.total && (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Run / agent</th>
                  <th>Team</th>
                  <th>Reported state</th>
                  <th>Step progress</th>
                  <th>Last received</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <button className="run-link" onClick={() => open(r.id)}>
                        {r.run_id}
                      </button>
                      <small className="cell-sub">{r.agent}</small>
                    </td>
                    <td>{r.team_name}</td>
                    <td>
                      <State value={r.status} />
                    </td>
                    <td>
                      <Ribbon run={r} />
                    </td>
                    <td className="mono date-cell">
                      {date(r.last_received_at)}
                      <small className="cell-sub">
                        {r.attempts} attempts · {r.review_count} reviews
                      </small>
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`Open ${r.run_id}`}
                        onClick={() => open(r.id)}
                      >
                        <ArrowUpRight size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            total={q.data.total}
            offset={offset}
            setOffset={setOffset}
          />
        </>
      )}
    </section>
  );
}
