#!/usr/bin/env python3
"""Emit reproducible structural metrics for the repository-wide review.

The output intentionally reports measurements rather than a composite score.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


PYTHON_ROOTS = ("src", "tests", "scripts")
MARKERS = ("TODO", "FIXME", "HACK", "legacy", "compatib", "migration", "fallback")
BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.Match,
    ast.IfExp,
    ast.comprehension,
)


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def name_for(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    names = [getattr(node, "name")]
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(current.name)
        current = parents.get(current)
    return ".".join(reversed(names))


def analyze_python(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=relative)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    functions = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = node.args
        parameter_count = (
            len(arguments.posonlyargs) + len(arguments.args) + len(arguments.kwonlyargs)
        )
        parameter_count += int(arguments.vararg is not None) + int(arguments.kwarg is not None)
        descendants = tuple(ast.walk(node))
        functions.append(
            {
                "name": name_for(node, parents),
                "line": node.lineno,
                "lines": node.end_lineno - node.lineno + 1,
                "parameters": parameter_count,
                "branches": sum(isinstance(item, BRANCH_NODES) for item in descendants),
                "returns": sum(isinstance(item, ast.Return) for item in descendants),
                "raises": sum(isinstance(item, ast.Raise) for item in descendants),
                "except_handlers": sum(isinstance(item, ast.ExceptHandler) for item in descendants),
            }
        )
    return {
        "path": relative,
        "lines": len(text.splitlines()),
        "functions": len(functions),
        "classes": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
        "imports": sorted(imports),
        "except_handlers": sum(isinstance(node, ast.ExceptHandler) for node in ast.walk(tree)),
        "broad_exception_handlers": sum(
            isinstance(node, ast.ExceptHandler)
            and (
                node.type is None
                or isinstance(node.type, ast.Name) and node.type.id == "Exception"
            )
            for node in ast.walk(tree)
        ),
        "marker_counts": {marker: text.lower().count(marker.lower()) for marker in MARKERS},
        "function_details": functions,
    }


def git_change_counts(root: Path) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["git", "log", "--format=", "--name-only", "--", "src", "tests"],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    counts = Counter(line for line in result.stdout.splitlines() if line)
    return [{"path": path, "commits_touching": count} for path, count in counts.most_common()]


def build_report(root: Path) -> dict[str, Any]:
    python_files = sorted(
        path
        for base in PYTHON_ROOTS
        for path in (root / base).rglob("*.py")
        if "__pycache__" not in path.parts
    )
    files = [analyze_python(root, path) for path in python_files]
    functions = [
        {"path": item["path"], **function}
        for item in files
        for function in item.pop("function_details")
    ]
    production = [item for item in files if item["path"].startswith("src/")]
    tests = [item for item in files if item["path"].startswith("tests/")]
    internal_imports = Counter(
        imported
        for item in production
        for imported in item["imports"]
        if imported == "rfi"
    )
    return {
        "schema_version": 1,
        "scope": {"python_roots": list(PYTHON_ROOTS), "marker_terms": list(MARKERS)},
        "totals": {
            "python_files": len(files),
            "production_python_files": len(production),
            "test_python_files": len(tests),
            "production_python_lines": sum(item["lines"] for item in production),
            "test_python_lines": sum(item["lines"] for item in tests),
            "functions": len(functions),
            "broad_exception_handlers": sum(item["broad_exception_handlers"] for item in files),
            "internal_import_statements": sum(internal_imports.values()),
        },
        "largest_production_modules": sorted(
            production, key=lambda item: item["lines"], reverse=True
        )[:30],
        "largest_test_modules": sorted(tests, key=lambda item: item["lines"], reverse=True)[:30],
        "largest_functions": sorted(functions, key=lambda item: item["lines"], reverse=True)[:50],
        "most_branched_functions": sorted(
            functions, key=lambda item: (item["branches"], item["lines"]), reverse=True
        )[:50],
        "highest_parameter_functions": sorted(
            functions, key=lambda item: (item["parameters"], item["lines"]), reverse=True
        )[:50],
        "git_change_concentration": git_change_counts(root)[:50],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.root.resolve())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
