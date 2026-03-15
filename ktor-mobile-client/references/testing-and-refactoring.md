Checked: 2026-03-15
Sources:
- Official: https://ktor.io/docs/client-testing.html
- Official: https://ktor.io/docs/client-response-validation.html
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-mock/common/src/io/ktor/client/engine/mock/MockEngineConfig.kt
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-tests/common/test/io/ktor/client/tests/plugins/SerializationTest.kt
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/ktor-client/ktor-client-tests/common/test/io/ktor/client/tests/HttpResponseValidatorTest.kt

# Testing And Refactoring

## Testing Seam

The official testing doc recommends sharing client configuration and swapping only the engine in tests.

Preferred patterns:

- `ApiClient(engine: HttpClientEngine)`
- `ApiClient(client: HttpClient)`
- `createHttpClient(engine, configOverrides)`

Avoid patterns where repositories or services hard-code `HttpClient()` internally with no injection seam.

## `MockEngine`

Use `MockEngine` when you need fast transport-level tests without live servers.

Look for:

- `ktor-client-mock` in test dependencies
- `MockEngine { request -> ... }`
- assertions against request URL, method, headers, or body
- shared production configuration reused in test clients

If production code already accepts an engine or a client, `MockEngine` can be introduced with minimal refactoring.

## Safe Refactor Order

1. Detect current client owners and plugin duplication.
2. Extract one shared builder or factory without changing request semantics.
3. Move shared plugin setup into that builder.
4. Move platform-only engine setup into platform modules.
5. Introduce `MockEngine`-friendly constructors.
6. Add tests around serialization, auth headers, and error mapping.

## Common Smells

- `HttpClient` is created inside repositories, use cases, or feature services.
- The same plugins are installed in multiple builders with slightly different options.
- Shared code imports Android or Darwin engine packages.
- Tests hit live endpoints because no `MockEngine` seam exists.
- Error mapping logic is duplicated across repositories instead of sitting at the client boundary.

## Conservative Advice

When refactoring mobile networking code:

- preserve DTO and exception behavior first
- centralize client construction second
- tighten validation and auth structure third

Do not mix structural refactors with serializer migrations unless the user explicitly wants both at once.
