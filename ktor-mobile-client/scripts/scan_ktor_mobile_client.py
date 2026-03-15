#!/usr/bin/env python3
"""
Scan a Kotlin/KMP repository for Ktor mobile client architecture signals.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

try:  # pragma: no cover
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


VALIDATED_RANGE_TEXT = ">= 3.3.3, < 3.6.0"
VALIDATED_MIN = (3, 3, 3)
VALIDATED_MAX_EXCLUSIVE = (3, 6, 0)

IGNORE_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".konan",
    ".kotlin",
    "build",
    "dist",
    "node_modules",
    "out",
}

PLATFORM_SPECIFIC_ENGINES = {"android", "darwin", "okhttp"}
BASELINE_PLUGINS = {"ContentNegotiation", "HttpTimeout", "Auth", "Logging", "DefaultRequest"}
MODULE_ID_RE = re.compile(r"module\s+io\.ktor:([A-Za-z0-9.\-]+):([A-Za-z0-9.\-+_]+)")
DEPENDENCY_COORD_RE = re.compile(r"^io\.ktor:([A-Za-z0-9.\-]+)(?::([A-Za-z0-9.\-+_]+))?$")
MANIFEST_KTOR_RE = re.compile(r"io\.ktor(?:\\:|:)([A-Za-z0-9.\-]+)(?:(?:\\:|:)([A-Za-z0-9.\-+_]+))?")
CATALOG_CREATE_RE = re.compile(r'create\("([^"]+)"\)\s*\{\s*from\("([^"]+)"\)', re.DOTALL)


@dataclass
class Finding:
    message: str
    confidence: str
    version_sensitive: bool
    evidence: list[str] = field(default_factory=list)


@dataclass
class VersionInfo:
    value: str | None
    source: str | None
    confidence: str
    compatibility: str
    evidence: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass
class StructureSummary:
    kmp_shared_detected: bool
    confidence: str
    evidence: list[str]
    production_http_client_count: int
    production_http_client_files: list[str]


@dataclass
class ScanResult:
    repo_root: str
    validated_range: str
    detected_version: VersionInfo
    structure: StructureSummary
    findings: dict[str, list[Finding]]


@dataclass
class VersionCandidate:
    version: str
    source: str
    priority: int
    confidence: str
    evidence: list[str]


@dataclass
class DependencyHit:
    artifact: str
    evidence: str


@dataclass
class ClientInstantiation:
    file: str
    line: int
    bucket: str
    argument: str | None
    in_leaf_type: bool


@dataclass
class PluginInstall:
    plugin: str
    file: str
    line: int
    bucket: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan a repo for Ktor mobile client architecture signals.")
    parser.add_argument("repo_root", help="Path to the app repository to scan.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def should_skip(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)


def relpath(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def iter_files(root: Path, suffixes: tuple[str, ...]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        if path.suffix in suffixes:
            yield path


def iter_gradle_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        if path.name in {"settings.gradle", "settings.gradle.kts", "build.gradle", "build.gradle.kts"}:
            yield path
            continue
        lowered = path.as_posix().lower()
        if path.suffix in {".gradle", ".kts"} and any(
            marker in lowered for marker in ("/buildsrc/", "/build-logic/", "/convention", "/conventions/")
        ):
            yield path


def is_test_path(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    if any("test" in part for part in lowered):
        return True
    return path.name.endswith("Test.kt")


def bucket_for_path(path: Path) -> str:
    lowered = [part.lower() for part in path.parts]
    if is_test_path(path):
        return "test"
    if any(part == "commonmain" for part in lowered):
        return "common"
    if any(part == "androidmain" for part in lowered):
        return "android"
    if any(part == "iosmain" for part in lowered):
        return "ios"
    if any(part.startswith("ios") for part in lowered):
        return "ios"
    if "common" in lowered:
        return "common"
    if "android" in lowered:
        return "android"
    if "ios" in lowered:
        return "ios"
    return "unknown"


def parse_version_tuple(version: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def compatibility_for(version: str | None) -> str:
    if version is None:
        return "unknown"
    parsed = parse_version_tuple(version)
    if parsed is None:
        return "unknown"
    if parsed < VALIDATED_MIN:
        return "outside-validated-range-old"
    if parsed >= VALIDATED_MAX_EXCLUSIVE:
        return "outside-validated-range-new"
    return "validated-range"


def line_evidence(path: Path, root: Path, line_no: int, label: str | None = None) -> str:
    base = f"{relpath(path, root)}:{line_no}"
    if label:
        return f"{base} ({label})"
    return base


def discover_catalog_definitions(root: Path) -> dict[str, str]:
    definitions: dict[str, str] = {}
    settings_files = [root / "settings.gradle.kts", root / "settings.gradle"]
    for path in settings_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in CATALOG_CREATE_RE.finditer(text):
            definitions[match.group(1)] = match.group(2)
    return definitions


def discover_catalog_names(root: Path) -> list[str]:
    return sorted(discover_catalog_definitions(root))


def catalog_source_is_published_ktor(source: str) -> bool:
    return source.startswith("io.ktor:ktor-version-catalog:")


def external_catalog_note(catalog_definitions: dict[str, str]) -> str | None:
    external = [name for name, source in catalog_definitions.items() if not catalog_source_is_published_ktor(source)]
    if not external:
        return None
    return (
        "External version catalogs were detected ("
        + ", ".join(sorted(external))
        + "); resolved Ktor version may require build metadata."
    )


def strip_toml_comment(line: str) -> str:
    in_string = False
    result: list[str] = []
    for char in line:
        if char == '"':
            in_string = not in_string
        if char == "#" and not in_string:
            break
        result.append(char)
    return "".join(result).strip()


def parse_inline_table(raw: str) -> dict[str, object]:
    content = raw.strip()
    if content.startswith("{") and content.endswith("}"):
        content = content[1:-1]
    entries: dict[str, object] = {}
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    for char in content:
        if char == '"':
            in_string = not in_string
        elif char == "{" and not in_string:
            depth += 1
        elif char == "}" and not in_string:
            depth -= 1
        elif char == "," and not in_string and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("{") and value.endswith("}"):
            entries[key] = parse_inline_table(value)
        else:
            entries[key] = value.strip('"').strip("'")
    return entries


def load_version_catalog(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)

    data: dict[str, object] = {"versions": {}, "libraries": {}}
    section: str | None = None
    for raw_line in text.splitlines():
        line = strip_toml_comment(raw_line)
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if section not in data:
                data[section] = {}
            continue
        if "=" not in line or section is None:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        target = data.setdefault(section, {})
        if not isinstance(target, dict):
            continue
        if value.startswith("{") and value.endswith("}"):
            target[key] = parse_inline_table(value)
        else:
            target[key] = value.strip('"').strip("'")
    return data


def iter_build_metadata_json_files(root: Path) -> Iterable[Path]:
    for dir_name in ("kotlinTransformedMetadataLibraries", "kotlinProjectStructureMetadata"):
        for directory in root.rglob(dir_name):
            if not directory.is_dir():
                continue
            if "build" not in directory.parts:
                continue
            for path in directory.rglob("*.json"):
                if path.is_file():
                    yield path


def iter_build_metadata_manifest_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("manifest"):
        if not path.is_file():
            continue
        if "build" not in path.parts:
            continue
        yield path


def iter_module_entries_from_json_data(data: object) -> Iterable[tuple[str, str | None]]:
    if isinstance(data, dict):
        module_id = data.get("moduleId")
        if isinstance(module_id, str):
            match = MODULE_ID_RE.search(module_id)
            if match:
                yield match.group(1), match.group(2)
        module_dependency = data.get("moduleDependency")
        if isinstance(module_dependency, list):
            for item in module_dependency:
                if isinstance(item, str):
                    match = DEPENDENCY_COORD_RE.match(item)
                    if match:
                        yield match.group(1), match.group(2)
        for value in data.values():
            yield from iter_module_entries_from_json_data(value)
    elif isinstance(data, list):
        for item in data:
            yield from iter_module_entries_from_json_data(item)


def extract_ktor_entries_from_json(path: Path) -> list[tuple[str, str | None]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(iter_module_entries_from_json_data(data))


def parse_manifest_entries(path: Path) -> list[tuple[str, str | None]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    return [(match.group(1), match.group(2)) for match in MANIFEST_KTOR_RE.finditer(text)]


def dedupe_dependency_hits(hits: list[DependencyHit]) -> list[DependencyHit]:
    seen: set[tuple[str, str]] = set()
    deduped: list[DependencyHit] = []
    for hit in hits:
        key = (hit.artifact, hit.evidence)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


def pick_version_info(candidates: list[VersionCandidate], notes: list[str], no_candidates_message: str) -> VersionInfo:
    if not candidates:
        return VersionInfo(
            value=None,
            source=None,
            confidence="low",
            compatibility="unknown",
            evidence=[],
            notes=notes + [no_candidates_message],
        )

    grouped: dict[int, dict[str, list[VersionCandidate]]] = defaultdict(lambda: defaultdict(list))
    for candidate in candidates:
        grouped[candidate.priority][candidate.version].append(candidate)

    best_priority = min(grouped)
    best_versions = grouped[best_priority]
    if len(best_versions) > 1:
        combined_evidence: list[str] = []
        for version_candidates in best_versions.values():
            combined_evidence.extend(version_candidates[0].evidence)
        return VersionInfo(
            value=None,
            source=None,
            confidence="low",
            compatibility="unknown",
            evidence=sorted(set(combined_evidence))[:12],
            notes=notes
            + [
                "Multiple conflicting Ktor versions were detected at the highest-priority source: "
                + ", ".join(sorted(best_versions))
            ],
        )

    selected_version, version_candidates = next(iter(best_versions.items()))
    evidence: list[str] = []
    for candidate in version_candidates:
        evidence.extend(candidate.evidence)
    return VersionInfo(
        value=selected_version,
        source=version_candidates[0].source,
        confidence=version_candidates[0].confidence,
        compatibility=compatibility_for(selected_version),
        evidence=sorted(set(evidence))[:12],
        notes=notes,
    )


def collect_build_metadata_version_candidates(root: Path) -> list[VersionCandidate]:
    candidates: list[VersionCandidate] = []
    for path in iter_build_metadata_json_files(root):
        for artifact, version in extract_ktor_entries_from_json(path):
            if version and parse_version_tuple(version):
                candidates.append(
                    VersionCandidate(
                        version=version,
                        source=relpath(path, root),
                        priority=0,
                        confidence="high",
                        evidence=[line_evidence(path, root, 1, f"build metadata {artifact}")],
                    )
                )
    for path in iter_build_metadata_manifest_files(root):
        for artifact, version in parse_manifest_entries(path):
            if version and parse_version_tuple(version):
                candidates.append(
                    VersionCandidate(
                        version=version,
                        source=relpath(path, root),
                        priority=0,
                        confidence="high",
                        evidence=[line_evidence(path, root, 1, f"manifest {artifact}")],
                    )
                )
    return candidates


def collect_gradle_version_candidates(root: Path, gradle_files: list[Path]) -> tuple[list[VersionCandidate], list[str]]:
    candidates: list[VersionCandidate] = []
    notes: list[str] = []

    version_catalogs = [root / "gradle" / "libs.versions.toml"]
    version_catalogs += [
        path
        for path in root.rglob("libs.versions.toml")
        if path != root / "gradle" / "libs.versions.toml" and not should_skip(path)
    ]
    for path in version_catalogs:
        if not path.exists():
            continue
        try:
            data = load_version_catalog(path)
        except Exception as exc:  # pragma: no cover
            notes.append(f"Failed to parse {relpath(path, root)}: {exc}")
            continue
        versions = data.get("versions", {}) or {}
        libraries = data.get("libraries", {}) or {}
        seen_versions = set()
        for key, value in versions.items():
            if "ktor" in key.lower() and isinstance(value, str) and parse_version_tuple(value):
                seen_versions.add(value)
                candidates.append(
                    VersionCandidate(
                        version=value,
                        source=relpath(path, root),
                        priority=1,
                        confidence="high",
                        evidence=[line_evidence(path, root, 1, f"versions.{key}")],
                    )
                )
        for alias, spec in libraries.items():
            if not isinstance(spec, dict):
                continue
            module = spec.get("module")
            version = spec.get("version")
            version_ref = spec.get("version.ref")
            nested_version = spec.get("version")
            if isinstance(nested_version, dict):
                version_ref = nested_version.get("ref")
                version = nested_version.get("require")
            if isinstance(module, str) and module.startswith("io.ktor:"):
                resolved = None
                if isinstance(version, str) and parse_version_tuple(version):
                    resolved = version
                elif isinstance(version_ref, str):
                    referenced = versions.get(version_ref)
                    if isinstance(referenced, str) and parse_version_tuple(referenced):
                        resolved = referenced
                if resolved:
                    seen_versions.add(resolved)
                    candidates.append(
                        VersionCandidate(
                            version=resolved,
                            source=relpath(path, root),
                            priority=1,
                            confidence="high",
                            evidence=[line_evidence(path, root, 1, f"libraries.{alias}")],
                        )
                    )
        if len(seen_versions) > 1:
            notes.append(
                f"Multiple Ktor versions were declared in {relpath(path, root)}: {', '.join(sorted(seen_versions))}"
            )

    property_values: dict[str, str] = {}

    def collect_properties(path: Path, priority: int, label: str) -> None:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*([^\s#]+)", stripped)
            if not match:
                continue
            key, value = match.groups()
            property_values[key] = value.strip('"').strip("'")
            if "ktor" in key.lower() and parse_version_tuple(property_values[key]):
                candidates.append(
                    VersionCandidate(
                        version=property_values[key],
                        source=relpath(path, root),
                        priority=priority,
                        confidence="medium",
                        evidence=[line_evidence(path, root, line_no, label)],
                    )
                )

    for path in [root / "gradle.properties"]:
        if path.exists():
            collect_properties(path, 3, "gradle.properties")

    gradle_direct_files: list[Path] = []
    gradle_convention_files: list[Path] = []
    for path in gradle_files:
        lowered = path.as_posix().lower()
        if any(segment in lowered for segment in ("/buildsrc/", "/build-logic/", "/convention", "/conventions/")):
            gradle_convention_files.append(path)
        else:
            gradle_direct_files.append(path)

    version_assign_re = re.compile(r"\b(?:val|var)?\s*([A-Za-z0-9_.-]*ktor[A-Za-z0-9_.-]*)\s*=\s*[\"']([^\"']+)[\"']")
    direct_dep_re = re.compile(r'io\.ktor:[A-Za-z0-9.\-]+:([A-Za-z0-9.\-+_]+)')
    property_ref_re = re.compile(r'\$\{?([A-Za-z0-9_.-]*ktor[A-Za-z0-9_.-]*)\}?')

    def collect_gradle_versions(paths: list[Path], priority: int, confidence: str) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), 1):
                for match in version_assign_re.finditer(line):
                    property_values[match.group(1)] = match.group(2)
                    if parse_version_tuple(match.group(2)):
                        candidates.append(
                            VersionCandidate(
                                version=match.group(2),
                                source=relpath(path, root),
                                priority=priority,
                                confidence=confidence,
                                evidence=[line_evidence(path, root, line_no, "version assignment")],
                            )
                        )
                for match in direct_dep_re.finditer(line):
                    version = match.group(1)
                    if parse_version_tuple(version):
                        candidates.append(
                            VersionCandidate(
                                version=version,
                                source=relpath(path, root),
                                priority=priority,
                                confidence=confidence,
                                evidence=[line_evidence(path, root, line_no, "direct dependency")],
                            )
                        )
                for catalog_name, source in discover_catalog_definitions(root).items():
                    if catalog_source_is_published_ktor(source):
                        version = source.rsplit(":", 1)[-1]
                        if re.search(rf'\b{re.escape(catalog_name)}\.', line) and parse_version_tuple(version):
                            candidates.append(
                                VersionCandidate(
                                    version=version,
                                    source=relpath(path, root),
                                    priority=priority,
                                    confidence=confidence,
                                    evidence=[
                                        line_evidence(
                                            path,
                                            root,
                                            line_no,
                                            f"published version catalog {catalog_name}",
                                        )
                                    ],
                                )
                            )
                if "io.ktor:" in line:
                    for prop in property_ref_re.findall(line):
                        value = property_values.get(prop)
                        if value and parse_version_tuple(value):
                            candidates.append(
                                VersionCandidate(
                                    version=value,
                                    source=relpath(path, root),
                                    priority=priority,
                                    confidence=confidence,
                                    evidence=[line_evidence(path, root, line_no, f"property ref {prop}")],
                                )
                            )
            if path.name == "gradle.properties":
                collect_properties(path, priority, "gradle.properties")

    collect_gradle_versions(gradle_direct_files, 2, "medium")
    collect_gradle_versions(gradle_convention_files, 4, "low")
    return candidates, notes


def detect_ktor_version(root: Path, gradle_files: list[Path]) -> VersionInfo:
    catalog_definitions = discover_catalog_definitions(root)
    metadata_candidates = collect_build_metadata_version_candidates(root)
    source_candidates, source_notes = collect_gradle_version_candidates(root, gradle_files)
    notes = list(source_notes)

    if metadata_candidates:
        metadata_versions = {candidate.version for candidate in metadata_candidates}
        source_versions = {candidate.version for candidate in source_candidates}
        if source_versions and source_versions != metadata_versions:
            notes.append(
                "Build metadata and Gradle source candidates disagree; preferring build metadata versions: "
                + ", ".join(sorted(metadata_versions))
            )
        return pick_version_info(
            metadata_candidates,
            notes,
            "No Ktor version could be detected from build metadata.",
        )

    external_note = external_catalog_note(catalog_definitions)
    if external_note:
        notes.append(external_note)

    return pick_version_info(
        source_candidates,
        notes,
        "No Ktor version could be detected from build metadata, version catalogs, Gradle files, or properties.",
    )


def collect_build_metadata_dependencies(root: Path) -> list[DependencyHit]:
    hits: list[DependencyHit] = []
    for path in iter_build_metadata_json_files(root):
        for artifact, _version in extract_ktor_entries_from_json(path):
            hits.append(
                DependencyHit(
                    artifact=artifact,
                    evidence=line_evidence(path, root, 1, f"build metadata {artifact}"),
                )
            )
    for path in iter_build_metadata_manifest_files(root):
        for artifact, _version in parse_manifest_entries(path):
            hits.append(
                DependencyHit(
                    artifact=artifact,
                    evidence=line_evidence(path, root, 1, f"manifest {artifact}"),
                )
            )
    return dedupe_dependency_hits(hits)


def camel_or_dot_to_kebab(value: str) -> str:
    value = value.replace(".", "-")
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    return value.lower()


def alias_suffix_to_artifact(suffix: str) -> str:
    cleaned = suffix.split()[0].rstrip("),")
    return "ktor-" + camel_or_dot_to_kebab(cleaned)


def collect_gradle_dependencies(root: Path, gradle_files: list[Path]) -> list[DependencyHit]:
    hits: list[DependencyHit] = []
    direct_dep_re = re.compile(r'io\.ktor:([A-Za-z0-9.\-]+)')
    catalog_definitions = discover_catalog_definitions(root)
    catalog_names = sorted(catalog_definitions)

    alias_to_artifact: dict[str, str] = {}
    catalog_path = root / "gradle" / "libs.versions.toml"
    if catalog_path.exists():
        data = load_version_catalog(catalog_path)
        libraries = data.get("libraries", {}) or {}
        for alias, spec in libraries.items():
            if not isinstance(spec, dict):
                continue
            module = spec.get("module")
            if isinstance(module, str) and module.startswith("io.ktor:"):
                alias_to_artifact["libs." + alias.replace("-", ".")] = module.split(":", 1)[1]

    for path in gradle_files:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            for alias, artifact in alias_to_artifact.items():
                if alias in line:
                    hits.append(DependencyHit(artifact=artifact, evidence=line_evidence(path, root, line_no, alias)))
            for match in direct_dep_re.finditer(line):
                hits.append(
                    DependencyHit(
                        artifact=match.group(1),
                        evidence=line_evidence(path, root, line_no, match.group(1)),
                    )
                )
            for catalog_name in catalog_names:
                for match in re.finditer(rf"\b{re.escape(catalog_name)}\.ktor\.([A-Za-z0-9_.]+)", line):
                    suffix = match.group(1)
                    artifact = alias_suffix_to_artifact(suffix)
                    hits.append(
                        DependencyHit(
                            artifact=artifact,
                            evidence=line_evidence(path, root, line_no, f"{catalog_name}.ktor.{suffix}"),
                        )
                    )

    return dedupe_dependency_hits(hits)


def collect_dependencies(root: Path, gradle_files: list[Path]) -> list[DependencyHit]:
    return dedupe_dependency_hits(collect_build_metadata_dependencies(root) + collect_gradle_dependencies(root, gradle_files))


def collect_kotlin_signals(
    root: Path,
) -> tuple[list[ClientInstantiation], list[PluginInstall], dict[str, list[str]], list[str], list[str]]:
    clients: list[ClientInstantiation] = []
    installs: list[PluginInstall] = []
    imports_by_file: dict[str, list[str]] = {}
    body_usage: list[str] = []
    mock_test_signals: list[str] = []

    install_re = re.compile(r"install\(\s*([A-Za-z0-9_.]+)")
    body_re = re.compile(r"\.body(?:<[^>]+>)?\s*\(|setBody\s*\(")
    leaf_type_re = re.compile(r"\b(class|object)\s+[A-Za-z0-9_]*(Repository|Service|DataSource|Api)\b")

    for path in iter_files(root, (".kt",)):
        text = path.read_text(encoding="utf-8")
        file_key = relpath(path, root)
        imports_by_file[file_key] = []
        bucket = bucket_for_path(path)
        in_leaf_type = bool(leaf_type_re.search(text))
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("import "):
                imported = stripped.removeprefix("import ").strip()
                imports_by_file[file_key].append(imported)
                if bucket == "test" and imported.endswith(".MockEngine"):
                    mock_test_signals.append(f"{file_key}:{line_no} (MockEngine import)")
            if "HttpClient" in line and not stripped.startswith("import "):
                for match in re.finditer(r"\bHttpClient\b", line):
                    tail = line[match.end():].lstrip()
                    if not tail or tail[0] not in "({":
                        continue
                    argument = None
                    if tail.startswith("("):
                        closing = tail.find(")")
                        argument = tail[1:closing].strip() if closing != -1 else tail[1:].strip()
                    clients.append(
                        ClientInstantiation(
                            file=file_key,
                            line=line_no,
                            bucket=bucket,
                            argument=argument,
                            in_leaf_type=in_leaf_type,
                        )
                    )
                    break
            for match in install_re.finditer(line):
                plugin = match.group(1).split(".")[-1]
                installs.append(PluginInstall(plugin=plugin, file=file_key, line=line_no, bucket=bucket))
            if body_re.search(line):
                body_usage.append(f"{file_key}:{line_no}")
            if bucket == "test":
                if "MockEngine" in line and not stripped.startswith("import "):
                    mock_test_signals.append(f"{file_key}:{line_no} (MockEngine usage)")
                if ".engine(" in line:
                    mock_test_signals.append(f"{file_key}:{line_no} (engine injection)")

    return clients, installs, imports_by_file, body_usage, sorted(set(mock_test_signals))


def detect_structure(root: Path, gradle_files: list[Path], clients: list[ClientInstantiation]) -> StructureSummary:
    evidence: list[str] = []
    has_common = False
    has_android = False
    has_ios = False

    source_dirs = [
        root / "src" / "commonMain",
        root / "src" / "androidMain",
        root / "src" / "iosMain",
    ]
    if source_dirs[0].exists():
        has_common = True
        evidence.append("src/commonMain")
    if source_dirs[1].exists():
        has_android = True
        evidence.append("src/androidMain")
    if source_dirs[2].exists():
        has_ios = True
        evidence.append("src/iosMain")

    for path in gradle_files:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if "commonMain" in line:
                has_common = True
                evidence.append(line_evidence(path, root, line_no, "commonMain"))
            if "androidMain" in line or "androidTarget(" in line or "android()" in line:
                has_android = True
                evidence.append(line_evidence(path, root, line_no, "android target"))
            if any(token in line for token in ("iosMain", "iosX64", "iosArm64", "iosSimulatorArm64", "ios(")):
                has_ios = True
                evidence.append(line_evidence(path, root, line_no, "ios target"))

    production_clients = [client for client in clients if client.bucket != "test"]
    kmp = has_common and has_android and has_ios
    confidence = "high" if kmp else "medium" if has_common and (has_android or has_ios) else "low"
    return StructureSummary(
        kmp_shared_detected=kmp,
        confidence=confidence,
        evidence=sorted(set(evidence)),
        production_http_client_count=len(production_clients),
        production_http_client_files=sorted({client.file for client in production_clients}),
    )


def add_finding(target: dict[str, list[Finding]], group: str, finding: Finding) -> None:
    target[group].append(finding)


def summarize_dependency_artifacts(dependencies: list[DependencyHit]) -> set[str]:
    return {hit.artifact for hit in dependencies}


def build_findings(
    root: Path,
    version_info: VersionInfo,
    structure: StructureSummary,
    dependencies: list[DependencyHit],
    clients: list[ClientInstantiation],
    installs: list[PluginInstall],
    imports_by_file: dict[str, list[str]],
    body_usage: list[str],
    mock_test_signals: list[str],
) -> dict[str, list[Finding]]:
    findings: dict[str, list[Finding]] = {
        "Structure": [],
        "Engines": [],
        "Plugins": [],
        "Testing": [],
        "Refactor Candidates": [],
    }

    artifacts = summarize_dependency_artifacts(dependencies)
    production_clients = [client for client in clients if client.bucket != "test"]

    if version_info.value is None:
        add_finding(
            findings,
            "Structure",
            Finding(
                message="Ktor version could not be determined from the repository. Architecture advice should stay conservative until the version is known.",
                confidence=version_info.confidence,
                version_sensitive=True,
                evidence=version_info.evidence,
            ),
        )
    elif version_info.compatibility != "validated-range":
        add_finding(
            findings,
            "Structure",
            Finding(
                message=(
                    f"Detected Ktor version {version_info.value}, which is outside the skill's validated range "
                    f"({VALIDATED_RANGE_TEXT})."
                ),
                confidence=version_info.confidence,
                version_sensitive=True,
                evidence=version_info.evidence,
            ),
        )

    if structure.kmp_shared_detected and structure.production_http_client_count == 0:
        add_finding(
            findings,
            "Structure",
            Finding(
                message="KMP shared source sets were detected, but no production HttpClient construction was found. Verify whether the client is created through DI or a factory outside scanned Kotlin sources.",
                confidence="medium",
                version_sensitive=False,
                evidence=structure.evidence[:6],
            ),
        )

    if structure.production_http_client_count >= 3:
        evidence = [f"{client.file}:{client.line}" for client in production_clients[:8]]
        add_finding(
            findings,
            "Structure",
            Finding(
                message="Multiple production HttpClient builders were detected. Verify whether the app should consolidate them into one shared owner per backend or trust boundary.",
                confidence="high" if structure.production_http_client_count >= 4 else "medium",
                version_sensitive=False,
                evidence=evidence,
            ),
        )

    common_leaks: list[str] = []
    for file_key, imports in imports_by_file.items():
        path_bucket = bucket_for_path(Path(file_key))
        if path_bucket != "common":
            continue
        for imp in imports:
            if any(f"io.ktor.client.engine.{engine}." in imp for engine in PLATFORM_SPECIFIC_ENGINES):
                common_leaks.append(f"{file_key} ({imp})")
    for client in production_clients:
        if client.bucket == "common" and client.argument:
            lowered = client.argument.lower()
            if any(engine in lowered for engine in PLATFORM_SPECIFIC_ENGINES):
                common_leaks.append(f"{client.file}:{client.line} ({client.argument})")
    if common_leaks:
        add_finding(
            findings,
            "Structure",
            Finding(
                message="Platform-specific engine usage leaked into shared/common code. Keep Android and Darwin engine wiring out of commonMain.",
                confidence="high",
                version_sensitive=False,
                evidence=sorted(set(common_leaks))[:8],
            ),
        )

    has_android_targets = any("android" in evidence.lower() for evidence in structure.evidence)
    has_ios_targets = any("ios" in evidence.lower() for evidence in structure.evidence)
    android_signals = {
        artifact
        for artifact in artifacts
        if artifact in {"ktor-client-android", "ktor-client-okhttp"} or artifact.endswith("-android") or artifact.endswith("-okhttp")
    }
    ios_signals = {
        artifact
        for artifact in artifacts
        if artifact == "ktor-client-darwin" or artifact.endswith("-darwin")
    }

    if has_android_targets and not android_signals:
        add_finding(
            findings,
            "Engines",
            Finding(
                message="Android targets were detected, but no Android-capable Ktor engine dependency signal was found.",
                confidence="medium",
                version_sensitive=True,
                evidence=structure.evidence[:6],
            ),
        )

    if has_ios_targets and not ios_signals:
        add_finding(
            findings,
            "Engines",
            Finding(
                message="iOS targets were detected, but no Darwin engine dependency signal was found.",
                confidence="medium",
                version_sensitive=True,
                evidence=structure.evidence[:6],
            ),
        )

    if version_info.value and parse_version_tuple(version_info.value):
        parsed = parse_version_tuple(version_info.value)
        if parsed and parsed < (3, 3, 2):
            add_finding(
                findings,
                "Engines",
                Finding(
                    message="Detected an older Ktor version. Re-check engine caveats before assuming current Android or Darwin behavior.",
                    confidence="medium",
                    version_sensitive=True,
                    evidence=version_info.evidence,
                ),
            )

    production_installs = [install for install in installs if install.bucket != "test"]
    installs_by_file: dict[str, set[str]] = defaultdict(set)
    for install in production_installs:
        installs_by_file[install.file].add(install.plugin)
    duplicate_plugin_files = [
        file
        for file, plugins in installs_by_file.items()
        if len(plugins & BASELINE_PLUGINS) >= 2
    ]
    duplicate_plugin_counter = Counter()
    for install in production_installs:
        if install.plugin in BASELINE_PLUGINS:
            duplicate_plugin_counter[install.plugin] += 1
    repeated_plugins = [plugin for plugin, count in duplicate_plugin_counter.items() if count >= 2]
    if len(duplicate_plugin_files) >= 2 and repeated_plugins:
        evidence = []
        for install in production_installs:
            if install.plugin in repeated_plugins:
                evidence.append(f"{install.file}:{install.line} ({install.plugin})")
        add_finding(
            findings,
            "Plugins",
            Finding(
                message=(
                    "Baseline plugins are installed across multiple production files. "
                    "Verify whether the shared client configuration should be centralized."
                ),
                confidence="medium",
                version_sensitive=False,
                evidence=sorted(set(evidence))[:10],
            ),
        )

    has_content_negotiation = any(install.plugin == "ContentNegotiation" for install in production_installs)
    if body_usage and not has_content_negotiation:
        add_finding(
            findings,
            "Plugins",
            Finding(
                message="Typed body usage was detected, but no ContentNegotiation installation was found in production sources.",
                confidence="medium",
                version_sensitive=True,
                evidence=body_usage[:8],
            ),
        )

    mock_dependency = any(hit.artifact == "ktor-client-mock" for hit in dependencies)
    has_mock_test_signals = bool(mock_test_signals)
    if not mock_dependency and not has_mock_test_signals and production_clients:
        add_finding(
            findings,
            "Testing",
            Finding(
                message="No ktor-client-mock dependency signal was found. MockEngine-based transport tests may be missing.",
                confidence="medium",
                version_sensitive=True,
                evidence=[hit.evidence for hit in dependencies[:6]],
            ),
        )
    if mock_dependency and not has_mock_test_signals:
        mock_install_evidence = [hit.evidence for hit in dependencies if hit.artifact == "ktor-client-mock"][:6]
        add_finding(
            findings,
            "Testing",
            Finding(
                message="A MockEngine dependency signal was found, but no MockEngine usage was detected in test sources.",
                confidence="medium",
                version_sensitive=False,
                evidence=mock_install_evidence,
            ),
        )
    if not mock_dependency and not has_mock_test_signals and production_clients:
        add_finding(
            findings,
            "Testing",
            Finding(
                message="No MockEngine test seam was detected. Prefer constructors that accept HttpClient or HttpClientEngine for fast mobile client tests.",
                confidence="medium",
                version_sensitive=False,
                evidence=[f"{client.file}:{client.line}" for client in production_clients[:6]],
            ),
        )

    leaf_instantiations = [client for client in production_clients if client.in_leaf_type]
    if leaf_instantiations:
        add_finding(
            findings,
            "Refactor Candidates",
            Finding(
                message="HttpClient is instantiated inside repository/service-style classes. Prefer injecting a shared client or wrapper instead.",
                confidence="medium",
                version_sensitive=False,
                evidence=[f"{client.file}:{client.line}" for client in leaf_instantiations[:8]],
            ),
        )

    if structure.production_http_client_count >= 2:
        add_finding(
            findings,
            "Refactor Candidates",
            Finding(
                message="Extract one shared mobile client builder, then move repeated plugin setup and default request policy into it before changing API wrappers.",
                confidence="medium",
                version_sensitive=False,
                evidence=[f"{client.file}:{client.line}" for client in production_clients[:8]],
            ),
        )

    return findings


def render_markdown(result: ScanResult) -> str:
    lines = [
        "# Ktor Mobile Client Scan",
        "",
        f"Repo: `{result.repo_root}`",
        f"Validated range: `{result.validated_range}`",
        "",
        "## Version",
        "",
        f"- Detected version: `{result.detected_version.value or 'unknown'}`",
        f"- Compatibility: `{result.detected_version.compatibility}`",
        f"- Confidence: `{result.detected_version.confidence}`",
    ]
    if result.detected_version.source:
        lines.append(f"- Source: `{result.detected_version.source}`")
    if result.detected_version.evidence:
        lines.append("- Evidence:")
        for item in result.detected_version.evidence:
            lines.append(f"  - `{item}`")
    if result.detected_version.notes:
        lines.append("- Notes:")
        for note in result.detected_version.notes:
            lines.append(f"  - {note}")

    lines.extend(
        [
            "",
            "## Structure Summary",
            "",
            f"- KMP shared detected: `{str(result.structure.kmp_shared_detected).lower()}`",
            f"- Confidence: `{result.structure.confidence}`",
            f"- Production HttpClient count: `{result.structure.production_http_client_count}`",
        ]
    )
    if result.structure.production_http_client_files:
        lines.append("- Production HttpClient files:")
        for path in result.structure.production_http_client_files:
            lines.append(f"  - `{path}`")
    if result.structure.evidence:
        lines.append("- Structure evidence:")
        for item in result.structure.evidence:
            lines.append(f"  - `{item}`")

    for group, items in result.findings.items():
        lines.extend(["", f"## {group}", ""])
        if not items:
            lines.append("- No high-signal findings.")
            continue
        for finding in items:
            lines.append(
                f"- {finding.message} "
                f"(confidence: `{finding.confidence}`, version-sensitive: `{str(finding.version_sensitive).lower()}`)"
            )
            if finding.evidence:
                lines.append("  - Evidence:")
                for item in finding.evidence:
                    lines.append(f"    - `{item}`")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Repository path not found or not a directory: {root}", file=sys.stderr)
        return 1

    gradle_files = sorted(iter_gradle_files(root))
    version_info = detect_ktor_version(root, gradle_files)
    dependencies = collect_dependencies(root, gradle_files)
    clients, installs, imports_by_file, body_usage, mock_test_signals = collect_kotlin_signals(root)
    structure = detect_structure(root, gradle_files, clients)
    findings = build_findings(
        root=root,
        version_info=version_info,
        structure=structure,
        dependencies=dependencies,
        clients=clients,
        installs=installs,
        imports_by_file=imports_by_file,
        body_usage=body_usage,
        mock_test_signals=mock_test_signals,
    )

    result = ScanResult(
        repo_root=root.as_posix(),
        validated_range=VALIDATED_RANGE_TEXT,
        detected_version=version_info,
        structure=structure,
        findings=findings,
    )

    if args.format == "json":
        print(json.dumps(asdict(result), indent=2, ensure_ascii=True))
    else:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
