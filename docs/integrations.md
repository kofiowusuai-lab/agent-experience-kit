# Integrating an external runtime

Agent Experience Kit is a local guidance and evidence gate. Your runtime supplies the model, browser, renderer, provider client, database access, and messaging transport. None of those executions are built in. Kedolabs maintains this MIT-licensed toolkit without requiring a particular agent platform.

An adapter maps a task into a contract, runs work externally, writes local evidence files, and submits check assertions. Keep credentials in the external runtime; do not put them in contracts, reports, artifacts intended for sharing, or lesson exports.

## CLI handoff

The CLI interface is:

```sh
aek start contract.json --db state.db
aek complete RUN STEP --origin ORIGIN --checks checks.json --artifact file --db state.db
aek status RUN --db state.db
aek review review.json
aek evaluate cases.json
aek lessons export lessons.json --output public.json
```

Replace `RUN`, `STEP`, `ORIGIN`, and `file` with actual values. Use the run identifier returned by `start`. Keep the same explicit database path across checkpoint commands. Consult `aek --help` and each subcommand’s help for optional flags and supported report schemas.

A contract declares `id`, `origin`, and a nonempty `steps` array. Each step declares `id`, `depends_on`, and `required_checks`; it may set `min_artifacts`, `max_attempts`, and `requires_approval`. Build dependency edges around actual prerequisites. Use separate steps for independently reusable outputs. A checks file maps check names to JSON booleans, for example:

```json
{"browser_submission_verified": true, "stored_record_matches": true}
```

Only assert a check after inspecting the corresponding evidence. An adapter should stop on a nonzero exit code, retain diagnostics, and inspect status before deciding whether to retry. Never turn an interrupted provider wait into an automatic paid resubmission.

## Example adapter sequence

1. Convert an approved brief into a contract and call `start`.
2. Ask the external runtime to perform the first ready step using synthetic or properly authorized inputs.
3. Save evidence to a regular local file; review it, then create the boolean checks file.
4. Call `complete` with the contract’s exact origin. Progress only when the gate accepts the step.
5. Call `status` after restarts and before the final handoff. Changed or missing evidence can invalidate completed work and dependent steps.
6. Review the final artifact independently where required. Use `review` to evaluate a QA report and `evaluate` to exercise synthetic policy regression cases.
7. Curate generalized lessons separately and manually review them before calling `lessons export`.

A rejected completion is a gate result, not proof that the external job failed. Reconcile existing outputs and provider state before retrying. Preserve useful artifacts and use bounded attempts. External adapters must handle concurrency, provider idempotency, access controls, destination verification, and publishing approval themselves.

## Trust boundaries

Checks and approval records trust operator-supplied boolean claims. The kit cannot tell whether a screenshot proves consent, a reviewer actually watched a video, or an approval came from an authorized person. Independent reviewer identities are declared strings, not verified accounts.

SHA-256 hashes verify that file bytes match recorded evidence; they do not verify correctness, provenance, copyright, safety, or truth. Origin strings enforce local run matching, not authentication. Protect the SQLite database and evidence files using your operating system and application access controls.

`review` applies QA policy to submitted reports. `evaluate` tests policy behavior against supplied synthetic cases. Neither command evaluates a model’s general quality or predicts business outcomes. An accepted gate does not itself publish, message, charge a provider, or perform any other external action.
