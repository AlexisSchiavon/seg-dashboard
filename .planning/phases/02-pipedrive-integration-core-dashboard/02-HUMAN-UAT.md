---
status: partial
phase: 02-pipedrive-integration-core-dashboard
source: [02-VERIFICATION.md]
started: 2026-06-14T20:55:00Z
updated: 2026-06-14T20:55:00Z
---

## Current Test

Covered by in-plan human checkpoints (02-01, 02-02, 02-03 all approved during execution).

## Tests

### 1. Resumen KPI colors + ranking arithmetic
expected: Pipeline total in accent color, 3 semantic tiles, ranking rows sum reconciles with global total
result: approved — covered by 02-01 checkpoint

### 2. Funnel stage order + bottleneck copy
expected: 6 stages in canonical order, En ejecución/Cobranza at 0, correct alert text, no "industria"
result: approved — covered by 02-02 checkpoint

### 3. Por talento selector + D-28 section order
expected: talent selector interaction, section order KPIs→Funnel→Deals activos→Categorías de marca→Oportunidades perdidas, no "Fuente de leads"
result: approved — covered by 02-03 checkpoint

### 4. Lost opportunities Spanish label pills
expected: pills show resolved Spanish labels (never integers) with live Pipedrive data
result: approved — covered by 02-03 checkpoint

### 5. Brand donut % by deal count
expected: percentages by deal count (not revenue), legend format "{Categoría} — {pct}% ({count} deals)"
result: approved — covered by 02-03 checkpoint

### 6. Sync button UI behavior
expected: button state transitions, live-pill update, toast, concurrency no-op
result: approved — covered by 02-01 checkpoint

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
