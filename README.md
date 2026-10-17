# Agent Experience Kit

Turn agent mistakes and successful checks into reusable operating rules, durable checkpoints and regression evaluations.

Built by [Kedolabs](https://kedolabs.com). Model-independent, MIT-licensed, Python 3.10+, with no runtime dependencies or paid API requirements.

This toolkit grew from operating a Telegram-based agent across creative production, software delivery and business workflows. It publishes generalized patterns and invented examples. Private conversations, customer records, credentials and raw agent history are excluded.

## Quick start

```sh
git clone https://github.com/kofiowusuai-lab/agent-experience-kit.git
cd agent-experience-kit
python3 -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
aek demo
aek evaluate
```

Use a Python 3.10 or newer interpreter. `demo` uses temporary files and shows a completed task being invalidated after its evidence changes. `evaluate` runs bundled synthetic policy regressions; it does not call or benchmark a model. The package is installed from this repository; no PyPI release is required.

## What works today

- **Durable checkpoints:** SQLite stores task contracts, dependency state, attempts, approvals and evidence across restarts.
- **Acceptance gates:** required boolean checks, dependency completion and file evidence must be present before a step completes.
- **Evidence freshness:** file hashes are checked when reading or mutating a run; changed or missing artifacts invalidate that step and its descendants.
- **Strict QA:** critical and major defects block a pass; required checks and declared reviewer separation are enforced.
- **Curated lessons:** a structured format separates failures, corrections, acceptance criteria and evidence levels. Public export requires explicit review and screens common sensitive patterns.
- **Nine playbooks:** practical workflows for external agents, plus synthetic regression cases you can extend.

The runtime records and gates work performed elsewhere. It does not run agents, browsers, renderers, messaging clients, outreach or publishing tools.

## Walk through a task

The included contract separates production, verification and an approved handoff. The checks file contains **invented assertions for this demonstration**; in a real adapter, write each assertion only after inspecting its evidence.

```sh
aek start examples/contract.json
aek complete demo-job produce --origin local:demo --checks examples/checks.json --artifact examples/artifact.txt
aek review examples/review.json
aek complete demo-job verify --origin local:demo --checks examples/checks.json --artifact examples/artifact.txt
aek approve demo-job handoff --origin local:demo
aek complete demo-job handoff --origin local:demo --checks examples/checks.json --artifact examples/artifact.txt
aek status demo-job
```

State defaults to `.aek/state.db`. Pass `--db PATH` to each state command to use another database. Repeating `start` with the same ID and contract resumes the run. Repeating an identical completed step is idempotent. A changed contract needs a new run ID.

For a failed external attempt, record it with `aek fail demo-job produce --origin local:demo --reason "Provider timed out"`. Failed attempts and first successful completions each consume one attempt; rejected gate submissions do not. Default budget: three attempts per step. Invalidation preserves consumed attempts and resets approvals. If exhausted, investigate before deliberately creating a new run ID. The kit cannot observe unreported external retries.

Artifacts resolve relative to the current working directory and are stored as absolute local paths. Keep evidence files available at those paths across restarts. Use unique, immutable evidence files per step: overwriting a shared file can invalidate multiple steps. `min_artifacts: 0` explicitly permits a step without file evidence; use this only where the task contract justifies it.

Exit codes: `0` for a successful command or passing verdict; `1` for a failed QA/evaluation/demo verdict; `2` for malformed input, a rejected state mutation or an I/O error. `status` exits `0` for a valid incomplete run too: inspect its `complete` field.

## Capture experience without publishing private history

Start with a manually curated lesson. Describe the general failure and correction; keep original transcripts and private evidence outside the repository. `examples/lesson.json` shows the schema.

```sh
python -c "import json; from pathlib import Path; lesson=json.loads(Path('examples/lesson.json').read_text()); Path('lessons.json').write_text(json.dumps([lesson]))"
aek lessons validate lessons.json
aek lessons export lessons.json --output public-lessons.json
```

Export never overwrites an existing output file. Extra source fields are excluded by an allowlist. Pattern detection catches some contacts, private paths and credentials; it cannot guarantee anonymization. Explicit manual review is still required. See [privacy guidance](docs/privacy.md).

## Specialist playbooks

| Playbook | Use it for |
|---|---|
| [Independent QA](playbooks/independent-qa.md) | Blocking defects, reviewer separation and acceptance evidence |
| [Browser-to-database verification](playbooks/browser-to-database.md) | Testing actual user journeys rather than only APIs |
| [Creative video](playbooks/creative-video.md) | Story variation, style consistency, timing and targeted repair |
| [Publishing](playbooks/publishing.md) | Correct masters, caption policy and verified external handoff |
| [Resumable jobs](playbooks/resumable-jobs.md) | Preserving completed work after interruptions |
| [Conversation operations](playbooks/conversation-scoped-operations.md) | Task routing and truthful progress |
| [Lead allocation](playbooks/lead-allocation.md) | Deduplication, ownership, quotas and test cohorts |
| [Sales operations](playbooks/sales-operations.md) | Authoritative offers, supported claims and outreach boundaries |
| [Localization](playbooks/localization.md) | Reusing approved sources across languages and ratios |

## Bring your own agent

Hermes, Codex or any other runtime can invoke the CLI or import `Store`, `evaluate_review`, `validate_lesson`, `export_lessons` and `evaluate_cases` from their respective modules. The external adapter supplies tools, reviewers and evidence. There is no provider-specific connector in v0.1. See [integration guidance](docs/integrations.md) and [JSON contracts](docs/contracts.md).

For runtimes that support `SKILL.md`, copy [the experience-driven agent skill](skills/experience-driven-agent/SKILL.md) into the runtime's skill directory and keep this repository available for its playbooks. Other runtimes can use the same text as operating instructions. Installation conventions differ by runtime; the toolkit does not change your running agent automatically.

## Trust and limitations

Boolean checks and approval records are operator assertions. Reviewer and origin strings are not authenticated identities. SHA-256 detects changed bytes, not truthful content or a correct customer experience. File hashing is a point-in-time check; adapters must control concurrent writes and protect the database. An agent that fabricates its checks can still pass them.

Synthetic evaluations test these deterministic policies, not intelligence, creative quality or business outcomes. Playbooks describe workflows that require external integrations. This is an alpha toolkit; it does not promise autonomous reliability or revenue improvements.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
aek evaluate
aek demo
python -m pip install build
python -m build
```

See [contributing](CONTRIBUTING.md), [security](SECURITY.md) and the [MIT licence](LICENSE).
