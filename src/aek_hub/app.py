"""Authenticated, scoped metadata audit API."""

import json, os, secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, and_, or_, func, case, text
from sqlalchemy.exc import IntegrityError, DBAPIError
from .database import (
    Database,
    organizations,
    teams,
    keys,
    sessions,
    producers,
    runs,
    events,
    reviews,
    digest,
    uid,
    now,
)
from .models import Batch, Login, Review

COOKIE = "aek_session"


def create_app(
    database_url, origin="http://127.0.0.1:8787", static_dir=None, secure_cookie=True
):
    db = Database(database_url)
    db.initialize()

    @asynccontextmanager
    async def lifespan(app):
        yield
        db.close()

    app = FastAPI(title="Agent audit hub", lifespan=lifespan)
    app.state.database = db

    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.middleware("http")
    async def bounds(request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            size = 0
            parts = []
            async for part in request.stream():
                size += len(part)
                if size > 2_000_000:
                    return JSONResponse(
                        {"detail": "Request too large"}, status_code=413
                    )
                parts.append(part)
            request._body = b"".join(parts)

            async def receive():
                return {
                    "type": "http.request",
                    "body": request._body,
                    "more_body": False,
                }

            request._receive = receive
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def origin_check(request):
        if request.headers.get("origin") != origin:
            raise HTTPException(403, "Origin rejected")

    def auth(request: Request):
        header = request.headers.get("authorization", "")
        with db.engine.connect() as c:
            if header:
                if not header.startswith("Bearer "):
                    raise HTTPException(401, "Authentication required")
                key = (
                    c.execute(
                        select(keys).where(
                            keys.c.digest == digest(header[7:]), keys.c.revoked == False
                        )
                    )
                    .mappings()
                    .first()
                )
                session = None
            else:
                session = (
                    c.execute(
                        select(sessions).where(
                            sessions.c.digest
                            == digest(request.cookies.get(COOKIE, "")),
                            sessions.c.expires_at > now(),
                        )
                    )
                    .mappings()
                    .first()
                )
                key = (
                    c.execute(
                        select(keys).where(
                            keys.c.id == session["key_id"], keys.c.revoked == False
                        )
                    )
                    .mappings()
                    .first()
                    if session
                    else None
                )
            if not key:
                raise HTTPException(401, "Authentication required")
            actor = dict(key)
            actor["session"] = dict(session) if session else None
            return actor

    def reader(actor=Depends(auth)):
        if actor["role"] not in ("viewer", "reviewer"):
            raise HTTPException(403, "Read access required")
        return actor

    def scope(table, actor, team_id=None):
        conditions = [table.c.org_id == actor["org_id"]]
        if actor["team_id"]:
            conditions.append(table.c.team_id == actor["team_id"])
        if team_id:
            conditions.append(table.c.team_id == team_id)
        return and_(*conditions)

    def scoped_rows(c, table, actor, team_id=None):
        return list(
            c.execute(select(table).where(scope(table, actor, team_id))).mappings()
        )

    def run_get(c, ident, actor):
        row = (
            c.execute(select(runs).where(runs.c.id == ident, scope(runs, actor)))
            .mappings()
            .first()
        )
        if not row:
            raise HTTPException(404, "Run not found")
        return row

    def team_name(c, ident):
        return (
            c.execute(select(teams.c.name).where(teams.c.id == ident)).scalar()
            if ident
            else None
        )

    def run_json(c, row):
        steps = row["steps"]
        count = row.get("review_count")
        if count is None:
            count = c.execute(
                select(func.count())
                .select_from(reviews)
                .where(
                    reviews.c.run_uuid == row["id"], reviews.c.org_id == row["org_id"]
                )
            ).scalar_one()
        name = (
            row.get("team_name") if "team_name" in row else team_name(c, row["team_id"])
        )
        return {
            k: row[k]
            for k in (
                "id",
                "run_id",
                "producer_id",
                "agent",
                "team_id",
                "status",
                "last_event_at",
                "last_received_at",
                "last_sequence",
            )
        } | dict(
            team_name=name,
            step_count=len(steps),
            completed_steps=sum(s["state"] in ("completed", "done") for s in steps),
            attempts=sum(s["attempts"] for s in steps),
            review_count=count,
        )

    def run_select():
        review_count = (
            select(func.count())
            .select_from(reviews)
            .where(reviews.c.run_uuid == runs.c.id, reviews.c.org_id == runs.c.org_id)
            .correlate(runs)
            .scalar_subquery()
        )
        return select(
            runs, teams.c.name.label("team_name"), review_count.label("review_count")
        ).outerjoin(
            teams, and_(teams.c.id == runs.c.team_id, teams.c.org_id == runs.c.org_id)
        )

    def review_select():
        return (
            select(
                reviews,
                runs.c.run_id.label("run_label"),
                teams.c.name.label("team_name"),
            )
            .join(
                runs,
                and_(
                    runs.c.id == reviews.c.run_uuid, runs.c.org_id == reviews.c.org_id
                ),
            )
            .outerjoin(
                teams,
                and_(
                    teams.c.id == reviews.c.team_id, teams.c.org_id == reviews.c.org_id
                ),
            )
        )

    def review_json(c, row):
        run = (
            row.get("run_label")
            if "run_label" in row
            else c.execute(
                select(runs.c.run_id).where(
                    runs.c.id == row["run_uuid"], runs.c.org_id == row["org_id"]
                )
            ).scalar()
        )
        return {
            k: row[k]
            for k in ("id", "team_id", "outcome", "note", "reviewer", "created_at")
        } | dict(
            run_id=row["run_uuid"],
            run_label=run,
            team_name=(
                row.get("team_name")
                if "team_name" in row
                else team_name(c, row["team_id"])
            ),
        )

    def me(actor, csrf):
        with db.engine.connect() as c:
            org = (
                c.execute(
                    select(organizations).where(organizations.c.id == actor["org_id"])
                )
                .mappings()
                .one()
            )
            ts = (
                c.execute(select(teams).where(scope(teams, actor))).mappings()
                if not actor["team_id"]
                else c.execute(
                    select(teams).where(
                        teams.c.org_id == actor["org_id"],
                        teams.c.id == actor["team_id"],
                    )
                ).mappings()
            )
            return dict(
                organization=dict(org),
                actor=dict(label=actor["label"], role=actor["role"]),
                teams=[dict(id=t["id"], name=t["name"]) for t in ts],
                csrf_token=csrf,
            )

    @app.get("/health")
    def health():
        try:
            with db.engine.connect() as c:
                c.execute(text("SELECT 1"))
            return {"ready": True}
        except Exception:
            return JSONResponse({"ready": False}, status_code=503)

    @app.post("/api/login")
    def login(body: Login, request: Request):
        origin_check(request)
        with db.engine.begin() as c:
            key = (
                c.execute(
                    select(keys).where(
                        keys.c.digest == digest(body.key), keys.c.revoked == False
                    )
                )
                .mappings()
                .first()
            )
            if not key or key["role"] not in ("viewer", "reviewer"):
                raise HTTPException(401, "Invalid dashboard key")
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            c.execute(
                sessions.insert().values(
                    digest=digest(token),
                    key_id=key["id"],
                    csrf=csrf,
                    expires_at=(
                        datetime.now(timezone.utc) + timedelta(hours=8)
                    ).isoformat(),
                )
            )
        response = JSONResponse(me(key, csrf))
        response.set_cookie(
            COOKIE,
            token,
            max_age=28800,
            httponly=True,
            secure=secure_cookie,
            samesite="strict",
            path="/",
        )
        return response

    @app.get("/api/me")
    def who(actor=Depends(reader)):
        return me(actor, actor["session"]["csrf"] if actor["session"] else "")

    def mutation(request, actor):
        if actor["session"]:
            origin_check(request)
            if not secrets.compare_digest(
                request.headers.get("x-csrf-token", ""), actor["session"]["csrf"]
            ):
                raise HTTPException(403, "CSRF rejected")

    @app.post("/api/logout")
    def logout(request: Request, actor=Depends(reader)):
        mutation(request, actor)
        if actor["session"]:
            with db.engine.begin() as c:
                c.execute(
                    sessions.delete().where(
                        sessions.c.digest == actor["session"]["digest"]
                    )
                )
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.post("/api/ingest")
    def ingest(body: Batch, request: Request, actor=Depends(auth)):
        if actor["role"] != "ingest" or not request.headers.get("authorization"):
            raise HTTPException(403, "Ingest key required")
        accepted = []
        duplicates = []
        try:
            with db.engine.begin() as c:
                # Acquire/provision each producer in stable order before processing.
                # This prevents opposite-order batches from deadlocking on row locks.
                for pid in sorted({str(event.producer_id) for event in body.events}):
                    owner = (
                        c.execute(
                            select(producers)
                            .where(producers.c.id == pid)
                            .with_for_update()
                        )
                        .mappings()
                        .first()
                    )
                    if owner and owner["key_id"] != actor["id"]:
                        raise HTTPException(409, "Producer owned by another key")
                    if not owner:
                        c.execute(producers.insert().values(id=pid, key_id=actor["id"]))
                for event in body.events:
                    wire = event.model_dump(mode="json", exclude_none=True)
                    fingerprint = digest(
                        json.dumps(wire, sort_keys=True, separators=(",", ":"))
                    )
                    pid = str(event.producer_id)
                    eid = str(event.id)
                    existing = (
                        c.execute(select(events).where(events.c.id == eid))
                        .mappings()
                        .first()
                    )
                    if existing:
                        if (
                            existing["fingerprint"] != fingerprint
                            or existing["org_id"] != actor["org_id"]
                        ):
                            raise HTTPException(409, "Event conflict")
                        duplicates.append(eid)
                        continue
                    if c.execute(
                        select(events.c.id).where(
                            events.c.producer_id == pid,
                            events.c.sequence == event.sequence,
                        )
                    ).first():
                        raise HTTPException(409, "Sequence conflict")
                    run = (
                        c.execute(
                            select(runs).where(
                                runs.c.producer_id == pid, runs.c.run_id == event.run_id
                            )
                        )
                        .mappings()
                        .first()
                    )
                    received = now()
                    payload = wire["payload"]
                    values = dict(
                        org_id=actor["org_id"],
                        team_id=actor["team_id"],
                        producer_id=pid,
                        run_id=event.run_id,
                        agent=actor["label"],
                        status=payload["status"],
                        steps=payload["steps"],
                        last_sequence=event.sequence,
                        last_event_at=wire["occurred_at"],
                        last_received_at=received,
                    )
                    if not run:
                        rid = uid()
                        c.execute(runs.insert().values(id=rid, **values))
                    else:
                        if (
                            run["org_id"] != actor["org_id"]
                            or run["team_id"] != actor["team_id"]
                        ):
                            raise HTTPException(409, "Run scope conflict")
                        rid = run["id"]
                        if event.sequence > run["last_sequence"]:
                            c.execute(
                                runs.update()
                                .where(
                                    runs.c.id == rid,
                                    runs.c.last_sequence < event.sequence,
                                )
                                .values(**values)
                            )
                        else:
                            c.execute(
                                runs.update()
                                .where(runs.c.id == rid)
                                .values(last_received_at=received)
                            )
                    code = payload.get("failure_code")
                    if not code and event.kind == "step_failed":
                        code = "external_failure"
                    if (
                        not code
                        and event.kind == "qa_reviewed"
                        and not payload.get("qa", {}).get("passed", True)
                    ):
                        code = "qa_failed"
                    c.execute(
                        events.insert().values(
                            id=eid,
                            org_id=actor["org_id"],
                            team_id=actor["team_id"],
                            run_uuid=rid,
                            producer_id=pid,
                            sequence=event.sequence,
                            kind=event.kind,
                            occurred_at=wire["occurred_at"],
                            received_at=received,
                            payload=payload,
                            fingerprint=fingerprint,
                            failure_code=code,
                        )
                    )
                    accepted.append(eid)
        except IntegrityError:
            raise HTTPException(409, "Concurrent event conflict; retry batch")
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) in ("40P01", "40001"):
                raise HTTPException(
                    409, "Concurrent event conflict; retry batch"
                ) from None
            raise
        return dict(accepted=accepted, duplicates=duplicates)

    @app.get("/api/runs")
    def list_runs(
        team_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        actor=Depends(reader),
    ):
        if status and status not in ("pending", "running", "completed", "failed"):
            raise HTTPException(422, "Invalid status")
        with db.engine.connect() as c:
            conditions = [scope(runs, actor, team_id)]
            if status:
                conditions.append(runs.c.status == status)
            if search:
                conditions.append(
                    or_(
                        func.lower(runs.c.run_id).contains(
                            search.lower(), autoescape=True
                        ),
                        func.lower(runs.c.agent).contains(
                            search.lower(), autoescape=True
                        ),
                    )
                )
            where = and_(*conditions)
            total = c.execute(
                select(func.count()).select_from(runs).where(where)
            ).scalar_one()
            rows = c.execute(
                run_select()
                .where(where)
                .order_by(runs.c.last_received_at.desc(), runs.c.id)
                .limit(limit)
                .offset(offset)
            ).mappings()
            return dict(
                items=[run_json(c, r) for r in rows],
                total=total,
                limit=limit,
                offset=offset,
            )

    @app.get("/api/runs/{ident}")
    def detail(ident: str, actor=Depends(reader)):
        with db.engine.connect() as c:
            row = run_get(c, ident, actor)
            rs = c.execute(
                review_select()
                .where(reviews.c.run_uuid == ident, scope(reviews, actor))
                .order_by(reviews.c.created_at.desc())
                .limit(100)
            ).mappings()
            return dict(
                run=run_json(c, row),
                steps=row["steps"],
                reviews=[review_json(c, r) for r in rs],
            )

    @app.get("/api/runs/{ident}/events")
    def history(
        ident: str,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        actor=Depends(reader),
    ):
        with db.engine.connect() as c:
            run_get(c, ident, actor)
            where = and_(events.c.run_uuid == ident, scope(events, actor))
            total = c.execute(
                select(func.count()).select_from(events).where(where)
            ).scalar_one()
            rs = c.execute(
                select(events)
                .where(where)
                .order_by(events.c.sequence.desc())
                .limit(limit)
                .offset(offset)
            ).mappings()
            return dict(
                items=[
                    {
                        k: r[k]
                        for k in (
                            "id",
                            "kind",
                            "sequence",
                            "occurred_at",
                            "received_at",
                            "payload",
                        )
                    }
                    for r in rs
                ],
                total=total,
                limit=limit,
                offset=offset,
            )

    @app.post("/api/runs/{ident}/reviews")
    def add_review(ident: str, body: Review, request: Request, actor=Depends(reader)):
        if actor["role"] != "reviewer":
            raise HTTPException(403, "Reviewer access required")
        mutation(request, actor)
        with db.engine.begin() as c:
            run = run_get(c, ident, actor)
            row = dict(
                id=uid(),
                org_id=actor["org_id"],
                team_id=run["team_id"],
                run_uuid=ident,
                outcome=body.outcome,
                note=body.note,
                reviewer=actor["label"],
                created_at=now(),
            )
            c.execute(reviews.insert().values(**row))
            return review_json(c, row)

    @app.get("/api/reviews")
    def list_reviews(
        team_id: str | None = None,
        run_id: str | None = None,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        actor=Depends(reader),
    ):
        with db.engine.connect() as c:
            where = scope(reviews, actor, team_id)
            if run_id:
                where = and_(where, reviews.c.run_uuid == run_id)
            total = c.execute(
                select(func.count()).select_from(reviews).where(where)
            ).scalar_one()
            rows = c.execute(
                review_select()
                .where(where)
                .order_by(reviews.c.created_at.desc(), reviews.c.id)
                .limit(limit)
                .offset(offset)
            ).mappings()
            return dict(
                items=[review_json(c, r) for r in rows],
                total=total,
                limit=limit,
                offset=offset,
            )

    def failure_query(actor, team_id):
        return (
            select(
                events.c.failure_code.label("code"),
                func.count().label("count"),
                func.count(func.distinct(events.c.run_uuid)).label("affected_runs"),
                func.max(events.c.received_at).label("last_seen"),
            )
            .where(scope(events, actor, team_id), events.c.failure_code.is_not(None))
            .group_by(events.c.failure_code)
            .order_by(func.count().desc(), events.c.failure_code)
        )

    @app.get("/api/failures")
    def failures(team_id: str | None = None, actor=Depends(reader)):
        with db.engine.connect() as c:
            items = [
                dict(r) for r in c.execute(failure_query(actor, team_id)).mappings()
            ]
            return dict(items=items, total=len(items))

    @app.get("/api/overview")
    def overview(team_id: str | None = None, actor=Depends(reader)):
        with db.engine.connect() as c:
            run_counts = dict(
                c.execute(
                    select(runs.c.status, func.count())
                    .where(scope(runs, actor, team_id))
                    .group_by(runs.c.status)
                ).all()
            )
            counts = {
                status: run_counts.get(status, 0)
                for status in ("completed", "failed", "running", "pending")
            }
            counts["total"] = sum(run_counts.values())
            event_where = scope(events, actor, team_id)
            total, latest, agents_total = c.execute(
                select(
                    func.count(),
                    func.max(events.c.received_at),
                    func.count(func.distinct(events.c.producer_id)),
                ).where(event_where)
            ).one()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            active = c.execute(
                select(func.count(func.distinct(events.c.producer_id))).where(
                    event_where, events.c.received_at >= cutoff
                )
            ).scalar_one()
            reviewed = (
                select(reviews.c.id)
                .where(
                    reviews.c.run_uuid == events.c.run_uuid,
                    scope(reviews, actor, team_id),
                )
                .exists()
            )
            unreviewed = c.execute(
                select(func.count(func.distinct(events.c.run_uuid))).where(
                    event_where, events.c.failure_code.is_not(None), ~reviewed
                )
            ).scalar_one()
            today = datetime.now(timezone.utc).date()
            start = (today - timedelta(days=6)).isoformat()
            day = func.substr(events.c.received_at, 1, 10)
            daily = {
                r[0]: (r[1], r[2])
                for r in c.execute(
                    select(
                        day,
                        func.count(),
                        func.sum(
                            case((events.c.failure_code.is_not(None), 1), else_=0)
                        ),
                    )
                    .where(event_where, events.c.received_at >= start)
                    .group_by(day)
                )
            }
            activity = []
            for delta in range(6, -1, -1):
                date = (today - timedelta(days=delta)).isoformat()
                values = daily.get(date, (0, 0))
                activity.append(dict(date=date, events=values[0], failures=values[1]))
            team_where = [teams.c.org_id == actor["org_id"]]
            if actor["team_id"]:
                team_where.append(teams.c.id == actor["team_id"])
            if team_id:
                team_where.append(teams.c.id == team_id)
            team_counts = (
                select(
                    runs.c.team_id,
                    func.count().label("runs"),
                    func.sum(case((runs.c.status == "failed", 1), else_=0)).label(
                        "failed"
                    ),
                )
                .where(scope(runs, actor, team_id))
                .group_by(runs.c.team_id)
                .subquery()
            )
            team_rows = c.execute(
                select(
                    teams.c.id,
                    teams.c.name,
                    func.coalesce(team_counts.c.runs, 0).label("runs"),
                    func.coalesce(team_counts.c.failed, 0).label("failed"),
                )
                .outerjoin(team_counts, team_counts.c.team_id == teams.c.id)
                .where(*team_where)
            ).mappings()
            failures = [
                dict(code=r["code"], count=r["count"])
                for r in c.execute(failure_query(actor, team_id)).mappings()
            ]
            return dict(
                runs=counts,
                agents=dict(total=agents_total, active=active),
                events_total=total,
                unreviewed_failures=unreviewed,
                latest_ingestion_at=latest,
                activity=activity,
                failures=failures,
                teams=[dict(r) for r in team_rows],
            )

    if static_dir:
        root = Path(static_dir).resolve()
        if (root / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            if path == "api" or path.startswith("api/"):
                raise HTTPException(404, "Not found")
            target = (root / path).resolve()
            if target.is_relative_to(root) and target.is_file():
                return FileResponse(target)
            return FileResponse(root / "index.html")

    return app


def from_env():
    origin = os.environ.get("AEK_PUBLIC_ORIGIN", "http://127.0.0.1:8787")
    parsed = urlparse(origin)
    insecure = os.environ.get("AEK_ALLOW_INSECURE_LOCALHOST") == "1"
    if insecure and (
        parsed.scheme != "http"
        or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError("Insecure cookies require explicit loopback HTTP origin")
    return create_app(
        os.environ["AEK_DATABASE_URL"],
        origin,
        os.environ.get("AEK_STATIC_DIR"),
        secure_cookie=not insecure,
    )
