---
name: verify-feature
description: Verify a newly implemented or modified AirportIQ feature end-to-end. Use after implementing features, bug fixes, API changes, or meaningful UI changes.
---

# Verify Feature

Verify the feature rather than assuming implementation correctness.

## Step 1 — Understand the Change

Identify:

- files changed
- feature goal
- expected behavior
- relevant architecture layer

Read docs/CODEBASE_MAP.md if the feature crosses multiple layers.

## Step 2 — Static Checks

Backend changes:

Run the appropriate Python checks and tests.

Frontend changes:

Run:

- TypeScript checking
- relevant tests
- production build

Fix introduced errors.

Do not fix unrelated repository problems unless necessary.

## Step 3 — Backend Verification

If backend behavior changed:

Verify the relevant endpoint or function.

Check:

- valid input
- invalid input
- missing data
- malformed data when relevant
- expected structured response

For scoring changes, confirm that repeated identical inputs produce identical outputs.

## Step 4 — Frontend Verification

If UI behavior changed:

Verify:

- loading state
- success state
- error state
- missing-data state

Ensure important backend fields are displayed correctly.

## Step 5 — Guardrail Verification

Ask:

- Did any number move from Python into LLM reasoning?
- Can the LLM modify deterministic results?
- Is missing data still explicit?
- Are assumptions preserved?
- Are sources preserved?
- Is confidence still deterministic?

## Step 6 — Regression Check

Run the most relevant existing tests.

Do not unnecessarily run expensive unrelated workflows.

## Step 7 — Report

Summarize:

- what was verified
- tests executed
- failures discovered
- fixes made
- remaining limitations

Do not claim success unless verification actually passed.