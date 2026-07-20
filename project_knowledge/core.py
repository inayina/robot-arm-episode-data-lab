"""Registry-backed catalog and deterministic project evidence retrieval."""

from __future__ import annotations

import ast
import fnmatch
import json
import math
import os
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "configs" / "knowledge_registry.yaml"
KINDS = {
    "test", "run_artifact", "code", "config", "canonical", "current_doc",
    "runbook", "portfolio", "reference", "spec", "legacy", "archive",
}
STATUSES = {
    "current", "draft", "derivative", "needs_reconciliation", "historical",
    "legacy", "archive",
}
QUERY_MODES = {"auto", "fact", "debug", "runbook", "learning", "portfolio", "legacy"}


@dataclass(frozen=True)
class Repository:
    name: str
    role: str
    root: Path
    required: bool = True


@dataclass(frozen=True)
class EvidenceMetadata:
    kind: str
    status: str
    enabled_modes: tuple[str, ...]
    evidence_priority: int
    authoritative_for: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    last_verified: str | None = None
    rule_id: str = ""

    @property
    def authoritative(self) -> bool:
        return bool(self.authoritative_for) and self.kind not in {
            "portfolio", "reference", "spec", "legacy", "archive"
        } and self.status == "current"


@dataclass(frozen=True)
class CatalogEntry:
    repository: Repository
    path: Path
    relative_path: str
    metadata: EvidenceMetadata
    tracked: bool | None = None


@dataclass(frozen=True)
class EvidenceChunk:
    entry: CatalogEntry
    symbol: str
    content: str
    start_line: int
    end_line: int

    @property
    def repository(self) -> str:
        return self.entry.repository.name

    @property
    def relative_path(self) -> str:
        return self.entry.relative_path

    @property
    def filepath(self) -> Path:
        return self.entry.path

    def evidence_id(self) -> str:
        return f"{self.repository}:{self.relative_path}:L{self.start_line}-L{self.end_line}"


@dataclass(frozen=True)
class RankedEvidence:
    score: float
    chunk: EvidenceChunk
    bm25: float
    exact_bonus: float

    def to_dict(self) -> dict[str, Any]:
        metadata = self.chunk.entry.metadata
        return {
            "evidence_id": self.chunk.evidence_id(),
            "repository": self.chunk.repository,
            "path": self.chunk.relative_path,
            "line_start": self.chunk.start_line,
            "line_end": self.chunk.end_line,
            "symbol": self.chunk.symbol,
            "kind": metadata.kind,
            "status": metadata.status,
            "score": round(self.score, 6),
            "bm25": round(self.bm25, 6),
            "evidence_priority": metadata.evidence_priority,
            "authoritative": metadata.authoritative,
            "authoritative_for": list(metadata.authoritative_for),
            "components": list(metadata.components),
            "tags": list(metadata.tags),
            "last_verified": metadata.last_verified,
            "tracked": self.chunk.entry.tracked,
            "snippet": re.sub(r"\s+", " ", self.chunk.content).strip()[:500],
        }


