import React,{useEffect,useState} from "react";
import {Activity,ArrowUpRight,ClipboardCheck,Layers,LogOut,ShieldCheck,TriangleAlert} from "lucide-react";
import type {Me} from "./types";
import {api,ApiError,RefreshContext} from "./api";
import {Notice} from "./shared";
import OverviewView from "./views/OverviewView";
import Runs from "./views/Runs";
import Reviews from "./views/Reviews";
import Failures from "./views/Failures";
import RunDetail from "./views/RunDetail";
export default function App() {
  const [refresh, setRefresh] = useState(0);
  const [me, setMe] = useState<Me>();
  const [authLoading, setAuthLoading] = useState(true);
  const [key, setKey] = useState("");
  const [authError, setAuthError] = useState("");
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("Overview");
  const [team, setTeam] = useState("");
  const [selected, setSelected] = useState<string>();
  useEffect(() => {
    api<Me>("/me")
      .then(setMe)
      .catch((error: Error) => {
        if (!(error instanceof ApiError) || ![401, 403].includes(error.status))
          setAuthError("Unable to check your session: " + error.message);
      })
      .finally(() => setAuthLoading(false));
  }, []);
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setAuthError("");
    try {
      await api<Me>("/login", {
        method: "POST",
        body: JSON.stringify({ key }),
      });
      setMe(await api<Me>("/me"));
      setKey("");
    } catch (e) {
      setAuthError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    setBusy(true);
    try {
      await api("/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": me!.csrf_token },
      });
      setMe(undefined);
      setSelected(undefined);
    } catch (e) {
      setAuthError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (authLoading)
    return (
      <main className="login">
        <Notice loading />
      </main>
    );
  if (!me)
    return (
      <main className="login">
        <section className="login-intro">
          <div className="brand">
            <ShieldCheck /> AGENT / AUDIT
          </div>
          <div>
            <span className="eyebrow">EXPERIENCE TOOLKIT</span>
            <h1>
              Evidence for every
              <br />
              agent decision.
            </h1>
            <p>
              Inspect reported work, trace acceptance checks and record a human
              disposition.
            </p>
          </div>
          <small>Self-hosted audit workspace</small>
        </section>
        <form onSubmit={login} className="login-form">
          <span className="eyebrow">WORKSPACE ACCESS</span>
          <h2>Sign in to the audit hub</h2>
          <p>
            Use a viewer or reviewer key provisioned by your workspace operator.
          </p>
          <label htmlFor="key">Access key</label>
          <input
            id="key"
            type="password"
            autoComplete="current-password"
            required
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          {authError && (
            <p role="alert" className="error-text">
              {authError}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
            <ArrowUpRight size={18} />
          </button>
          <small>
            Your access key is exchanged for a secure browser session.
          </small>
        </form>
      </main>
    );
  return (
    <RefreshContext.Provider value={refresh}><div className="shell">
      <aside className="rail">
        <a
          className="brand"
          href="#overview"
          onClick={() => {
            setView("Overview");
            setSelected(undefined);
          }}
        >
          <ShieldCheck />
          <span>
            AGENT
            <br />
            <b>AUDIT</b>
          </span>
        </a>
        <div className="rail-label">WORKSPACE</div>
        <nav>
          {[
            { label: "Overview", icon: Activity },
            { label: "Fleet", icon: Layers },
            { label: "Reviews", icon: ClipboardCheck },
            { label: "Failure patterns", icon: TriangleAlert },
          ].map(({ label, icon: Icon }) => (
            <button
              key={label}
              className={view === label ? "active" : ""}
              onClick={() => {
                setView(label);
                setSelected(undefined);
              }}
            >
              <Icon size={19} />
              {label}
            </button>
          ))}
        </nav>
        <div className="rail-footer">
          <span className="avatar">
            {me.actor.label.slice(0, 2).toUpperCase()}
          </span>
          <div>
            {me.actor.label}
            <small>{me.actor.role}</small>
          </div>
          <button aria-label="Sign out" onClick={logout} disabled={busy}>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>{me.organization.name}</span>
          <div>
            {me.organization.demo && (
              <span className="demo">SYNTHETIC DEMO</span>
            )}
            <span className="scope">Scoped audit access</span>
            <button className="refresh-button" onClick={() => setRefresh(n => n + 1)}>Refresh data</button>
          </div>
        </header>
        <main className="content">
          {authError && (
            <p role="alert" className="error-text">
              {authError}
            </p>
          )}
          {selected ? (
            <RunDetail
              id={selected}
              me={me}
              back={() => setSelected(undefined)}
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">AGENT OPERATIONS / AUDIT HUB</span>
                  <h1>
                    {view === "Overview"
                      ? "A clear view of reported work."
                      : view}
                  </h1>
                  <p>
                    {view === "Overview"
                      ? "Follow the evidence. Find exceptions. Close the review loop."
                      : view === "Fleet"
                        ? "Inspect run progress across your scoped agent fleet."
                        : view === "Reviews"
                          ? "Human decisions, preserved in an append-only history."
                          : "Normalized failure events across reported agent work."}
                  </p>
                </div>
                <label className="team-filter">
                  Team
                  <select
                    value={team}
                    onChange={(e) => setTeam(e.target.value)}
                  >
                    <option value="">All teams</option>
                    {me.teams.map((t) => (
                      <option value={t.id} key={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {view === "Overview" && <OverviewView team={team} />}{" "}
              {(view === "Overview" || view === "Fleet") && (
                <Runs team={team} open={setSelected} />
              )}{" "}
              {view === "Reviews" && <Reviews team={team} open={setSelected} />}{" "}
              {view === "Failure patterns" && <Failures team={team} />}
            </>
          )}
          <footer className="footnote">
            <ShieldCheck size={14} /> Agent-reported metadata · Receipt time is
            distinct from occurrence time · No remote execution
          </footer>
        </main>
      </div>
    </div></RefreshContext.Provider>
  );
}
