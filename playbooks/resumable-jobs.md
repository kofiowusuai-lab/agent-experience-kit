# Resumable paid jobs

## Purpose

Resume completed work safely without repeating paid provider requests unnecessarily.

## Input contract

Scene or job IDs, dependency graph, expected outputs, provider receipts, retry budget, cost limits, and checkpoint location.

## Steps

1. Create one checkpointed step per independently reusable job; record provider job references externally when needed.
2. Before submitting paid work, inspect existing checkpoints, output hashes, and provider job status.
3. Complete each step only after downloading and verifying its output; retain receipts with the evidence package.
4. On restart, resume pending work and reuse valid completed outputs; invalidate downstream work when inputs change.

## Acceptance evidence

Per-job output files and hashes, provider receipts, retry decisions, and status showing reused completed steps.

## Fail and repair rules

Do not resubmit a job merely because a local wait timed out. Reconcile provider state first; bound retries and stop when budgets or permissions are exhausted.

## Synthetic example

A synthetic six-scene render stops after scene four. A restart reuses four verified scene files and submits only the remaining two.

## Limitations

The kit tracks local steps, not provider billing or idempotency. Adapters must handle ambiguous provider responses and avoid duplicate charges.
