---
name: ktor-mobile-client
description: Design, review, and refactor Ktor-based Android and iOS mobile client layers for Kotlin Multiplatform projects. Use when Codex needs to recommend a shared HttpClient structure, choose or wire Android and Darwin engines, centralize plugin setup, diagnose version drift, review mobile networking code for maintainability, or improve MockEngine-friendly testing without depending on live web access.
---

# Ktor Mobile Client

Use this skill for app-facing Ktor client architecture work, not for contributing to the Ktor framework itself.

## Runtime Rules

1. Start by detecting the project's Ktor version and structure before recommending refactors.
2. During normal skill use, rely only on bundled `references/` files and the target-project scan results.
3. Do not require web access or any local Ktor checkout during runtime use.
4. If the detected Ktor version is outside the validated range in `references/version-policy.md`, warn explicitly and keep recommendations conservative.
5. Do not present inferred architecture claims as certain without evidence. Quote the scan result's confidence and evidence paths when the conclusion is heuristic.

## Workflow

1. If a local repo path is available, run `scripts/scan_ktor_mobile_client.py <repo_root>`.
2. Read only the references needed for the current question.
3. Summarize the current structure first: Ktor version, shared-vs-platform layout, client ownership, engine wiring, plugin placement, and test seams.
4. Identify high-signal risks next: version drift, common/platform leakage, duplicated client setup, and missing test seams.
5. Recommend a concrete refactor path that preserves runtime behavior and improves shared-client ownership.
6. End with testing advice, including whether `MockEngine` can be introduced without reshaping production APIs.

## Answer Shape

Respond in this order:

1. Current state
2. Risks or smells
3. Recommended structure
4. Refactor sequence
5. Test strategy
6. Version note when the project is outside the validated range

## Reference Map

Read these files directly from `references/` as needed:

- `architecture.md`: preferred KMP shared-client ownership, DI boundaries, and layering rules.
- `engines.md`: Android and Darwin engine selection, platform placement, and engine-specific cautions.
- `plugins.md`: baseline plugin setup and when to centralize or split plugin configuration.
- `testing-and-refactoring.md`: MockEngine seams, common anti-patterns, and safe refactor order.
- `official-docs-snapshot.md`: stable summaries of official Ktor client docs used for runtime guidance.
- `version-policy.md`: validated version range, drift behavior, and version-sensitive topics.

## Default Recommendations

- Prefer one shared `HttpClient` owner or wrapper in `commonMain`, then inject or select engines from platform source sets.
- Keep Android- or Darwin-specific configuration out of `commonMain`.
- Centralize `ContentNegotiation`, `HttpTimeout`, default request headers, and response validation close to the shared client.
- Add `Auth` and `Logging` only when the product requirements justify them, then keep their setup discoverable and testable.
- Make API wrappers accept an engine or a preconfigured `HttpClient` when you need `MockEngine` tests.

## Guardrails

- Treat SSL pinning, Darwin `challengeHandler`, WebSockets, and SSE as out of scope for v1 unless the user explicitly asks.
- For those out-of-scope topics, give only conservative guidance from bundled references and note that the skill does not maintain deep runtime coverage there.
- Avoid forcing a KMP-shared answer onto clearly platform-separated apps. Distinguish between a preferred default and a mandatory fix.

## Maintenance Rules

- Use official Ktor client docs and the official `ktorio/ktor` source tree, optionally through a local clone, only when updating this skill.
- Refresh `references/official-docs-snapshot.md` and `references/version-policy.md` whenever a doc change or release materially affects covered topics.
- Cross-check behavior-sensitive guidance against official Ktor source and tests before updating bundled references.
- Keep changing facts in `references/` so `SKILL.md` stays stable and short.
