"""JSON-oriented local CLI. No provider access or arbitrary command execution."""

import argparse
from importlib import resources
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

from . import __version__


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def parser():
    root = argparse.ArgumentParser(prog="aek", description=__doc__)
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("start", "status", "complete", "approve", "fail"):
        command = commands.add_parser(name)
        command.add_argument("contract" if name == "start" else "run")
        command.add_argument("--db", default=".aek/state.db")
        if name in ("complete", "approve", "fail"):
            command.add_argument("step")
            command.add_argument("--origin", required=True)
        if name == "complete":
            command.add_argument("--checks", required=True, help="JSON object of boolean assertions")
            command.add_argument("--artifact", action="append", default=[])
        if name == "fail":
            command.add_argument("--reason", required=True)
    review = commands.add_parser("review")
    review.add_argument("report")
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("cases", nargs="?", help="Defaults to bundled synthetic policy cases")
    lessons = commands.add_parser("lessons").add_subparsers(dest="action", required=True)
    for action in ("validate", "export"):
        command = lessons.add_parser(action)
        command.add_argument("input", help="JSON array of curated lessons")
        if action == "export":
            command.add_argument("--output", required=True, help="New output file; never overwrites")
    commands.add_parser("demo", help="Run an ephemeral offline checkpoint and QA demonstration")
    return root


def run_demo():
    from .qa import evaluate_review
    from .store import Store

    with tempfile.TemporaryDirectory(prefix="aek-demo-") as directory:
        artifact = Path(directory) / "result.txt"
        artifact.write_text("Synthetic demo artifact.\n", encoding="utf-8")
        store = Store(Path(directory) / "state.db")
        try:
            store.start({"id": "demo", "origin": "local:demo", "steps": [
                {"id": "produce", "required_checks": ["created"]},
                {"id": "verify", "depends_on": ["produce"], "required_checks": ["accepted"]},
            ]})
            store.complete("demo", "produce", "local:demo", {"created": True}, [str(artifact)])
            blocked = evaluate_review({"builder": "producer", "reviewer": "reviewer",
                "declared_pass": True, "required_checks": [], "checks": {},
                "defects": [{"severity": "critical", "description": "Synthetic broken lip-sync"}]})
            good = evaluate_review({"builder": "producer", "reviewer": "reviewer",
                "declared_pass": True, "required_checks": ["timing"], "checks": {"timing": True},
                "defects": []})
            if blocked["passed"] or not good["passed"]:
                raise ValueError("Demo QA behavior did not match the expected policy")
            store.complete("demo", "verify", "local:demo", {"accepted": good["passed"]}, [str(artifact)])
            before = store.status("demo")["complete"]
            artifact.write_text("Mutated after review.\n", encoding="utf-8")
            after = store.status("demo")["complete"]
            return {"passed": before and not after, "critical_defect_blocked": not blocked["passed"],
                    "completed_before_mutation": before, "invalidated_after_mutation": not after,
                    "storage": "temporary; removed when demo exits"}
        finally:
            store.close()


def dispatch(args):
    if args.command in ("start", "status", "complete", "approve", "fail"):
        from .store import Store

        store = Store(args.db)
        try:
            if args.command == "start":
                return store.start(read_json(args.contract)), 0
            if args.command == "status":
                return store.status(args.run), 0
            if args.command == "complete":
                return store.complete(args.run, args.step, args.origin,
                                      read_json(args.checks), args.artifact), 0
            if args.command == "approve":
                return store.approve(args.run, args.step, args.origin), 0
            return store.fail(args.run, args.step, args.origin, args.reason), 0
        finally:
            store.close()
    if args.command == "review":
        from .qa import evaluate_review

        result = evaluate_review(read_json(args.report))
        return result, 0 if result["passed"] else 1
    if args.command == "evaluate":
        from .evaluations import evaluate_cases

        cases = read_json(args.cases) if args.cases else json.loads(
            resources.files("agent_experience_kit").joinpath("data/qa-cases.json").read_text(encoding="utf-8"))
        result = evaluate_cases(cases)
        return result, 0 if result["passed"] else 1
    if args.command == "lessons":
        from .lessons import export_lessons, validate_lesson

        values = read_json(args.input)
        if not isinstance(values, list):
            raise ValueError("Lesson input must be a JSON array")
        result = export_lessons(values) if args.action == "export" else [validate_lesson(x) for x in values]
        if args.action == "export":
            with open(args.output, "x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
            return {"exported": len(result), "output": args.output}, 0
        return {"validated": len(result)}, 0
    result = run_demo()
    return result, 0 if result["passed"] else 1


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result, code = dispatch(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return code
    except (ValueError, OSError, sqlite3.Error) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
