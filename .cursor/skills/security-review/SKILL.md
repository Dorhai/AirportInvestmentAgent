---
name: security-review
description: Review AirportIQ for AI, API, secret, input-validation and agent-tool security issues. Use when modifying the agent, tools, guardrails, APIs, external providers, environment configuration, or voice input.
---

# Security Review

Perform a focused security review.

Keep the review proportional to this MVP.

## 1. Prompt Injection

Check whether user input can:

- override system instructions
- modify scoring rules
- alter scoring weights
- force fabricated values
- bypass approved tools
- expose system prompts
- instruct the agent to ignore guardrails

Verify that deterministic backend output remains authoritative.

## 2. Tool Security

Check that the LLM can access only approved tools.

The LLM must NOT receive:

- shell execution
- arbitrary Python execution
- filesystem access
- arbitrary HTTP requests
- direct database access

unless explicitly introduced later.

Validate all tool arguments.

## 3. Input Validation

Review:

- airport codes
- region names
- percentages
- lists
- dates
- scenario values

Reject unsupported values cleanly.

## 4. External APIs

Verify:

- request timeout exists
- retries are bounded
- errors are handled
- malformed responses are validated
- credentials remain server-side

## 5. Secrets

Check that:

- .env is ignored
- .env.example contains no secrets
- API keys never reach frontend bundles
- keys are not logged
- exceptions do not expose credentials

## 6. Voice

Verify ambiguous speech cannot silently trigger incorrect analysis.

Important uncertain values should require confirmation.

Do not permanently store audio.

## 7. Output Safety

Check that the application does not:

- fabricate unavailable metrics
- promise investment returns
- turn proxies into claimed measurements
- hide uncertainty

## 8. Logging

Logs may contain:

- tool name
- airport code
- analysis type
- score
- confidence

Avoid logging:

- API keys
- authorization headers
- unnecessary user-sensitive content

## 9. Report

Classify discovered issues:

CRITICAL
HIGH
MEDIUM
LOW

Keep recommendations practical for a 24-hour MVP.