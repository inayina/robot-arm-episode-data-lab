from pathlib import Path

import pytest

from scripts import rag_assistant as rag


def write_config(tmp_path: Path, repositories: list[tuple[str, Path]]) -> Path:
    config = tmp_path / "configs" / "rag_sources.yaml"
    config.parent.mkdir()
    entries = "\n".join(
        f"  - name: {name}\n    path: {path}" for name, path in repositories
    )
    config.write_text(
        f"repositories:\n{entries}\n"
        "include:\n  - README.md\n  - docs/**/*.md\n  - scripts/**/*.py\n"
        "exclude_dirs: [.git, dataset]\nmax_file_size_bytes: 100000\n",
        encoding="utf-8",
    )
    return config


def test_config_loading_and_multi_repository_sources(tmp_path):
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (first / "README.md").write_text("# Alpha\nunique_robot_token\n", encoding="utf-8")
    (second / "README.md").write_text("# Beta\nunique_bridge_token\n", encoding="utf-8")
    config = rag.load_config(write_config(tmp_path, [("upstream", first), ("downstream", second)]))

    chunks = rag.load_all_documents(config)

    assert {chunk.repository for chunk in chunks} == {"upstream", "downstream"}
    assert rag.retrieve_chunks("unique_bridge_token", chunks)[0][1].repository == "downstream"


def test_source_uses_environment_path_before_portable_fallback(tmp_path, monkeypatch):
    configured = tmp_path / "missing-sibling"
    override = tmp_path / "actual-upstream"
    override.mkdir()
    config = {
        "_base_dir": tmp_path,
        "repositories": [{
            "name": "upstream",
            "path": str(configured),
            "path_env": "TEST_RAG_UPSTREAM",
            "fallback_paths": [str(tmp_path / "other")],
        }],
        "include": ["README.md"],
    }
    monkeypatch.setenv("TEST_RAG_UPSTREAM", str(override))

    sources = rag.configured_sources(config)

    assert sources == [rag.Source("upstream", override.resolve())]


def test_single_query_prints_required_evidence_fields(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Gate\nThe gate validates episodes.\n", encoding="utf-8")
    config = write_config(tmp_path, [("middle", repo)])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    assert rag.main(["--config", str(config), "--query", "gate"]) == 0
    output = capsys.readouterr().out
    for label in ("仓库: middle", "路径: README.md", "行号:", "章节/符号:", "内容片段:", "检索分数:"):
        assert label in output


def test_empty_result_uses_required_phrase(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Known\nalpha\n", encoding="utf-8")
    config = write_config(tmp_path, [("repo", repo)])

    rag.main(["--config", str(config), "--query", "zzzz_no_match"])

    assert "当前项目证据不足" in capsys.readouterr().out


def test_interactive_mode_accepts_query_then_quits(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Motion\nservo controller\n", encoding="utf-8")
    config = write_config(tmp_path, [("repo", repo)])
    answers = iter(["servo", "q"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    assert rag.main(["--config", str(config)]) == 0
    output = capsys.readouterr().out
    assert "检索证据" in output
    assert "再见" in output


def test_python_chunks_report_code_symbol(tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "worker.py").write_text(
        "def confirmed_feature():\n    return 'implemented'\n", encoding="utf-8"
    )
    config = rag.load_config(write_config(tmp_path, [("repo", repo)]))

    chunks = rag.load_all_documents(config)

    assert any(chunk.symbol == "function confirmed_feature" for chunk in chunks)
