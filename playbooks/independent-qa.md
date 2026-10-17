# Independent QA

## Purpose

Keep a builder’s completion claim separate from an evidence-based release verdict.

## Input contract

Artifact, intended behavior, named builder and reviewer, required checks, severity rubric, and approval owner.

## Steps

1. Give the reviewer the acceptance contract and final artifact; record who built and who reviewed it.
2. Inspect the actual output, including audio and motion where relevant. List defects before assigning the overall verdict.
3. Block passing for any critical defect, missing or false required check, or missing required independent reviewer.
4. Repair the artifact and repeat affected checks; retain the earlier failed report for traceability.

## Acceptance evidence

Final artifact hash, reviewer identity, check results, defect severities, and review report.

## Fail and repair rules

Never downgrade a critical defect to obtain a pass. If independent review is unavailable, report blocked rather than self-certifying independence.

## Synthetic example

A synthetic presenter clip has visibly misaligned speech. The reviewer marks lip-sync critical; an otherwise polished clip fails until a replacement is reviewed.

## Limitations

Identity fields and boolean checks are declarations. The kit cannot verify reviewer independence or detect lip-sync itself.
