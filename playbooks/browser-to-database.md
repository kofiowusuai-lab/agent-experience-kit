# Browser-to-database verification

## Purpose

Verify a user action across the rendered interface, request, stored record, and response.

## Input contract

Test environment, synthetic input, consent requirements, expected stored fields, and allowed cleanup procedure.

## Steps

1. Inspect the rendered form, including disabled, hidden, unchecked, and conditionally enabled inputs.
2. Submit through the browser with synthetic values; capture the actual request and visible response.
3. Confirm the resulting database record matches the submitted data and required consent state.
4. Exercise a negative case and verify rejected input does not create an accepted record.

## Acceptance evidence

Browser capture, redacted request summary, synthetic record assertion, and visible success or error state.

## Fail and repair rules

An API-only test cannot satisfy a browser-flow check. If consent is omitted because its input is disabled, repair form behavior and repeat the browser submission.

## Synthetic example

A synthetic signup API accepts consent=true, but the browser disables the checkbox and omits it. The browser-flow gate fails despite the API test passing.

## Limitations

The kit does not control browsers, query databases, validate consent law, or interpret screenshots. External tools and operators supply evidence.
