---
name: architecture-check
description: Review AirportIQ architectural boundaries and repository organization. Use after large features, refactoring, moving files, adding dependencies, or changing backend/frontend responsibilities.
---

# Architecture Check

Review the implementation against the intended architecture.

Read:

CODEBASE_MAP.md

and:

docs/architecture.md

before reviewing.

## 1. Layer Check

Expected flow:

React
→ API
→ Agent / Service
→ Analytics
→ Scoring
→ Provider

Identify violations.

Examples:

BAD:
React calculates opportunity score.

BAD:
FastAPI route contains congestion formula.

BAD:
Provider calculates airport ranking.

BAD:
LLM directly fetches arbitrary APIs.

GOOD:
Each layer owns one responsibility.

## 2. Source-of-Truth Check

Ensure Python deterministic logic still owns:

- metrics
- KPIs
- normalization
- confidence
- scoring
- rankings

## 3. Complexity Check

Look for unnecessary:

- abstractions
- wrappers
- dependencies
- inheritance
- global state
- duplicated logic
- files with mixed responsibilities

Prefer simplification.

## 4. File Organization

Verify files live in the correct directories.

Ensure component/domain boundaries remain understandable.

Do not create miscellaneous "helpers" dumping grounds.

## 5. Dependency Check

For each newly added dependency ask:

Can the standard library or an existing dependency reasonably solve this?

Remove unnecessary dependencies.

## 6. Duplicate Logic

Check whether formulas or validation rules have been duplicated between:

- frontend/backend
- API/service
- service/analytics
- agent/tools

Use one canonical implementation.

## 7. Codebase Map

Compare repository structure against CODEBASE_MAP.md.

If the architecture legitimately changed:

update CODEBASE_MAP.md.

Do not update the map for trivial internal edits.

## 8. Final Report

Report:

- architecture violations
- unnecessary complexity
- misplaced responsibilities
- duplicated logic
- recommended simplifications

Prioritize clarity over theoretical architectural purity.