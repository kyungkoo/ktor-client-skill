Checked: 2026-03-15
Sources:
- Official: https://ktor.io/docs/client-engines.html
- Official: https://ktor.io/docs/client-timeout.html
- Official: https://ktor.io/docs/releases.html
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-android/jvm/src/io/ktor/client/engine/android/AndroidEngineConfig.kt
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-darwin/darwin/src/io/ktor/client/engine/darwin/DarwinClientEngineConfig.kt
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-tests/common/test/io/ktor/client/tests/WebSocketTest.kt

# Engines

## Preferred Mobile Setup

For KMP mobile clients, prefer platform-specific engine dependencies and default engine selection at runtime:

- `commonMain`: `ktor-client-core` plus shared plugins.
- `androidMain`: `ktor-client-android` or `ktor-client-okhttp`.
- `iosMain`: `ktor-client-darwin`.
- Shared code can call `HttpClient()` when platform source sets already provide the engine dependencies.

This keeps shared code free from platform imports while still using the right engine on each platform.

## Android Options

### `Android`

Use when you want the platform-focused engine and the configuration surface exposed by `AndroidEngineConfig`.

Maintenance cross-check highlights:

- `connectTimeout`
- `socketTimeout`
- `sslManager`
- `requestConfig`

### `OkHttp`

Use when the app already standardizes on OkHttp or needs OkHttp-specific features and interceptors.

Do not treat `OkHttp` as automatically better than `Android`. It is an integration choice, not a default refactor target by itself.

## iOS Option

### `Darwin`

Use for iOS and other Apple targets. The official docs describe Darwin as using `NSURLSession` under the hood.

Maintenance cross-check highlights:

- `configureRequest`
- `configureSession`
- `handleChallenge`
- `usePreconfiguredSession`

For v1 of this skill, treat `handleChallenge` and custom `NSURLSession` delegates as advanced. Mention them only when the user explicitly needs them.

## Placement Rules

- Do not import Android or Darwin engine classes from `commonMain`.
- Put engine dependencies in platform source sets.
- Keep shared client configuration in one common builder when possible.
- Keep platform-only request/session tuning in platform factories or DI modules.

## Timeout Notes

The official timeout doc shows that timeout support differs by engine. For mobile guidance, the most important caution is:

- Darwin supports request and socket timeout, but not connect timeout in the same way other engines do.

When a codebase assumes all timeout knobs behave identically across platforms, flag it as version- and engine-sensitive.

## When To Flag An Engine Issue

Flag with high confidence when:

- `commonMain` imports Android or Darwin engine packages.
- iOS targets exist but no Darwin engine signals are present.
- Android targets exist but no Android-appropriate engine signals are present.

Flag with medium confidence when:

- The app uses `HttpClient()` with implicit engine selection, but the scanner cannot confirm platform engine dependencies.
- The app mixes multiple engine choices without a clear ownership boundary.
