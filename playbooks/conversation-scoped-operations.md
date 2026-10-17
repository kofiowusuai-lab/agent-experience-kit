# Conversation-scoped operations

## Purpose

Keep task state and progress reporting attached to the intended conversation.

## Input contract

Run contract, stable origin string, dependency graph, reporting destination, and completion criteria.

## Steps

1. Bind the run to its origin at creation; pass that origin on every mutation.
2. Have the external reporting adapter verify the destination before posting progress.
3. Update stages from verified evidence and dependency state; keep reporting delivery separate from task execution.
4. Announce completion only after all required dependencies and final checks have passed.

## Acceptance evidence

Origin-bound contract, step status, destination verification record, and final dependency checks.

## Fail and repair rules

Reject mismatched origins. A failed monitor delivery must be reported honestly; it does not justify marking work complete or sending to another conversation.

## Synthetic example

Two synthetic conversations request similar reports. A completion call carrying the other origin is rejected, and the adapter checks its destination before retrying.

## Limitations

Origin strings are routing labels, not authentication or authorization. The kit sends no messages and cannot verify external conversation membership.
