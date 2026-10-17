"""Versioned SQLAlchemy storage and operator-only credential provisioning."""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Integer,
    Boolean,
    Text,
    JSON,
    UniqueConstraint,
    select,
    Index,
    inspect,
)
from sqlalchemy.pool import StaticPool


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


metadata = MetaData()
versions = Table("hub_schema", metadata, Column("version", Integer, primary_key=True))
organizations = Table(
    "hub_organizations",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("demo", Boolean, nullable=False),
)
teams = Table(
    "hub_teams",
    metadata,
    Column("id", String, primary_key=True),
    Column("org_id", String, index=True, nullable=False),
    Column("name", String, nullable=False),
)
keys = Table(
    "hub_keys",
    metadata,
    Column("id", String, primary_key=True),
    Column("digest", String, unique=True, nullable=False),
    Column("org_id", String, nullable=False),
    Column("team_id", String),
    Column("role", String, nullable=False),
    Column("label", String, nullable=False),
    Column("revoked", Boolean, nullable=False),
)
sessions = Table(
    "hub_sessions",
    metadata,
    Column("digest", String, primary_key=True),
    Column("key_id", String, nullable=False),
    Column("csrf", String, nullable=False),
    Column("expires_at", String, nullable=False),
)
producers = Table(
    "hub_producers",
    metadata,
    Column("id", String, primary_key=True),
    Column("key_id", String, nullable=False),
)
runs = Table(
    "hub_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("org_id", String, index=True, nullable=False),
    Column("team_id", String),
    Column("producer_id", String, nullable=False),
    Column("run_id", String, nullable=False),
    Column("agent", String, nullable=False),
    Column("status", String, nullable=False),
    Column("steps", JSON, nullable=False),
    Column("last_sequence", Integer, nullable=False),
    Column("last_event_at", String, nullable=False),
    Column("last_received_at", String, nullable=False),
    UniqueConstraint("producer_id", "run_id"),
)
events = Table(
    "hub_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("org_id", String, index=True, nullable=False),
    Column("team_id", String),
    Column("run_uuid", String, index=True, nullable=False),
    Column("producer_id", String, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("kind", String, nullable=False),
    Column("occurred_at", String, nullable=False),
    Column("received_at", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("fingerprint", String, nullable=False),
    Column("failure_code", String),
    UniqueConstraint("producer_id", "sequence"),
)
reviews = Table(
    "hub_reviews",
    metadata,
    Column("id", String, primary_key=True),
    Column("org_id", String, index=True, nullable=False),
    Column("team_id", String),
    Column("run_uuid", String, index=True, nullable=False),
    Column("outcome", String, nullable=False),
    Column("note", Text, nullable=False),
    Column("reviewer", String, nullable=False),
    Column("created_at", String, nullable=False),
)

Index(
    "ix_hub_runs_scope_status_time",
    runs.c.org_id,
    runs.c.team_id,
    runs.c.status,
    runs.c.last_received_at,
)
Index(
    "ix_hub_events_scope_time", events.c.org_id, events.c.team_id, events.c.received_at
)
Index("ix_hub_events_run_sequence", events.c.run_uuid, events.c.sequence)
Index(
    "ix_hub_reviews_scope_time",
    reviews.c.org_id,
    reviews.c.team_id,
    reviews.c.created_at,
)


class Database:
    def __init__(self, url):
        options = {}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)

    def initialize(self):
        if inspect(self.engine).has_table("hub_schema"):
            with self.engine.connect() as c:
                existing = c.execute(select(versions.c.version)).scalar()
                if existing not in (None, 1):
                    raise RuntimeError("Unsupported hub schema version")
        metadata.create_all(self.engine)
        with self.engine.begin() as c:
            version = c.execute(select(versions.c.version)).scalar()
            if version is None:
                c.execute(versions.insert().values(version=1))
            elif version != 1:
                raise RuntimeError("Unsupported hub schema version")

    def create_organization(self, name, demo=False):
        ident = uid()
        with self.engine.begin() as c:
            c.execute(organizations.insert().values(id=ident, name=name, demo=demo))
        return ident

    def create_team(self, org_id, name):
        ident = uid()
        with self.engine.begin() as c:
            if not c.execute(
                select(organizations).where(organizations.c.id == org_id)
            ).first():
                raise ValueError("Unknown organization")
            c.execute(teams.insert().values(id=ident, org_id=org_id, name=name))
        return ident

    def issue_key(self, org_id, team_id, role, label):
        if role not in ("ingest", "viewer", "reviewer"):
            raise ValueError("Invalid role")
        if role == "ingest" and not team_id:
            raise ValueError("Ingest keys require a team")
        key = secrets.token_urlsafe(32)
        with self.engine.begin() as c:
            if not c.execute(
                select(organizations).where(organizations.c.id == org_id)
            ).first():
                raise ValueError("Unknown organization")
            if (
                team_id
                and not c.execute(
                    select(teams).where(teams.c.id == team_id, teams.c.org_id == org_id)
                ).first()
            ):
                raise ValueError("Unknown team")
            c.execute(
                keys.insert().values(
                    id=uid(),
                    digest=digest(key),
                    org_id=org_id,
                    team_id=team_id,
                    role=role,
                    label=label,
                    revoked=False,
                )
            )
        return key

    def revoke_key(self, plain_key):
        with self.engine.begin() as c:
            c.execute(
                keys.update()
                .where(keys.c.digest == digest(plain_key))
                .values(revoked=True)
            )

    def close(self):
        self.engine.dispose()
