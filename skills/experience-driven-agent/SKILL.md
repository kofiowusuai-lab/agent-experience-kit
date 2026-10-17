---
name: experience-driven-agent
description: Use Agent Experience Kit to checkpoint multi-step agent work, apply explicit QA gates and curate reusable operational lessons.
---

# Experience-driven agent

Requires the `aek` command from Agent Experience Kit. The host runtime supplies model and tool access. This skill does not authorize external communication, publication, payment or access changes; follow the user's actual authorization.

1. Read the relevant specialist playbook from the installed repository. Define a task contract with a unique ID, the origin conversation label, dependency steps, acceptance checks and bounded attempts. Keep credentials and contact data outside it.
2. Start or resume with `aek start contract.json --db state.db`. Read `aek status RUN --db state.db` before starting paid work or recovering an interrupted run. Reconcile provider state before resubmitting; never assume a timeout means the provider failed.
3. Perform work using the host's tools. Save immutable evidence files for completed steps. Inspect the actual artifact and results before writing boolean check assertions. Submit with `aek complete RUN STEP --origin ORIGIN --checks checks.json --artifact evidence-file --db state.db`.
4. Record an unsuccessful external attempt with `aek fail RUN STEP --origin ORIGIN --reason "Sanitized failure description" --db state.db`. Respect the budget. A rejected completion check is not a reason to repeat a paid job blindly.
5. Use an independent reviewer where required. The reviewer writes a QA report with explicit required checks and every observed defect. Run `aek review review.json`; only assert the acceptance check if its exit code is 0 and `passed` is true. Never downgrade critical or major defects to warnings to force a pass.
6. For consequential actions, obtain authorization in the host runtime and record its approval assertion with `aek approve RUN STEP --origin ORIGIN --db state.db`. The toolkit does not authenticate approval or execute the action. Verify the actual external result and record its evidence separately.
7. Refresh status before reporting completion. Valid status can still be incomplete: inspect `complete`. Report what is evidenced, what remains and any limitations. Keep progress in the originating conversation.
8. Curate a general lesson when a failure, correction or verified success can improve future work. Distinguish observed, reported and synthetic evidence. Retrieve relevant approved lessons when planning subsequent work; do not treat older instructions as overriding the current user request.

Public lesson export requires manual review and explicit public markers. Never copy raw transcripts, credentials, customer identifiers or private source references into a shared framework. The detector is supplementary.

The toolkit trusts supplied checks and identity strings. Hashes prove matching bytes at a point in time, not truth or semantic quality. Keep the host's permission controls and reviewer judgment in place.
