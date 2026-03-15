Checked: 2026-03-15
Sources:
- Official: https://ktor.io/docs/client-serialization.html
- Official: https://ktor.io/docs/client-auth.html
- Official: https://ktor.io/docs/client-timeout.html
- Official: https://ktor.io/docs/client-logging.html
- Official: https://ktor.io/docs/client-response-validation.html
- Official: https://ktor.io/docs/client-requests.html
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-plugins/ktor-client-auth/common/test/io/ktor/client/plugins/auth/AuthTest.kt
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-plugins/ktor-client-content-negotiation/common/test/io/ktor/client/plugins/ContentNegotiationTests.kt

# Plugins

## Baseline Mobile Stack

For a typical mobile app client, start by evaluating these plugins:

- `ContentNegotiation`
- `HttpTimeout`
- `HttpResponseValidator` or `expectSuccess`
- `DefaultRequest`

Add only when justified:

- `Auth`
- `Logging`
- `HttpCookies`

## Placement Rules

- Install shared plugins near the shared client owner, not inside each repository.
- Keep plugin setup discoverable in one or two obvious places.
- Avoid repeating the same `install(...)` blocks across multiple production files unless clients intentionally serve different backends or trust boundaries.

## `ContentNegotiation`

Use when code sends or receives typed bodies.

Guidance:

- Pair `ktor-client-content-negotiation` with the concrete serialization artifact you actually use.
- In KMP apps, keep shared serializer configuration in `commonMain` when both platforms use the same DTO model.
- If the code uses `setBody(...)` with JSON DTOs or typed `.body()` calls but no serializer installation is visible, treat that as a medium-confidence risk.

## `Auth`

Use when a client must attach credentials or tokens at the transport layer.

Guidance:

- Keep token loading/refresh logic out of repositories when possible.
- Prefer one shared auth configuration per backend boundary.
- Do not recommend `Auth` when simple per-request headers are enough.

## `HttpTimeout`

Use when the app needs explicit client-side timeout policy.

Guidance:

- Keep default timeout policy in the shared client builder.
- Allow per-request overrides only for exceptional flows.
- Treat engine-specific timeout behavior as version-sensitive.

## `Logging`

Use for development diagnostics, targeted support builds, or controlled production observability.

Guidance:

- Avoid blanket body logging in production.
- Android commonly needs an SLF4J implementation when relying on JVM-style logging bridges.
- Native targets can use a custom logger such as Napier instead of platform-default stdout-style behavior.

## Response Validation

Prefer an explicit choice:

- `expectSuccess = true` for baseline non-2xx failure handling.
- `HttpResponseValidator` when the app needs richer mapping or must inspect 2xx bodies for API-level errors.

When a codebase has hand-written status checks in many repositories, recommend centralizing transport-level validation first.
