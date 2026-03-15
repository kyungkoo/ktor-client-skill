Checked: 2026-03-15
Sources:
- Official: https://ktor.io/docs/client-engines.html
- Official: https://ktor.io/docs/client-dependencies.html
- Official: https://ktor.io/docs/client-requests.html
- Official: https://ktor.io/docs/client-testing.html
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-core/common/src/io/ktor/client/HttpClient.kt
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-mock/common/src/io/ktor/client/engine/mock/MockEngineConfig.kt

# Architecture

## Preferred Default

Use one shared networking entry point in `commonMain` and keep platform engine choice in platform source sets.

Typical shape:

1. `commonMain` owns shared request policy, serializers, error mapping, and API wrappers.
2. `androidMain` provides an Android-capable engine dependency and any Android-only tuning.
3. `iosMain` provides a Darwin engine dependency and any iOS-only tuning.
4. Tests inject `MockEngine` or a preconfigured `HttpClient`.

## Ownership Rules

- Prefer one long-lived `HttpClient` owner per backend or trust boundary.
- Inject the client into repositories and data sources instead of constructing `HttpClient()` inside leaf classes.
- Keep request-building code near the API wrapper, not scattered across repositories and view models.
- If multiple backends need materially different auth, headers, or serializers, split at the wrapper/client-owner boundary rather than cloning request code in feature classes.

## DI Boundaries

- A DI container or factory may own `HttpClient` construction.
- Repositories should depend on a preconfigured client or a small API abstraction.
- Platform code should provide engines, certificates, or OS integrations, then hand them to shared code.
- Shared code should not import `io.ktor.client.engine.android.*` or `io.ktor.client.engine.darwin.*`.

## Shared-Layer Smells

- Multiple production files each call `HttpClient(...)` with near-identical plugin setup.
- `commonMain` directly references Android or Darwin engine classes.
- Repository or service classes construct their own client instead of receiving one.
- Shared code mixes transport concerns, DTO serialization, and domain mapping in the same function.
- Tests cannot swap the engine because production constructors hide `HttpClient` creation.

## Good Refactor Targets

- Extract a `createHttpClient(...)` or `AppHttpClientFactory` function from duplicated builders.
- Extract a thin API client class that takes `HttpClient` or `HttpClientEngine`.
- Move default headers, base URL, and shared serializers into one place.
- Keep response-to-domain mapping outside the raw transport client when it reduces coupling.

## Review Prompts

When reviewing a project, answer these first:

1. Where is the production `HttpClient` created?
2. How many distinct client owners exist?
3. Which concerns are common across Android and iOS?
4. Which concerns are truly platform-specific?
5. Can tests replace the engine without editing production code?
