#!/usr/bin/env python3
"""Lightweight, local multi-repository RAG command line assistant."""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "rag_sources.yaml"
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class Source:
    name: str
    path: Path


@dataclass
class DocumentChunk:
    repository: str
    repository_root: Path
    filepath: Path
    symbol: str
    content: str
    start_line: int
    end_line: int

    @property
    def header_title(self) -> str:  # compatibility with the original script
        return self.symbol

    @property
    def relative_path(self) -> str:
        return self.filepath.relative_to(self.repository_root).as_posix()


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    """Load and minimally validate a RAG source configuration."""
    path = path.resolve()
    with path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    if not isinstance(config.get("repositories"), list) or not config.get("include"):
        raise ValueError("rag config requires non-empty 'repositories' and 'include'")
    config["_base_dir"] = path.parent.parent
    return config


def configured_sources(config: dict) -> list[Source]:
    base = Path(config["_base_dir"])
    sources = []
    for item in config["repositories"]:
        if isinstance(item, str):
            candidates = [item]
            name = None
        else:
            env_path = os.getenv(item.get("path_env", "")) if item.get("path_env") else None
            candidates = [env_path, item["path"], *item.get("fallback_paths", [])]
            name = item.get("name")
        for raw in filter(None, candidates):
            candidate = Path(raw).expanduser()
            root = (candidate if candidate.is_absolute() else base / candidate).resolve()
            if root.is_dir():
                sources.append(Source(name or root.name, root))
                break
    return sources


def _is_binary(path: Path) -> bool:
    try:
        return b"\0" in path.read_bytes()[:4096]
    except OSError:
        return True


def iter_source_files(source: Source, config: dict):
    excluded = set(config.get("exclude_dirs", []))
    maximum = int(config.get("max_file_size_bytes", 1_000_000))
    seen: set[Path] = set()
    for pattern in config["include"]:
        for path in source.path.glob(pattern):
            if path in seen or not path.is_file():
                continue
            relative = path.relative_to(source.path)
            if any(part in excluded for part in relative.parts):
                continue
            try:
                if path.stat().st_size > maximum or _is_binary(path):
                    continue
            except OSError:
                continue
            seen.add(path)
            yield path


def _chunk(source: Source, path: Path, symbol: str, lines: list[str], start: int, end: int):
    content = "".join(lines[start - 1:end]).strip()
    return DocumentChunk(source.name, source.path, path, symbol, content, start, end)


def parse_markdown_file(path: Path, source: Source | None = None) -> list[DocumentChunk]:
    source = source or Source(path.parent.name, path.parent)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    headers: list[str] = []
    starts = [1]
    symbols = ["General"]
    for number, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            if number != 1 or starts != [1]:
                starts.append(number)
            elif number == 1:
                starts[0] = 1
            level = len(match.group(1))
            headers = headers[: level - 1] + [match.group(2)]
            title = " > ".join(filter(None, headers))
            if number == 1 and symbols == ["General"]:
                symbols[0] = title
            else:
                symbols.append(title)
    ends = [n - 1 for n in starts[1:]] + [len(lines)]
    return [_chunk(source, path, symbol, lines, start, end)
            for symbol, start, end in zip(symbols, starts, ends) if end >= start]


