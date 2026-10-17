import {useEffect,useState} from "react";
import type {Review,Page} from "../types";
import {useData} from "../api";
import {date,State,Notice,Pagination} from "../shared";
export default function Reviews({
  team,
  open,
  run,
  revision = 0,
}: {
  team: string;
  open: (id: string) => void;
  run?: string;
  revision?: number;
}) {
  const [offset, setOffset] = useState(0);
  useEffect(() => setOffset(0), [team, run]);
  const q = useData<Page<Review>>(
    `/reviews?${new URLSearchParams({ team_id: team, run_id: run || "", limit: "10", offset: String(offset) })}`,
    revision,
  );
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Review history</h2>
        <span className="muted">Append only</span>
      </div>
      <Notice {...q} empty={q.data?.total === 0} />
      {!q.loading && !q.error && q.data && (
        <>
          <div className="review-list">
            {q.data.items.map((r) => (
              <article className="review" key={r.id}>
                <div>
                  <State value={r.outcome} />
                  <time>{date(r.created_at)}</time>
                </div>
                {!run && (
                  <button className="run-link" onClick={() => open(r.run_id)}>
                    {r.run_label}
                  </button>
                )}
                <p className="review-note">{r.note}</p>
                <small>
                  {r.reviewer} · {r.team_name}
                </small>
              </article>
            ))}
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