@dataclass
class QueryResult:
    query: str
    requested_mode: str
    mode: str
    coverage: dict[str, Any]
    evidence: list[RankedEvidence]
    conclusion: str
    claims: list[dict[str, Any]] = field(default_factory=list)
    llm_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "query": self.query,
            "requested_mode": self.requested_mode,
            "mode": self.mode,
            "coverage": self.coverage,
            "conclusion": self.conclusion,
            "claims": self.claims,
            "evidence": [item.to_dict() for item in self.evidence],
            "llm_summary": self.llm_summary,
        }


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Load and strictly validate the V1 registry."""
    path = path.resolve()
    with path.open(encoding="utf-8") as stream:
        registry = yaml.safe_load(stream) or {}
    allowed_top = {"schema_version", "repositories", "exclude_dirs", "max_file_size_bytes", "rules", "overrides"}
    unknown_top = set(registry) - allowed_top
    if unknown_top:
        raise ValueError(f"unknown registry fields: {sorted(unknown_top)}")
    if registry.get("schema_version") != 1:
        raise ValueError("knowledge registry requires schema_version: 1")
    repositories = registry.get("repositories")
    rules = registry.get("rules")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("knowledge registry requires non-empty repositories")
    if not isinstance(rules, list) or not rules:
        raise ValueError("knowledge registry requires non-empty rules")
    names: set[str] = set()
    for item in repositories:
        if not isinstance(item, dict) or not item.get("name") or not item.get("path"):
            raise ValueError("each repository requires name and path")
        if item["name"] in names:
            raise ValueError(f"duplicate repository: {item['name']}")
        unknown = set(item) - {"name", "role", "path", "path_env", "fallback_paths", "required"}
        if unknown:
            raise ValueError(f"unknown repository fields for {item['name']}: {sorted(unknown)}")
        names.add(item["name"])
    override_keys: set[tuple[str, str]] = set()
    for section in (rules, registry.get("overrides", [])):
        for item in section:
            _validate_metadata_item(item, names, override="path" in item)
            if "path" in item:
                key = (item["repository"], item["path"])
                if key in override_keys:
                    raise ValueError(f"duplicate override: {key[0]}:{key[1]}")
                override_keys.add(key)
    registry["_base_dir"] = path.parent.parent
    registry["_path"] = path
    return registry


def _validate_metadata_item(item: dict[str, Any], repositories: set[str], *, override: bool) -> None:
    allowed = {
        "repository", "kind", "status", "enabled_modes", "evidence_priority",
        "authoritative_for", "component", "tags", "depends_on", "last_verified",
        "required_match", "required", "path" if override else "globs",
    }
    unknown = set(item) - allowed
    if unknown:
        raise ValueError(f"unknown registry metadata fields: {sorted(unknown)}")
    if item.get("repository") not in repositories:
        raise ValueError(f"unknown repository in rule: {item.get('repository')}")
    if item.get("kind") not in KINDS:
        raise ValueError(f"invalid evidence kind: {item.get('kind')}")
    if item.get("status") not in STATUSES:
        raise ValueError(f"invalid evidence status: {item.get('status')}")
    modes = item.get("enabled_modes")
    if not isinstance(modes, list) or any(mode not in QUERY_MODES - {"auto"} for mode in modes):
        raise ValueError(f"invalid enabled_modes for {item.get('repository')}")
    priority = item.get("evidence_priority")
    if not isinstance(priority, int) or not 0 <= priority <= 100:
        raise ValueError("evidence_priority must be an integer in [0, 100]")
    key = "path" if override else "globs"
    value = item.get(key)
    if override:
        if not isinstance(value, str) or _unsafe_relative(value):
            raise ValueError(f"override path must be safe and relative: {value}")
    elif not isinstance(value, list) or not value:
        raise ValueError("each rule requires non-empty globs")
    elif any(not isinstance(pattern, str) or _unsafe_relative(pattern) for pattern in value):
        raise ValueError("registry globs must be safe relative patterns")


def _unsafe_relative(value: str) -> bool:
    path = Path(value)
    return path.is_absolute() or ".." in path.parts


def resolve_repositories(registry: dict[str, Any], *, strict: bool = True) -> tuple[list[Repository], list[str]]:
    base = Path(registry["_base_dir"])
    repositories: list[Repository] = []
    warnings: list[str] = []
    for item in registry["repositories"]:
        env_value = os.getenv(item.get("path_env", "")) if item.get("path_env") else None
        candidates = [env_value, item["path"], *item.get("fallback_paths", [])]
        attempted: list[str] = []
        root: Path | None = None
        for raw in filter(None, candidates):
            candidate = Path(str(raw)).expanduser()
            candidate = (candidate if candidate.is_absolute() else base / candidate).resolve()
            attempted.append(str(candidate))
            if candidate.is_dir():
                root = candidate
                break
        required = bool(item.get("required", True))
        if root is None:
            message = f"repository {item['name']} not found; attempted: {', '.join(attempted)}"
            if required and strict:
                raise FileNotFoundError(message)
            warnings.append(message)
            continue
        repositories.append(Repository(item["name"], item.get("role", "unknown"), root, required))
    return repositories, warnings


def _glob_matches(path: str, pattern: str) -> bool:
    candidates = {pattern}
    pending = [pattern]
    while pending:
        current = pending.pop()
        index = current.find("**/")
        while index >= 0:
            shortened = current[:index] + current[index + 3:]
            if shortened not in candidates:
                candidates.add(shortened)
                pending.append(shortened)
            index = current.find("**/", index + 1)
    return any(fnmatch.fnmatchcase(path, candidate) for candidate in candidates)


def metadata_from_item(item: dict[str, Any], rule_id: str) -> EvidenceMetadata:
    return EvidenceMetadata(
        kind=item["kind"],
        status=item["status"],
        enabled_modes=tuple(item.get("enabled_modes", [])),
        evidence_priority=int(item["evidence_priority"]),
        authoritative_for=tuple(item.get("authoritative_for", [])),
        components=tuple(item.get("component", [])),
        tags=tuple(item.get("tags", [])),
        depends_on=tuple(item.get("depends_on", [])),
        last_verified=str(item["last_verified"]) if item.get("last_verified") else None,
        rule_id=rule_id,
    )


def classify_path(registry: dict[str, Any], repository: str, relative_path: str) -> EvidenceMetadata | None:
    for index, item in enumerate(registry.get("overrides", [])):
        if item["repository"] == repository and item["path"] == relative_path:
            return metadata_from_item(item, f"override:{index}")
    for index, item in enumerate(registry["rules"]):
        if item["repository"] != repository:
            continue
        if any(_glob_matches(relative_path, pattern) for pattern in item["globs"]):
            return metadata_from_item(item, f"rule:{index}")
    return None


def _iter_rule_paths(root: Path, patterns: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def _is_binary(path: Path) -> bool:
    try:
        return b"\0" in path.read_bytes()[:4096]
    except OSError:
        return True


def _tracked_paths(repository: Repository) -> set[str] | None:
    import subprocess
    try:
        output = subprocess.run(
            ["git", "-C", str(repository.root), "ls-files"],
            check=True, capture_output=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {line for line in output.splitlines() if line}


def build_catalog(
    registry: dict[str, Any], *, strict: bool = True
) -> tuple[list[CatalogEntry], dict[str, Any]]:
    repositories, warnings = resolve_repositories(registry, strict=strict)
    excluded = set(registry.get("exclude_dirs", []))
    maximum = int(registry.get("max_file_size_bytes", 1_000_000))
    entries: list[CatalogEntry] = []
    for repository in repositories:
        patterns = [
            pattern
            for item in registry["rules"]
            if item["repository"] == repository.name
            for pattern in item["globs"]
        ]
        patterns.extend(
            item["path"] for item in registry.get("overrides", [])
            if item["repository"] == repository.name
        )
        tracked = _tracked_paths(repository)
        for path in _iter_rule_paths(repository.root, patterns):
            relative = path.relative_to(repository.root).as_posix()
            if any(part in excluded for part in Path(relative).parts):
                continue
            try:
                if path.stat().st_size > maximum or _is_binary(path):
                    continue
            except OSError:
                continue
            metadata = classify_path(registry, repository.name, relative)
            if metadata is None:
                continue
            entries.append(CatalogEntry(
                repository, path, relative, metadata,
                None if tracked is None else relative in tracked,
            ))
    entries.sort(key=lambda item: (item.repository.name, item.relative_path))
    coverage = {
        "repositories": [repo.name for repo in repositories],
        "missing_or_optional": warnings,
        "complete": not warnings and len(repositories) == len(registry["repositories"]),
        "catalog_entries": len(entries),
    }
    return entries, coverage


def _chunk(entry: CatalogEntry, symbol: str, lines: list[str], start: int, end: int) -> EvidenceChunk:
    return EvidenceChunk(entry, symbol, "".join(lines[start - 1:end]).strip(), start, end)


def parse_markdown(entry: CatalogEntry) -> list[EvidenceChunk]:
    lines = entry.path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    headers: list[str] = []
    starts = [1]
    symbols = ["General"]
    in_fence = False
    fence_marker = ""
    for number, line in enumerate(lines, 1):
        fence = re.match(r"^\s*(```+|~~~+)", line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker == fence_marker:
                in_fence = False
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        if number != 1 or starts != [1]:
            starts.append(number)
        level = len(match.group(1))
        headers = headers[:level - 1] + [match.group(2)]
        title = " > ".join(headers)
        if number == 1 and symbols == ["General"]:
            symbols[0] = title
        else:
            symbols.append(title)
    ends = [value - 1 for value in starts[1:]] + [len(lines)]
    return [_chunk(entry, symbol, lines, start, end)
            for symbol, start, end in zip(symbols, starts, ends) if end >= start]


def parse_python(entry: CatalogEntry) -> list[EvidenceChunk]:
    text = entry.path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(keepends=True)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [_chunk(entry, "module", lines, 1, len(lines))]
    nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    chunks: list[EvidenceChunk] = []
    first = nodes[0].lineno if nodes else len(lines) + 1
    if first > 1 and "".join(lines[:first - 1]).strip():
        chunks.append(_chunk(entry, "module", lines, 1, first - 1))
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
            end = methods[0].lineno - 1 if methods else getattr(node, "end_lineno", node.lineno)
            chunks.append(_chunk(entry, f"class {node.name}", lines, node.lineno, end))
            for method in methods:
                chunks.append(_chunk(entry, f"method {node.name}.{method.name}", lines,
                                     method.lineno, getattr(method, "end_lineno", method.lineno)))
        else:
            chunks.append(_chunk(entry, f"function {node.name}", lines,
                                 node.lineno, getattr(node, "end_lineno", node.lineno)))
    return chunks or [_chunk(entry, "module", lines, 1, len(lines))]


def parse_entry(entry: CatalogEntry) -> list[EvidenceChunk]:
    suffix = entry.path.suffix.lower()
    if suffix == ".md":
        return parse_markdown(entry)
    if suffix == ".py":
        return parse_python(entry)
    lines = entry.path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    size = 80
    return [_chunk(entry, "configuration" if suffix in {".yaml", ".yml"} else "artifact",
                   lines, start, min(start + size - 1, len(lines)))
            for start in range(1, len(lines) + 1, size)]


def tokenize(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    text = text.replace("_", " ")
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,}|\d+(?:\.\d+)?|[\u4e00-\u9fff]", text.lower())


def route_mode(query: str) -> str:
    lowered = query.lower()
    rules = [
        (("legacy", "kuka", "历史实现", "旧版"), "legacy"),
        (("简历", "作品集", "headline", "面试表述", "能否写"), "portfolio"),
        (("traceback", "error", "报错", "失败", "不一致", "排查", "debug"), "debug"),
        (("如何运行", "怎么跑", "命令", "runbook", "复现"), "runbook"),
    ]
    for terms, mode in rules:
        if any(term in lowered for term in terms):
            return mode
    if any(term in lowered for term in ("原理", "为什么", "学习", "概念")) and not any(
        term in lowered for term in ("当前", "是否实现", "字段", "职责")
    ):
        return "learning"
    return "fact"


def _mode_allows(metadata: EvidenceMetadata, mode: str) -> bool:
    if mode not in metadata.enabled_modes:
        return False
    if metadata.kind == "archive" or metadata.status == "archive":
        return False
    if mode == "legacy":
        return metadata.kind == "legacy" or metadata.status == "legacy"
    if metadata.kind == "legacy" or metadata.status == "legacy":
        return False
    if mode == "fact":
        return metadata.status == "current" and metadata.kind not in {"portfolio", "reference", "spec", "runbook"}
    if mode == "learning":
        return metadata.kind in {"reference", "current_doc", "spec", "code"} and metadata.status != "needs_reconciliation"
    if mode == "runbook":
        return metadata.status == "current" and metadata.kind in {"runbook", "config", "code", "test", "current_doc"}
    if mode == "portfolio":
        return metadata.status in {"current", "derivative", "needs_reconciliation"} and metadata.kind not in {"reference", "legacy", "archive", "spec"}
    if mode == "debug":
        return metadata.status not in {"archive", "legacy"} and metadata.kind != "reference"
    return False


def _bm25(query_tokens: list[str], chunks: list[EvidenceChunk]) -> list[float]:
    documents = [tokenize(f"{chunk.symbol} {chunk.relative_path} {chunk.content}") for chunk in chunks]
    if not documents:
        return []
    average = sum(len(tokens) for tokens in documents) / len(documents)
    unique_query = set(query_tokens)
    df = {token: sum(token in set(document) for document in documents) for token in unique_query}
    total = len(documents)
    scores: list[float] = []
    for chunk, tokens in zip(chunks, documents):
        score = 0.0
        if not tokens:
            scores.append(score)
            continue
        symbol_tokens = set(tokenize(chunk.symbol))
        for token in query_tokens:
            frequency = tokens.count(token)
            if not frequency:
                continue
            normalized = frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * len(tokens) / max(average, 1)))
            inverse = math.log((total - df[token] + 0.5) / (df[token] + 0.5) + 1)
            score += normalized * inverse * (3.0 if token in symbol_tokens else 1.0)
        scores.append(score)
    return scores


def _exact_bonus(query: str, chunk: EvidenceChunk) -> float:
    lowered = query.lower()
    query_tokens = set(tokenize(query))
    symbol = chunk.symbol.lower()
    path = chunk.relative_path.lower()
    tags = " ".join(chunk.entry.metadata.tags).lower()
    bonus = 0.0
    if symbol and symbol in lowered:
        bonus = max(bonus, 20.0)
    token_overlap = query_tokens & set(tokenize(chunk.symbol))
    if token_overlap:
        bonus = max(bonus, min(16.0, 5.0 + 3.0 * len(token_overlap)))
    path_overlap = query_tokens & set(tokenize(path))
    if path_overlap:
        bonus = max(bonus, min(14.0, 4.0 + 2.0 * len(path_overlap)))
    tag_overlap = query_tokens & set(tokenize(tags))
    if tag_overlap:
        bonus = max(bonus, min(10.0, 3.0 + 2.0 * len(tag_overlap)))
    return bonus


def _intent_bonus(query: str, chunk: EvidenceChunk) -> float:
    """Small deterministic boosts for curated high-risk project claims."""
    lowered = query.lower()
    path = chunk.relative_path.lower()
    if "act" in lowered:
        if path.endswith("training/scripts/train_act_lerobot.py"):
            return 35.0
        if path.endswith("training/scripts/train_act_smoke.py"):
            return 30.0
        if path.endswith("docs/portfolio/three_repo_canonical_facts.md"):
            return 25.0
    if "94.399" in lowered or ("94" in lowered and "ms" in lowered):
        if path.endswith("docs/portfolio/canonical_experiment.md"):
            return 90.0
        if path.endswith("docs/portfolio/three_repo_canonical_facts.md"):
            return 70.0
        if path.endswith("evidence/downstream/benchmark_summary.json"):
            return 90.0
    if "三仓" in lowered and any(term in lowered for term in ("职责", "角色", "边界")):
        if path.endswith("agents.md"):
            return 70.0
        if path.endswith("docs/portfolio/three_repo_canonical_facts.md"):
            return 60.0
    if any(term in lowered for term in ("真实机器人", "真实机械臂", "sim2real", "实机")):
        if path.endswith("docs/portfolio/three_repo_canonical_facts.md"):
            return 40.0
        if path.endswith("agents.md"):
            return 15.0
    return 0.0


def retrieve_evidence(query: str, entries: list[CatalogEntry], mode: str, top_k: int = 5) -> list[RankedEvidence]:
    chunks = [chunk for entry in entries if _mode_allows(entry.metadata, mode) for chunk in parse_entry(entry)]
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    raw = _bm25(query_tokens, chunks)
    maximum = max(raw, default=0.0)
    ranked: list[RankedEvidence] = []
    status_weights = {"current": 10.0, "derivative": -10.0, "historical": -20.0,
                      "draft": -15.0, "needs_reconciliation": -25.0}
    for chunk, bm25 in zip(chunks, raw):
        intent = _intent_bonus(query, chunk)
        if bm25 <= 0 and intent <= 0:
            continue
        metadata = chunk.entry.metadata
        exact = _exact_bonus(query, chunk)
        score = (
            50.0 * bm25 / maximum
            + exact
            + 20.0 * metadata.evidence_priority / 100.0
            + status_weights.get(metadata.status, 0.0)
            + 10.0
            + intent
        )
        ranked.append(RankedEvidence(score, chunk, bm25, exact))
    ranked.sort(key=lambda item: (-item.score, -item.chunk.entry.metadata.evidence_priority,
                                  item.chunk.repository, item.chunk.relative_path, item.chunk.start_line))
    # First pass gives file diversity; second pass fills remaining slots.
    selected: list[RankedEvidence] = []
    seen_files: set[tuple[str, str]] = set()
    for item in ranked:
        key = (item.chunk.repository, item.chunk.relative_path)
        if key in seen_files:
            continue
        selected.append(item)
        seen_files.add(key)
        if len(selected) >= top_k:
            return selected
    for item in ranked:
        if item not in selected:
            selected.append(item)
        if len(selected) >= top_k:
            break
    return selected


def _resolve_claims(query: str, evidence: list[RankedEvidence]) -> tuple[str, list[dict[str, Any]]]:
    lowered = query.lower()
    paths = {item.chunk.relative_path for item in evidence}
    if "94.399" in lowered or ("94" in lowered and "ms" in lowered):
        claims = [{
            "claim": "downstream_fault_alarm_latency_ms=94.399",
            "status": "needs_reconciliation",
            "verified_headline": False,
            "reason": "原始 fault benchmark JSON 未定位；latest archived artifact is a no-fault smoke.",
        }]
        return "94.399 ms 当前未经运行产物验证，不能作为 verified headline。", claims
    if "act" in lowered and any(term in lowered for term in ("canonical", "完成", "训练", "run")):
        claims = [{
            "claim": "ACT diagnostic training and bounded Isaac evaluation completed",
            "status": "verified_diagnostic_run",
            "verified": True,
            "code_present": any("train_act_lerobot.py" in path for path in paths),
            "task_success_verified": False,
            "reason": "ACT checkpoints and E3/E3.6 runtime evidence exist, but learned-policy lift/place remain zero.",
        }]
        return "ACT diagnostic training and bounded Isaac evaluation are verified; task success is not.", claims
    if not evidence:
        return "当前项目证据不足，无法确认。", []
    return "已返回按知识注册表过滤和排序的项目证据；最终事实应服从证据类型、状态与冲突标记。", []


def _llm_prompt(query: str, evidence: list[RankedEvidence]) -> str:
    context = "\n\n".join(
        f"[{item.chunk.evidence_id()}; kind={item.chunk.entry.metadata.kind}; "
        f"status={item.chunk.entry.metadata.status}]\n{item.chunk.content}"
        for item in evidence
    )
    return (
        "仅根据以下已筛选项目证据总结。引用 evidence id；不得补充外部事实。"
        "needs_reconciliation/portfolio/spec/legacy 不得写成当前已验证事实。\n\n"
        f"证据：\n{context}\n\n问题：{query}\n回答："
    )


def run_optional_llm(query: str, evidence: list[RankedEvidence]) -> str | None:
    if not evidence:
        return None
    prompt = _llm_prompt(query, evidence)
    try:
        if os.getenv("OPENAI_API_KEY"):
            request = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps({
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                }).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())["choices"][0]["message"]["content"].strip()
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        request = urllib.request.Request(
            f"{host}/api/generate",
            data=json.dumps({"model": os.getenv("OLLAMA_MODEL", "llama3"), "prompt": prompt, "stream": False}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=30.0) as response:
            return json.loads(response.read())["response"].strip()
    except Exception:
        return None


def query_project(
    query: str,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    mode: str = "auto",
    top_k: int = 5,
    no_llm: bool = True,
) -> QueryResult:
    if mode not in QUERY_MODES:
        raise ValueError(f"invalid query mode: {mode}")
    registry = load_registry(registry_path)
    entries, coverage = build_catalog(registry)
    selected_mode = route_mode(query) if mode == "auto" else mode
    evidence = retrieve_evidence(query, entries, selected_mode, top_k)
    conclusion, claims = _resolve_claims(query, evidence)
    result = QueryResult(query, mode, selected_mode, coverage, evidence, conclusion, claims)
    if not no_llm:
        result.llm_summary = run_optional_llm(query, evidence)
    return result


def render_query_text(result: QueryResult, *, compatibility: bool = False) -> str:
    lines = [f"查询模式: {result.mode}", f"仓库覆盖: {', '.join(result.coverage['repositories'])}"]
    if not result.evidence:
        lines.append("当前项目证据不足，无法确认。")
        return "\n".join(lines)
    lines.append("检索证据：")
    for rank, item in enumerate(result.evidence, 1):
        data = item.to_dict()
        lines.extend([
            "",
            f"[{rank}] 仓库: {data['repository']}",
            f"路径: {data['path']}",
            f"行号: L{data['line_start']}-L{data['line_end']}",
            f"章节/符号: {data['symbol']}",
            f"证据类型: {data['kind']}",
            f"证据状态: {data['status']}",
            f"最后验证: {data['last_verified'] or 'unknown'}",
            f"内容片段: {data['snippet']}",
            f"检索分数: {data['score']:.6f}",
        ])
    lines.extend(["", f"结论: {result.conclusion}"])
    if result.claims:
        lines.append("Claim 状态: " + json.dumps(result.claims, ensure_ascii=False))
    if result.llm_summary:
        lines.extend(["", "LLM 回答：", result.llm_summary])
    elif compatibility:
        lines.extend(["", "LLM 回答：", "未配置或未启用 LLM；以上为本地检索证据。"])
    return "\n".join(lines)
