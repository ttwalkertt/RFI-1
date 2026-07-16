#!/usr/bin/env python3
"""Dependency-free bootstrap lint, formatting, and annotation-policy checks."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = (ROOT / "src", ROOT / "scripts", ROOT / "tests")


def python_files() -> list[Path]:
    """Return project Python files in deterministic order."""
    return sorted(path for root in PYTHON_ROOTS for path in root.rglob("*.py"))


def relative(path: Path) -> str:
    """Return a repository-relative display path."""
    return path.relative_to(ROOT).as_posix()


def check_lint() -> list[str]:
    """Check parseability and a small set of explicit bootstrap lint rules."""
    errors: list[str] = []
    for path in python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative(path))
        except SyntaxError as error:
            errors.append(f"{relative(path)}:{error.lineno}: syntax error: {error.msg}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                errors.append(f"{relative(path)}:{node.lineno}: wildcard import")
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                errors.append(f"{relative(path)}:{node.lineno}: bare except")
    return errors


def check_format() -> list[str]:
    """Validate the repository's minimal Python text-format policy."""
    errors: list[str] = []
    for path in python_files():
        content = path.read_text(encoding="utf-8")
        if content and not content.endswith("\n"):
            errors.append(f"{relative(path)}: missing final newline")
        for number, line in enumerate(content.splitlines(), start=1):
            if line.rstrip() != line:
                errors.append(f"{relative(path)}:{number}: trailing whitespace")
            if "\t" in line:
                errors.append(f"{relative(path)}:{number}: tab character")
            if len(line) > 100:
                errors.append(f"{relative(path)}:{number}: line exceeds 100 characters")
    return errors


def function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return function nodes including methods and nested helpers."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def check_type_policy() -> list[str]:
    """Require annotations on implementation functions while the package is dependency-free."""
    errors: list[str] = []
    for path in python_files():
        if path.is_relative_to(ROOT / "tests"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative(path))
        for node in function_nodes(tree):
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            arguments = [argument for argument in arguments if argument.arg not in {"self", "cls"}]
            for argument in arguments:
                if argument.annotation is None:
                    errors.append(
                        f"{relative(path)}:{node.lineno}: {node.name} argument "
                        f"'{argument.arg}' lacks annotation"
                    )
            if node.args.vararg and node.args.vararg.annotation is None:
                errors.append(f"{relative(path)}:{node.lineno}: *args lacks annotation")
            if node.args.kwarg and node.args.kwarg.annotation is None:
                errors.append(f"{relative(path)}:{node.lineno}: **kwargs lacks annotation")
            if node.returns is None:
                errors.append(
                    f"{relative(path)}:{node.lineno}: {node.name} lacks return annotation"
                )
    return errors


def main() -> int:
    """Run the selected check and print exact, review-friendly results."""
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=("lint", "format", "typecheck"))
    check = parser.parse_args().check
    checks = {
        "lint": check_lint,
        "format": check_format,
        "typecheck": check_type_policy,
    }
    errors = checks[check]()
    print(f"policy: dependency-free repository {check} check")
    print(f"python files checked: {len(python_files())}")
    if errors:
        print("result: FAIL")
        print("\n".join(errors))
        return 1
    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
