Checked: 2026-03-15
Sources:
- Official: https://ktor.io/docs/releases.html
- Official: https://ktor.io/docs/client-engines.html
- Official: https://ktor.io/docs/client-dependencies.html
- Official: https://ktor.io/docs/client-timeout.html
- Official: https://ktor.io/docs/client-testing.html
- Maintenance-only cross-check: https://github.com/ktorio/ktor/blob/main/VERSION

# Version Policy

## Validated Range

This skill is validated against:

- Official docs snapshot: `3.4.1`
- Official releases cross-check: `3.3.3` patch release remains within the same mobile-client guidance covered by this skill
- Local maintenance cross-check repo: `3.5.0-SNAPSHOT`
- Runtime recommendation range: `>= 3.3.3, < 3.6.0`

Treat projects outside that range as potentially drifted.

## Lower Bound Rationale

The lower bound starts at `3.3.3`, not all of `3.3.x`.

- The bundled references were authored from the `3.4.1` docs snapshot, then maintenance-checked for low-drift mobile topics against the `3.3.3` release line.
- The topics treated as safe at `3.3.3` are the ones this skill emphasizes most:
  - shared `HttpClient` ownership
  - `androidMain` and `iosMain` engine placement
  - centralized plugin installation
  - `MockEngine`-friendly test seams
- Engine-specific quirks and timeout behavior stay version-sensitive even inside the validated range.

## Runtime Behavior Outside Range

When the target project is outside the validated range:

1. Warn explicitly that the project may use newer or older behavior than the bundled references cover.
2. Narrow advice to conservative architecture guidance:
   - shared client ownership
   - engine placement by source set
   - centralized plugin setup
   - MockEngine test seams
3. Avoid strong claims about engine-specific quirks or newly added plugin behavior unless the evidence is local to the project itself.

## Version-Sensitive Topics

Treat these topics as version-sensitive:

- exact engine feature and timeout support
- new or deprecated engine configuration APIs
- plugin artifact names and platform limitations
- version-catalog and BOM guidance
- logging backends and engine/platform bug fixes called out in releases
- behavioral differences between `3.3.3` and later `3.4.x` or `3.5.x` client fixes

## Low-Drift Topics

These topics are usually safe even when the version is slightly outside range:

- prefer one shared `HttpClient` owner
- keep Android and Darwin specifics out of shared code
- avoid constructing `HttpClient` in repositories and services
- make transport code swappable for `MockEngine` tests
- centralize shared plugin installation

## Maintenance Trigger

Refresh this skill when either condition is true:

- a user provides updated official Ktor doc links that materially change covered guidance
- a Ktor release changes mobile client behavior, plugin setup, or engine caveats covered by the skill

During maintenance, update the validated range here first, then refresh the affected topic references.
