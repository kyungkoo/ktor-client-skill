Checked: 2026-03-15
Sources:
- https://ktor.io/docs/client-engines.html
- https://ktor.io/docs/client-dependencies.html
- https://ktor.io/docs/client-requests.html
- https://ktor.io/docs/client-serialization.html
- https://ktor.io/docs/client-auth.html
- https://ktor.io/docs/client-timeout.html
- https://ktor.io/docs/client-logging.html
- https://ktor.io/docs/client-response-validation.html
- https://ktor.io/docs/client-testing.html
- https://ktor.io/docs/releases.html
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/VERSION

# Official Docs Snapshot

This file is a runtime-safe summary of the Ktor client docs used to author the skill. Use it during normal skill execution instead of live browsing.

## Snapshot Context

- Docs family: Ktor Documentation
- Observed doc version banner: `Ktor 3.4.1 Help`
- Release page latest listed version: `3.4.1` on `2026-03-04`
- Release page also lists `3.3.3` as the latest `3.3.x` patch on `2025-11-26`
- Maintenance cross-check repo: `https://github.com/ktorio/ktor`

Runtime note:

- This snapshot was authored from the current docs, then maintenance-checked so the skill can safely cover `3.3.3` for low-drift mobile guidance such as shared client ownership, source-set engine placement, centralized plugin setup, and `MockEngine` seams.
- When advice depends on engine quirks or timeout semantics, keep it version-sensitive even for `3.3.3`.

## Client Engines

- Source URL: https://ktor.io/docs/client-engines.html
- Doc page title: Client engines
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-android/jvm/src/io/ktor/client/engine/android/AndroidEngineConfig.kt`
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-darwin/darwin/src/io/ktor/client/engine/darwin/DarwinClientEngineConfig.kt`

Summary:

- Ktor client is multiplatform and selects an engine per target platform.
- In multiplatform mobile projects, official docs explicitly allow adding Android engine dependencies to `androidMain` and Darwin engine dependencies to `iosMain`, then using `HttpClient()` without passing an engine in shared code.
- Android and OkHttp are both viable on Android. Darwin is the native Apple-target engine.

## Adding Client Dependencies

- Source URL: https://ktor.io/docs/client-dependencies.html
- Doc page title: Adding client dependencies
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/VERSION`

Summary:

- `ktor-client-core` belongs in shared code.
- Engine dependencies belong in target-specific source sets for KMP.
- The docs show `gradle/libs.versions.toml`, BOM usage, and the published version catalog as version-centralization options.
- Runtime guidance should prefer consistent Ktor versions across all modules.

## Making Requests

- Source URL: https://ktor.io/docs/client-requests.html
- Doc page title: Making requests
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-core/common/src/io/ktor/client/HttpClient.kt`

Summary:

- Use typed request builders, default headers, and body serialization through shared configuration.
- Prefer `DefaultRequest` for shared base URL and headers rather than duplicating request setup in repositories.
- Typed bodies imply a serialization setup decision, usually `ContentNegotiation`.

## Content Negotiation And Serialization

- Source URL: https://ktor.io/docs/client-serialization.html
- Doc page title: Content negotiation and serialization in Ktor Client
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-plugins/ktor-client-content-negotiation/common/test/io/ktor/client/plugins/ContentNegotiationTests.kt`

Summary:

- `ContentNegotiation` handles both media type negotiation and serializer wiring.
- JSON support commonly pairs `ktor-client-content-negotiation` with `ktor-serialization-kotlinx-json`.
- The docs keep serializer choice explicit; the skill should not assume Gson or Jackson unless the project already uses them.

## Authentication

- Source URL: https://ktor.io/docs/client-auth.html
- Doc page title: Authentication and authorization in Ktor Client
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-plugins/ktor-client-auth/common/test/io/ktor/client/plugins/auth/AuthTest.kt`

Summary:

- The `Auth` plugin supports basic, digest, and bearer flows.
- Use it when credentials are transport-level concerns and should be shared by the client boundary.
- Do not recommend it for every project by default; simple per-request headers are sometimes enough.

## Timeout

- Source URL: https://ktor.io/docs/client-timeout.html
- Doc page title: Timeout
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-darwin/darwin/src/io/ktor/client/engine/darwin/TimeoutUtils.kt`

Summary:

- `HttpTimeout` lives in client core and does not require a separate plugin artifact.
- Timeout support differs by engine.
- The docs explicitly show Darwin lacking the same connect-timeout support as some other engines.

## Logging

- Source URL: https://ktor.io/docs/client-logging.html
- Doc page title: Logging in Ktor Client
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-plugins/ktor-client-logging/common/src/io/ktor/client/plugins/logging/Logging.kt`

Summary:

- `Logging` is a client plugin, but platform logging backends differ.
- Android commonly uses an SLF4J Android backend.
- Multiplatform apps may prefer a custom logger abstraction instead of platform-default behavior.

## Response Validation

- Source URL: https://ktor.io/docs/client-response-validation.html
- Doc page title: Response validation
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-tests/common/test/io/ktor/client/tests/HttpResponseValidatorTest.kt`

Summary:

- Ktor does not validate responses by status code by default.
- `expectSuccess = true` is the simplest baseline.
- `HttpResponseValidator` is the richer option when apps need transport-level mapping for 2xx or non-2xx responses.

## Testing

- Source URL: https://ktor.io/docs/client-testing.html
- Doc page title: Testing in Ktor Client
- Checked: 2026-03-15
- Maintenance cross-check sources:
  - `https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-mock/common/src/io/ktor/client/engine/mock/MockEngineConfig.kt`

Summary:

- `MockEngine` is the official transport-level test seam.
- The docs recommend sharing client configuration and swapping only the engine in tests.
- The skill should prefer refactors that make engine injection possible rather than recommending live-network tests.
