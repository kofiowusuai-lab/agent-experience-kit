"""Operator commands for the optional, self-hosted audit hub."""
import argparse
import json
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aek-hub", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--organization", required=True)
    init.add_argument("--team", required=True)
    key = commands.add_parser("key")
    key.add_argument("--organization", required=True, help="Organization UUID from init")
    key.add_argument("--team", help="Optional reader scope; required for ingest")
    key.add_argument("--role", choices=["ingest", "viewer", "reviewer"], required=True)
    key.add_argument("--label", required=True, help="Agent or reviewer identity assigned by the operator")
    key.add_argument("--output", help="New private JSON file for the issued key instead of stdout")
    revoke = commands.add_parser("revoke")
    revoke.add_argument("--token-env", default="AEK_REVOKE_KEY")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    demo = commands.add_parser("demo")
    demo.add_argument("--url", default="http://127.0.0.1:8787")
    demo.add_argument("--output", default=".aek/demo-credentials.json")
    args = parser.parse_args(argv)
    try:
        url = os.environ.get("AEK_DATABASE_URL", "").strip()
        if not url:
            raise ValueError("Set AEK_DATABASE_URL before using hub commands")
        if args.command == "serve":
            import uvicorn
            from .app import from_env
            uvicorn.run(from_env(), host=args.host, port=args.port)
            return 0
        if args.command == "demo":
            from .demo import seed_demo
            result = seed_demo(url, args.url, args.output)
        else:
            from .database import Database
            db = Database(url)
            try:
                db.initialize()
                if args.command == "init":
                    org = db.create_organization(args.organization)
                    team = db.create_team(org, args.team)
                    result = {"organization_id": org, "team_id": team}
                elif args.command == "key":
                    if args.output and Path(args.output).exists():
                        raise ValueError("Output already exists; refusing to overwrite credentials")
                    token = db.issue_key(args.organization, args.team, args.role, args.label)
                    result = {"key": token, "role": args.role, "label": args.label}
                    if args.output:
                        write_private_json(args.output, result)
                        result = {"credentials_file": args.output, "role": args.role}
                else:
                    token = os.environ.get(args.token_env, "").strip()
                    if not token:
                        raise ValueError(f"Set {args.token_env} to the key being revoked")
                    db.revoke_key(token)
                    result = {"revoked": True}
            finally:
                db.close()
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


def write_private_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
