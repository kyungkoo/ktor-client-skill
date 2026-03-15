# ktor-mobile-client-skill

Codex skill for reviewing and refactoring Ktor-based Android and iOS client code in Kotlin Multiplatform projects.

The bundled skill focuses on:

- shared `HttpClient` ownership and DI boundaries
- Android and Darwin engine placement
- centralized plugin setup
- `MockEngine`-friendly testing
- version-aware, evidence-backed project scanning

## Skill Name

Use the skill as:

```text
$ktor-mobile-client
```

UI metadata lives in [ktor-mobile-client/agents/openai.yaml](./ktor-mobile-client/agents/openai.yaml).

## Repository Layout

- [ktor-mobile-client/SKILL.md](./ktor-mobile-client/SKILL.md): runtime instructions for Codex
- [ktor-mobile-client/references/](./ktor-mobile-client/references): self-contained bundled guidance used at runtime
- [ktor-mobile-client/scripts/scan_ktor_mobile_client.py](./ktor-mobile-client/scripts/scan_ktor_mobile_client.py): Kotlin/KMP repository scanner
- [bin/install.js](./bin/install.js): `npx` installer

## Install

Install from this local checkout:

```bash
node ./bin/install.js --force
```

Or use `npx` against the local repo:

```bash
npx --yes . --force
```

After publishing to npm, the intended install path is:

```bash
npx ktor-mobile-client-skill --force
```

By default the installer copies the skill into `$CODEX_HOME/skills` or `~/.codex/skills`.

Useful installer options:

- `--target <dir>`: install into a custom skills directory
- `--force`: replace an existing installed copy
- `--dry-run`: print resolved paths without copying files

## Use In Codex

Prompt Codex with the skill name and a repo path:

```text
Use $ktor-mobile-client to review /path/to/app for Ktor mobile client issues.
```

Example prompts:

- `Use $ktor-mobile-client to refactor this KMP networking layer.`
- `Use $ktor-mobile-client to find wrong Ktor client usage in /path/to/app.`
- `Use $ktor-mobile-client to review Android/iOS engine wiring and MockEngine testing.`

## Run The Scanner Directly

You can also run the scanner without invoking the skill through Codex:

```bash
python3 "$CODEX_HOME/skills/ktor-mobile-client/scripts/scan_ktor_mobile_client.py" /path/to/project
```

Or from this repository:

```bash
python3 ./ktor-mobile-client/scripts/scan_ktor_mobile_client.py /path/to/project --format markdown
```

The scanner reports:

- detected Ktor version
- compatibility against the skill's validated range
- structure, engine, plugin, testing, and refactor findings
- confidence and evidence for each non-trivial finding

## Runtime Model

Normal skill usage is self-contained:

- no web access required
- no local Ktor checkout required
- answers come from bundled references plus scan results

Skill maintenance is external:

- official Ktor docs are reviewed when updating the skill
- official `ktorio/ktor` source and tests are used only for maintenance cross-checks

Current validated version range is documented in [ktor-mobile-client/references/version-policy.md](./ktor-mobile-client/references/version-policy.md).

## Scope

The current skill is aimed at app/client code guidance, not Ktor framework contribution work.

Covered well:

- KMP shared client structure
- Android and iOS engine separation
- baseline plugin setup
- duplication and ownership smells
- `MockEngine` seams and transport tests

Out of scope for v1 unless explicitly requested:

- SSL pinning
- Darwin `challengeHandler`
- WebSockets
- SSE

## Maintenance

When updating the skill:

1. Refresh the bundled references under [ktor-mobile-client/references/](./ktor-mobile-client/references).
2. Re-check version policy in [ktor-mobile-client/references/version-policy.md](./ktor-mobile-client/references/version-policy.md).
3. Validate the skill:

```bash
python3 "$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py" ./ktor-mobile-client
```

4. Re-run the scanner on fixture repos and at least one real Ktor mobile client project.
