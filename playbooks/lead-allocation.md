# Lead allocation

## Purpose

Turn country targets and daily capacity into explicit, auditable assignments.

## Input contract

Synthetic or consented lead pool, country weights, total daily quota, eligibility and deduplication rules, owner capacity, and timezone.

## Steps

1. Filter ineligible and duplicate records before allocation; define the daily cutoff.
2. Calculate country allocations proportional to weights; use a documented rounding rule so integer allocations sum to the quota.
3. Assign each selected lead explicitly to one owner and date, respecting owner capacity.
4. Reconcile totals by country and owner; carry shortages forward only under a stated rule.

## Acceptance evidence

Allocation table, rounding rule, duplicate check, quota reconciliation, and explicit owner/date assignments.

## Fail and repair rules

A percentage target is not an assignment. Block completion for unassigned records, duplicated assignments, exceeded capacity, or unexplained quota shortfalls.

## Synthetic example

A synthetic quota of 10 with country weights 50/30/20 assigns 5/3/2 records. Each row names an owner and work date; a shortage is recorded rather than invented.

## Limitations

The kit does not source leads, establish consent, verify contactability, or operate a CRM. Allocation does not authorize outreach.
