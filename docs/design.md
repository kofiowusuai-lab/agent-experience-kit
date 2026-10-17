# Agent Experience Kit v0.1

Turn operational lessons into explicit task contracts, evidence gates and repeatable evaluations. This is a model-independent local toolkit, not an autonomous agent service.

## Public scope

Python 3.10+, standard-library runtime, MIT licence. Provide a CLI and library, SQLite task checkpoints, file-hash evidence, strict acceptance checks, independent QA verdicts, curated lessons, synthetic regression cases and nine specialist playbooks. No credentials, private transcripts, contact lists, customer identifiers, historical database IDs or private machine paths are shipped. Examples are invented scenarios expressing general failure patterns.

## Contracts and state

A contract has `id`, `origin`, and nonempty `steps`. Each step has `id`, `depends_on`, `required_checks`, `min_artifacts` (default 1), `max_attempts` (default 3) and `requires_approval` (default false). Validate identifiers, duplicate names, cycles, references, boolean fields and numeric limits. Persist contracts, step states, attempts, approvals and evidence in SQLite transactions. A failed attempt consumes budget. Completed work is reusable, but changed or missing evidence invalidates it and its descendants when status is read. An origin mismatch must reject mutation.

Evidence is a regular local file, resolved to an absolute path and hashed with SHA-256. Checks are explicitly supplied boolean assertions, not automatic proof of semantic quality. Approval is a recorded operator assertion, not an authentication system. The toolkit never sends messages, publishes content, executes arbitrary commands or calls a model.

## QA and learning

QA reports have builder/reviewer identities, a declared pass flag, required boolean checks and defects with severity. Any critical defect, failed/missing check or missing required independent reviewer blocks a pass. Lessons contain a generalized failure, correction, acceptance criteria, evidence level and provenance type; only explicitly public, reviewed records may be exported. Detect common secret/contact/path patterns as a supplementary guard, not a guarantee of anonymization. Never import raw Hermes databases automatically.

## Evaluation and docs

Ship synthetic positive and negative QA cases. The local evaluation command checks policy behavior; it does not measure an LLM or real-world business results. Include a documented adapter pattern for external agent outputs. Nine playbooks cover QA, browser verification, creative production, publishing, resumable jobs, conversation operations, lead allocation, sales operations and localization. README includes a working end-to-end offline example and honest limitations.

## Acceptance

Fresh installation runs without provider credentials. Tests cover critical-failure downgrade, false/missing checks, independent review, DAG rejection, origin isolation, attempt limits, restart/resume, changed artifacts, safe lesson export and CLI exit codes. Package build and clean-wheel installation succeed. Public tracked files are reviewed for private data. GitHub CI repeats tests, examples and packaging on supported Python versions.
