import React,{useState} from "react";
import {ArrowLeft,Check,ClipboardCheck} from "lucide-react";
import type {Me,Run,Review,Step,Event,Page} from "../types";
import {api,useData} from "../api";
import {date,words,State,Ribbon,Notice,Pagination} from "../shared";
import Reviews from "./Reviews";
import Qa from "./Qa";
export default function RunDetail({ id, me, back }: { id: string; me: Me; back: () => void }) {
  const [revision, setRevision] = useState(0);
  const q = useData<{ run: Run; steps: Step[]; reviews: Review[] }>(
    `/runs/${encodeURIComponent(id)}`,
    revision,
  );
  const [offset, setOffset] = useState(0);
  const events = useData<Page<Event>>(
    `/runs/${encodeURIComponent(id)}/events?limit=10&offset=${offset}`,
    revision,
  );
  const [outcome, setOutcome] = useState("accepted");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api(`/runs/${encodeURIComponent(id)}/reviews`, {
        method: "POST",
        headers: { "X-CSRF-Token": me.csrf_token },
        body: JSON.stringify({ outcome, note }),
      });
      setNote("");
      setSaved(true);
      setRevision((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="back" onClick={back}>
        <ArrowLeft size={16} />
        Back to workspace
      </button>
      <Notice {...q} />
      {q.data && !q.loading && !q.error && (
        <>
          <div className="page-heading detail-heading">
            <div>
              <span className="eyebrow">
                RUN EVIDENCE / {q.data.run.team_name}
              </span>
              <h1>{q.data.run.run_id}</h1>
              <p>
                {q.data.run.agent} · Last received{" "}
                {date(q.data.run.last_received_at)}
              </p>
            </div>
            <State value={q.data.run.status} />
          </div>
          <section className="panel">
            <div className="panel-heading">
              <h2>Acceptance & evidence</h2>
              <Ribbon run={q.data.run} />
            </div>
            <div className="steps">
              {q.data.steps.length ? (
                q.data.steps.map((s, i) => (
                  <details className="step" key={s.id}>
                    <summary>
                      <span className="step-index">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <strong>{s.id}</strong>
                      <State value={s.state} />
                      <span className="approval">
                        {s.approved ? (
                          <>
                            <Check size={14} />
                            Approved
                          </>
                        ) : (
                          "Not approved"
                        )}
                      </span>
                      <small>{s.attempts} attempts</small>
                    </summary>
                    <div className="step-evidence">
                      <div>
                        <h3>Acceptance checks</h3>
                        <pre>{JSON.stringify(s.checks, null, 2)}</pre>
                      </div>
                      <div>
                        <h3>Reported artifact hashes</h3>
                        <pre>{JSON.stringify(s.artifact_hashes, null, 2)}</pre>
                        <p className="caption">
                          Byte identities reported by the agent; central
                          artifacts are not independently verified.
                        </p>
                      </div>
                    </div>
                  </details>
                ))
              ) : (
                <div className="notice">No step metadata received.</div>
              )}
            </div>
          </section>
          <div className="detail-grid">
            <section className="panel">
              <div className="panel-heading">
                <h2>Audit trail & automated QA</h2>
                <span className="muted">Newest sequence first</span>
              </div>
              <Notice {...events} empty={events.data?.total === 0} />
              {!events.loading && !events.error && events.data && (
                <>
                  <div className="event-list">
                    {events.data.items.map((e) => (
                      <details className="event" key={e.id}>
                        <summary>
                          <span className="event-mark" />
                          <div>
                            <strong>{words(e.kind)}</strong>
                            {e.kind === "qa_reviewed" && (
                              <Qa payload={e.payload} />
                            )}
                            <small>
                              Occurred {date(e.occurred_at)} · Received{" "}
                              {date(e.received_at)}
                            </small>
                          </div>
                          <span className="mono">#{e.sequence}</span>
                        </summary>
                        <pre>{JSON.stringify(e.payload, null, 2)}</pre>
                      </details>
                    ))}
                  </div>
                  <Pagination
                    total={events.data.total}
                    offset={offset}
                    setOffset={setOffset}
                  />
                </>
              )}
            </section>
            <section className="panel review-form-panel">
              <div className="panel-heading">
                <h2>Record a disposition</h2>
                <ClipboardCheck size={19} />
              </div>
              {me.actor.role === "reviewer" ? (
                <form className="review-form" onSubmit={submit}>
                  <p>
                    Append a human review to this run. Earlier decisions and
                    agent state remain unchanged.
                  </p>
                  <label htmlFor="outcome">Outcome</label>
                  <select
                    id="outcome"
                    value={outcome}
                    onChange={(e) => setOutcome(e.target.value)}
                  >
                    <option value="accepted">Accepted</option>
                    <option value="needs_changes">Needs changes</option>
                    <option value="escalated">Escalated</option>
                  </select>
                  <label htmlFor="note">Review note</label>
                  <textarea
                    id="note"
                    maxLength={2000}
                    required
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Describe the evidence behind your decision…"
                  />
                  <small>{note.length}/2000 characters</small>
                  {error && (
                    <p className="error-text" role="alert">
                      {error}
                    </p>
                  )}
                  {saved && (
                    <p className="success-text" role="status">
                      Review recorded.
                    </p>
                  )}
                  <button className="primary" disabled={busy || !note.trim()}>
                    {busy ? "Recording…" : "Record review"}
                    <Check size={17} />
                  </button>
                </form>
              ) : (
                <div className="notice">
                  Viewer access is read only. A reviewer key is required to
                  record a disposition.
                </div>
              )}
            </section>
          </div>
          <Reviews team="" run={id} revision={revision} open={() => {}} />
        </>
      )}
    </>
  );
}