def parse_python_file(path: Path, source: Source) -> list[DocumentChunk]:
    """Parse a Python file into per-symbol DocumentChunks.

    Top-level classes and functions are always emitted as their own chunks.
    Methods *inside* classes are also emitted individually (labelled
    ``ClassName.method_name``) so that large classes do not dilute the BM25
    score of their individual methods.  This is the key fix that allows
    private helpers like ``_pybullet_ik`` (which contains the Jacobian SVD
    singularity check) to surface as top-1 results for queries such as
    ``SVD singularity Jacobian``.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(keepends=True)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [_chunk(source, path, "module", lines, 1, len(lines))]

    chunks = []
    top_nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    first = top_nodes[0].lineno if top_nodes else len(lines) + 1
    if first > 1 and "".join(lines[: first - 1]).strip():
        chunks.append(_chunk(source, path, "module", lines, 1, first - 1))

    for node in top_nodes:
        if isinstance(node, ast.ClassDef):
            # Emit the class header (up to first method) as its own chunk
            method_nodes = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            class_end = (method_nodes[0].lineno - 1) if method_nodes else getattr(node, "end_lineno", node.lineno)
            chunks.append(_chunk(source, path, f"class {node.name}", lines, node.lineno, class_end))
            # Emit each method as a separate chunk labelled ClassName.method_name
            for method in method_nodes:
                label = f"method {node.name}.{method.name}"
                chunks.append(_chunk(source, path, label, lines, method.lineno,
                                     getattr(method, "end_lineno", method.lineno)))
        else:
            kind = "function"
            chunks.append(_chunk(source, path, f"{kind} {node.name}", lines, node.lineno,
                                 getattr(node, "end_lineno", node.lineno)))

    return chunks or [_chunk(source, path, "module", lines, 1, len(lines))]



def parse_file(path: Path, source: Source) -> list[DocumentChunk]:
    if path.suffix.lower() == ".md":
        return parse_markdown_file(path, source)
    if path.suffix.lower() == ".py":
        return parse_python_file(path, source)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    size = 80
    return [_chunk(source, path, "configuration", lines, start, min(start + size - 1, len(lines)))
            for start in range(1, len(lines) + 1, size)]


def load_all_documents(config_or_repo: dict | Path) -> list[DocumentChunk]:
    """Load configured sources; accepting a Path preserves the old public API."""
    if isinstance(config_or_repo, Path):
        config = load_config()
        config["repositories"] = [{"name": config_or_repo.name, "path": "."}]
        config["_base_dir"] = config_or_repo.resolve()
    else:
        config = config_or_repo
    return [chunk for source in configured_sources(config)
            for path in iter_source_files(source, config)
            for chunk in parse_file(path, source)]


def tokenize(text: str) -> list[str]:
    """Tokenise text into sub-word tokens.

    * CJK characters are kept as single tokens so Chinese queries work without
      an external tokeniser library.
    * CamelCase identifiers (e.g. ``PandaActionAdapter``) are split at
      upper-case boundaries so a query for ``hold`` or ``panda`` still matches
      the class-level chunk even though the class name is written in PascalCase.
    """
    # First, split CamelCase / PascalCase into constituent words.
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    # Then extract normal alphanumeric tokens and individual CJK characters.
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,}|[\u4e00-\u9fff]", text.lower())


def retrieve_chunks(query: str, chunks: list[DocumentChunk], top_k: int = 5):
    """BM25-based retrieval with symbol and source-file boosting.

    Improvements over the previous bare TF-IDF implementation:

    1. **BM25 term-frequency saturation** (k1=1.5, b=0.75): long source files
       are no longer penalised relative to short test helpers because BM25
       applies a tunable length normalisation rather than a hard division.
    2. **Symbol exact-match 3× boost**: tokens that appear in the chunk's
       symbol name (class / function / section heading) get triple weight,
       up from the previous 2×, so ``class PandaActionAdapter`` ranks above
       a short test function that merely *calls* the class.
    3. **Source-file 1.2× boost**: implementation files (``.py`` files outside
       ``test*/``) receive a mild confidence premium over unit tests when the
       query is about *what something does* rather than *how it is tested*.
    """
    query_tokens = tokenize(query)
    if not query_tokens or not chunks:
        return []

    # BM25 hyper-parameters (Robertson & Zaragoza, 2009 defaults)
    k1 = 1.5
    b = 0.75

    document_tokens = [tokenize(f"{c.symbol} {c.relative_path} {c.content}") for c in chunks]
    avg_dl = sum(len(t) for t in document_tokens) / max(len(document_tokens), 1)

    df = {token: sum(token in set(tokens) for tokens in document_tokens) for token in set(query_tokens)}
    N = len(chunks)

    scores = []
    for chunk, tokens in zip(chunks, document_tokens):
        if not tokens:
            continue
        dl = len(tokens)
        symbol_tokens = set(tokenize(chunk.symbol))
        bm25_score = 0.0
        for token in query_tokens:
            tf = tokens.count(token)
            if tf == 0:
                continue
            # BM25 TF with length normalisation
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
            idf = math.log((N - df[token] + 0.5) / (df[token] + 0.5) + 1)
            # Symbol name exact-match earns a 3× boost
            symbol_boost = 3.0 if token in symbol_tokens else 1.0
            bm25_score += tf_norm * idf * symbol_boost

        if bm25_score <= 0:
            continue

        # Source-file premium: implementation files outrank test files slightly
        relative = str(chunk.relative_path)
        is_test = relative.startswith("test") or "/test" in relative
        is_source_py = chunk.filepath.suffix == ".py" and not is_test
        source_boost = 1.2 if is_source_py else 1.0

        scores.append((bm25_score * source_boost, chunk))

    return sorted(scores, key=lambda item: item[0], reverse=True)[:top_k]


def _prompt(query: str, chunks: list[DocumentChunk]) -> str:
    def evidence_kind(chunk: DocumentChunk) -> str:
        if chunk.relative_path.startswith("tests/"):
            return "测试代码（最高优先级）"
        if chunk.filepath.suffix == ".py":
            return "项目代码"
        return "文档或配置声明"

    context = "\n\n".join(
        f"[{evidence_kind(c)}; {c.repository}/{c.relative_path}:L{c.start_line}-L{c.end_line}; {c.symbol}]\n{c.content}"
        for c in chunks)
    return f"""你是项目证据助手。仅根据给定证据回答问题。必须按以下类别明确标注每项陈述：
