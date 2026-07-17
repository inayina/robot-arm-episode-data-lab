"""Read-only registry and Markdown audit for Project Evidence Agent V1."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .core import (
    DEFAULT_REGISTRY,
    CatalogEntry,
    build_catalog,
    classify_path,
    load_registry,
    resolve_repositories,
)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    repository: str
    path: str
    line: int | None
    message: str
    related_paths: tuple[str, ...] = ()
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["related_paths"] = list(self.related_paths)
        return data


LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
EXPLICIT_HISTORICAL_RE = re.compile(r"\b(?:legacy|archive|v1)\b|历史|归档|旧版", re.IGNORECASE)


def _markdown_lines(path: Path) -> Iterable[tuple[int, str, bool]]:
    in_fence = False
    marker = ""
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        fence = re.match(r"^\s*(```+|~~~+)", line)
        nested = False
        if fence:
            current = fence.group(1)[0]
            if not in_fence:
                in_fence, marker = True, current
            elif current == marker and line.strip() in {"```", "~~~"}:
                in_fence = False
            else:
                nested = True
            yield number, line, nested
            continue
        yield number, line, in_fence


def _tracked_markdown(repository_root: Path) -> list[str]:
    try:
        output = subprocess.run(
            ["git", "-C", str(repository_root), "ls-files", "*.md"],
            check=True, capture_output=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted(line for line in output.splitlines() if line)


def _resolve_dependency(repository: str, dependency: str) -> tuple[str, str]:
    if ":" in dependency:
        candidate_repo, candidate_path = dependency.split(":", 1)
        if "/" not in candidate_repo:
            return candidate_repo, candidate_path
    return repository, dependency


def audit_project(registry_path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    registry = load_registry(registry_path)
    repositories, coverage_warnings = resolve_repositories(registry, strict=False)
    repository_map = {item.name: item for item in repositories}
    entries, coverage = build_catalog(registry, strict=False)
    entry_map = {(item.repository.name, item.relative_path): item for item in entries}
    findings: list[Finding] = []

    for warning in coverage_warnings:
        findings.append(Finding("MISSING_REPOSITORY", "error", "registry", "", None, warning,
                                suggestion="Set the configured environment variable or fallback path."))

    # Registry paths and dependencies.
    for item in registry.get("overrides", []):
        repository = repository_map.get(item["repository"])
        if repository is None:
            continue
        path = repository.root / item["path"]
        if not path.exists():
            findings.append(Finding(
                "MISSING_REGISTERED_PATH", "error", repository.name, item["path"], None,
                "Registered override path does not exist.", suggestion="Restore the path or update the registry override.",
            ))
        for dependency in item.get("depends_on", []):
            dep_repo_name, dep_path = _resolve_dependency(repository.name, dependency)
            dep_repo = repository_map.get(dep_repo_name)
            if dep_repo is None or not (dep_repo.root / dep_path).exists():
                findings.append(Finding(
                    "MISSING_REGISTERED_PATH", "error", repository.name, item["path"], None,
                    f"Registered dependency does not exist: {dep_repo_name}:{dep_path}",
                    related_paths=(f"{dep_repo_name}:{dep_path}",),
                    suggestion="Restore the evidence dependency or mark the source needs_reconciliation.",
                ))

    for index, item in enumerate(registry.get("rules", [])):
        repository = repository_map.get(item["repository"])
        if repository is None:
            continue
        for pattern in item["globs"]:
            if not any(path.is_file() for path in repository.root.glob(pattern)):
                severity = "error" if item.get("required_match") else "warning"
                findings.append(Finding(
                    "UNMATCHED_REGISTRY_GLOB", severity, repository.name, pattern, None,
                    f"Registry glob matched no files (rule:{index}).",
                    suggestion="Correct the glob, remove the stale rule, or mark an intentionally optional source.",
                ))

    # All tracked Markdown must classify.
    for repository in repositories:
        for relative in _tracked_markdown(repository.root):
            if classify_path(registry, repository.name, relative) is None:
                findings.append(Finding(
                    "UNREGISTERED_MARKDOWN", "warning", repository.name, relative, None,
                    "Tracked Markdown is not covered by any registry rule or override.",
                    suggestion="Add a narrow registry rule or an exact override.",
                ))

    markdown_entries = [item for item in entries if item.path.suffix.lower() == ".md"]
    for entry in markdown_entries:
        _audit_markdown(entry, registry, findings)
        metadata = entry.metadata
        if metadata.kind in {"canonical", "current_doc", "runbook", "run_artifact"} and metadata.status == "current" and not metadata.last_verified:
            findings.append(Finding(
                "MISSING_LAST_VERIFIED", "warning", entry.repository.name, entry.relative_path, None,
                "Current evidence source has no last_verified date.", suggestion="Add an ISO last_verified date to its registry metadata.",
            ))

    # Multiple current document/canonical authorities for one claim namespace.
    authorities: dict[str, list[CatalogEntry]] = {}
    for entry in entries:
        if entry.metadata.status != "current" or entry.metadata.kind not in {"canonical", "current_doc"}:
            continue
        for claim in entry.metadata.authoritative_for:
            authorities.setdefault(claim, []).append(entry)
    for claim, sources in authorities.items():
        unique = {(source.repository.name, source.relative_path) for source in sources}
        if len(unique) > 1:
            first = sources[0]
            findings.append(Finding(
                "MULTIPLE_AUTHORITIES", "warning", first.repository.name, first.relative_path, None,
                f"Multiple current authorities declare authoritative_for={claim}.",
                related_paths=tuple(f"{repo}:{path}" for repo, path in sorted(unique)),
                suggestion="Choose one authority or document an explicit priority.",
            ))

    _known_claim_conflicts(repository_map, findings)
    findings.sort(key=lambda item: (item.severity != "error", item.repository, item.path, item.line or 0, item.rule_id))
    counts = {severity: sum(item.severity == severity for item in findings) for severity in ("error", "warning", "info")}
    return {
        "schema_version": 1,
        "coverage": coverage,
        "counts": counts,
        "findings": [item.to_dict() for item in findings],
    }


def _audit_markdown(entry: CatalogEntry, registry: dict[str, Any], findings: list[Finding]) -> None:
    h1_lines: list[int] = []
    links: dict[str, list[int]] = {}
    in_fence = False
    marker = ""
    for number, line in enumerate(entry.path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        fence = re.match(r"^\s*(```+|~~~+)(.*)$", line)
        if fence:
            current = fence.group(1)[0]
            remainder = fence.group(2).strip()
            if not in_fence:
                in_fence, marker = True, current
            elif current == marker and not remainder:
                in_fence = False
            else:
                findings.append(Finding(
                    "UNCLOSED_CODE_FENCE", "warning", entry.repository.name, entry.relative_path, number,
                    "Nested or mismatched Markdown code fence.", suggestion="Close the active fence before opening another fence.",
                ))
            continue
        if in_fence:
            continue
        if re.match(r"^#\s+", line):
            h1_lines.append(number)
        for raw_target in LINK_RE.findall(line):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            links.setdefault(target, []).append(number)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if target.startswith("file://"):
                findings.append(Finding(
                    "NONPORTABLE_LOCAL_LINK", "warning", entry.repository.name, entry.relative_path, number,
                    f"Absolute file URI is not portable: {target}",
                    related_paths=(target,), suggestion="Use a repository-relative link or a public repository URL.",
                ))
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (entry.path.parent / path_part).resolve()
            try:
                resolved.relative_to(entry.repository.root)
            except ValueError:
                findings.append(Finding(
                    "NONPORTABLE_LOCAL_LINK", "warning", entry.repository.name, entry.relative_path, number,
                    f"Relative link escapes the repository: {target}",
                    related_paths=(target,), suggestion="Use a link within this repository or an HTTPS URL for another repository.",
                ))
                continue
            if not resolved.exists():
                findings.append(Finding(
                    "BROKEN_LOCAL_LINK", "warning", entry.repository.name, entry.relative_path, number,
                    f"Local Markdown link target does not exist: {target}",
                    related_paths=(target,), suggestion="Correct the relative path or restore the target.",
                ))
                continue
            if resolved.is_file():
                relative = resolved.relative_to(entry.repository.root).as_posix()
                target_metadata = classify_path(registry, entry.repository.name, relative)
                if (entry.metadata.status == "current" and entry.metadata.kind in {"canonical", "current_doc", "runbook"}
                        and target_metadata and target_metadata.status in {"legacy", "archive"}
                        and not EXPLICIT_HISTORICAL_RE.search(line)):
                    findings.append(Finding(
                        "CURRENT_REFERENCES_LEGACY", "warning", entry.repository.name, entry.relative_path, number,
                        f"Current document links to {target_metadata.status} material: {relative}",
                        related_paths=(relative,), suggestion="Keep only an explicit boundary reference or add an allowlist reason.",
                    ))
    if in_fence:
        findings.append(Finding(
            "UNCLOSED_CODE_FENCE", "warning", entry.repository.name, entry.relative_path, None,
            "Markdown code fence is not closed at end of file.", suggestion="Add the matching closing fence.",
        ))
    if len(h1_lines) > 1:
        findings.append(Finding(
            "DUPLICATE_H1", "warning", entry.repository.name, entry.relative_path, h1_lines[1],
            f"Document contains {len(h1_lines)} level-one headings.", suggestion="Use one H1 and demote section headings where appropriate.",
        ))
    for target, lines in links.items():
        repeated_on_same_line = len(lines) != len(set(lines))
        if repeated_on_same_line:
            findings.append(Finding(
                "DOC_INDEX_ERROR", "info", entry.repository.name, entry.relative_path, lines[1],
                f"Document repeats the same target on one line: {target}",
                related_paths=(target,), suggestion="Remove accidental duplicate index entries; retain intentional narrative links.",
            ))


def _known_claim_conflicts(repositories: dict[str, Any], findings: list[Finding]) -> None:
    middle = repositories.get("robot-arm-episode-data-lab")
    if middle is not None:
        canonical = middle.root / "docs/portfolio/CANONICAL_EXPERIMENT.md"
        latest = middle.root / "evidence/downstream/benchmark_summary.json"
        if canonical.exists() and latest.exists():
            text = canonical.read_text(encoding="utf-8", errors="ignore")
            try:
                payload = json.loads(latest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            if "94.399" in text and payload.get("fault_injection") is False and payload.get("health_alarm_latency_ms") is None:
                findings.append(Finding(
                    "KNOWN_CLAIM_CONFLICT", "error", middle.name,
                    "docs/portfolio/CANONICAL_EXPERIMENT.md", 10,
                    "94.399 ms fault claim conflicts with latest archived no-fault artifact whose alarm latency is null.",
                    related_paths=("evidence/downstream/benchmark_summary.json",),
                    suggestion="Keep the claim needs_reconciliation until its original fault benchmark JSON is located.",
                ))

    downstream = repositories.get("ros2-moveit-pybullet-bridge")
    if downstream is None:
        return
    readiness = downstream.root / "docs/REAL_MACHINE_READINESS.md"
    current_status = downstream.root / "docs/CURRENT_STATUS.md"
    if not readiness.exists() or not current_status.exists():
        return
    readiness_text = readiness.read_text(encoding="utf-8", errors="ignore")
    status_text = current_status.read_text(encoding="utf-8", errors="ignore")
    unsupported_hardware = "Real Panda hardware source" in status_text and "Partial Or Future Work" in status_text
    if unsupported_hardware and re.search(r"\|\s*`Pass`\s*\|", readiness_text):
        findings.append(Finding(
            "KNOWN_CLAIM_CONFLICT", "error", downstream.name, "docs/REAL_MACHINE_READINESS.md", None,
            "Hardware readiness row is marked Pass while CURRENT_STATUS lists real Panda hardware as future work.",
            related_paths=("docs/CURRENT_STATUS.md",),
            suggestion="Use Sim Precheck/Planned/Hardware Pending until real-hardware evidence exists.",
        ))


def render_audit_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Project Evidence Audit",
        "",
        f"Coverage complete: `{str(report['coverage']['complete']).lower()}`",
        f"Findings: errors={report['counts']['error']}, warnings={report['counts']['warning']}, info={report['counts']['info']}",
        "",
        "| Severity | Rule | Repository | Path:line | Finding |",
        "|---|---|---|---|---|",
    ]
    for item in report["findings"]:
        location = item["path"] + (f":{item['line']}" if item["line"] else "")
        message = item["message"].replace("|", "\\|")
        lines.append(f"| {item['severity']} | `{item['rule_id']}` | `{item['repository']}` | `{location}` | {message} |")
    return "\n".join(lines) + "\n"
