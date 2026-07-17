"""Command line interface for Project Evidence Agent V1."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .audit import audit_project, render_audit_markdown
from .core import DEFAULT_REGISTRY, query_project, render_query_text
from .impact import analyze_impact, render_impact_markdown


def _query_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("query", help="Query classified project evidence")
    parser.add_argument("text", nargs="?", help="Query text (alternative to --query)")
    parser.add_argument("--query", dest="query_option", help="Query text")
    parser.add_argument("--mode", choices=["auto", "fact", "debug", "runbook", "learning", "portfolio", "legacy"], default="auto")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--no-llm", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _query_parser(subparsers)
    audit = subparsers.add_parser("audit", help="Audit registry and Markdown sources without modifying them")
    audit.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    audit.add_argument("--json-out", type=Path)
    audit.add_argument("--markdown-out", type=Path)
    audit.add_argument("--no-fail", action="store_true")
    impact = subparsers.add_parser("impact", help="Map a Git diff to components, tests and docs")
    impact.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    impact.add_argument("--repository", default="robot-arm-episode-data-lab")
    impact.add_argument("--base", default="HEAD~1")
    impact.add_argument("--head", default="HEAD")
    impact.add_argument("--format", choices=["json", "markdown"], default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "query":
            query = args.query_option or args.text
            if not query:
                raise ValueError("query text is required")
            result = query_project(query, registry_path=args.registry, mode=args.mode,
                                   top_k=args.top_k, no_llm=args.no_llm)
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) if args.format == "json"
                  else render_query_text(result))
            return 0
        if args.command == "audit":
            report = audit_project(args.registry)
            json_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            markdown = render_audit_markdown(report)
            if args.json_out:
                args.json_out.write_text(json_text, encoding="utf-8")
            if args.markdown_out:
                args.markdown_out.write_text(markdown, encoding="utf-8")
            if not args.json_out and not args.markdown_out:
                print(markdown, end="")
            if args.no_fail:
                return 0
            return 2 if report["counts"]["error"] else (1 if report["counts"]["warning"] else 0)
        report = analyze_impact(registry_path=args.registry, repository_name=args.repository,
                                base=args.base, head=args.head)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json"
              else render_impact_markdown(report), end="\n" if args.format == "json" else "")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"project evidence command failed: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