[项目代码确认已实现]、[文档声明但代码未确认]、[根据证据作出的推断]、[通用背景知识]。
测试和代码优先于文档；发现冲突时明确指出双方及优先依据。不得用行业惯例补全项目事实。
若证据不能回答，必须原样写出“当前项目证据不足”。不要把文档声明描述成已经实现。

证据：
{context}

问题：{query}
回答："""


def query_ollama(prompt: str, host: str) -> str:
    request = urllib.request.Request(f"{host.rstrip('/')}/api/generate",
        data=json.dumps({"model": os.getenv("OLLAMA_MODEL", "llama3"), "prompt": prompt, "stream": False}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["response"].strip()


def query_openai(prompt: str, api_key: str) -> str:
    request = urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=json.dumps({"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["choices"][0]["message"]["content"].strip()


def run_llm_qa(query: str, matched_chunks: list[DocumentChunk]) -> str | None:
    if not matched_chunks:
        return "当前项目证据不足"
    prompt = _prompt(query, matched_chunks)
    try:
        if os.getenv("OPENAI_API_KEY"):
            return query_openai(prompt, os.environ["OPENAI_API_KEY"])
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        # Preserve the original zero-configuration local Ollama behavior, with a
        # short probe so a missing daemon does not make the CLI feel sluggish.
        with urllib.request.urlopen(ollama_host, timeout=.3):
            return query_ollama(prompt, ollama_host)
    except Exception as error:
        return f"LLM 调用失败：{error}"
    return None


def answer_query(query: str, chunks: list[DocumentChunk], top_k: int = 5) -> None:
    results = retrieve_chunks(query, chunks, top_k)
    if not results:
        print("当前项目证据不足")
        return
    print("检索证据：")
    for rank, (score, chunk) in enumerate(results, 1):
        snippet = re.sub(r"\s+", " ", chunk.content).strip()[:350]
        print(f"\n[{rank}] 仓库: {chunk.repository}")
        print(f"路径: {chunk.relative_path}")
        print(f"行号: L{chunk.start_line}-L{chunk.end_line}")
        print(f"章节/符号: {chunk.symbol}")
        print(f"内容片段: {snippet}")
        print(f"检索分数: {score:.6f}")
    print("\nLLM 回答：")
    answer = run_llm_qa(query, [chunk for _, chunk in results])
    print(answer or "未配置 LLM；以上为本地检索证据。项目事实请仅依据这些证据判断。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="执行一次查询后退出")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="来源配置 YAML")
    parser.add_argument("--top-k", type=int, default=5, help="返回证据条数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # The historical CLI remains the compatibility surface.  Default project
    # queries now use the registry-backed V1 implementation; explicit legacy
    # rag_sources.yaml fixtures/custom configs retain the old public behavior.
    if args.config.resolve() == DEFAULT_CONFIG.resolve():
        try:
            from project_knowledge.core import query_project, render_query_text

            def answer_v1(query: str) -> None:
                result = query_project(query, mode="auto", top_k=args.top_k, no_llm=False)
                print(render_query_text(result, compatibility=True))

            if args.query is not None:
                answer_v1(args.query.strip())
                return 0
            print("三仓项目 RAG 助手（输入 q 退出）")
            while True:
                try:
                    query = input("请输入您的问题: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n再见！")
                    break
                if query.lower() in {"q", "quit", "exit"}:
                    print("再见！")
                    break
                if query:
                    answer_v1(query)
            return 0
        except (OSError, ValueError, yaml.YAMLError) as error:
            print(f"配置或扫描失败：{error}")
            return 2
    try:
        config = load_config(args.config)
        chunks = load_all_documents(config)
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"配置或扫描失败：{error}")
        return 2
    if args.query is not None:
        answer_query(args.query.strip(), chunks, args.top_k)
        return 0
    print("三仓项目 RAG 助手（输入 q 退出）")
    while True:
        try:
            query = input("请输入您的问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if query.lower() in {"q", "quit", "exit"}:
            print("再见！")
            break
        if query:
            answer_query(query, chunks, args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
