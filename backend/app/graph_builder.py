from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any


SKIP_DIRS = {
    ".cache",
    ".git",
    ".idea",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
}

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".pyi": "Python Stub",
    ".pyw": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript JSX",
    ".ts": "TypeScript",
    ".tsx": "TypeScript TSX",
    ".mjs": "JavaScript Module",
    ".cjs": "JavaScript CommonJS",
    ".mts": "TypeScript Module",
    ".cts": "TypeScript CommonJS",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".md": "Markdown",
    ".toml": "TOML",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".c": "C",
    ".h": "C Header",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hpp": "C++ Header",
    ".hh": "C++ Header",
    ".hxx": "C++ Header",
    ".java": "Java",
}

TEXT_EXTENSIONS = set(LANGUAGE_BY_EXTENSION.keys())
PYTHON_EXTENSIONS = {".py", ".pyw", ".pyi"}
CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}

_BRANCH_PATTERN = re.compile(
    r"\b(if|else\s+if|for|while|case|catch|except|switch|\?|&&|\|\|)\b"
)


def make_id(path: Path, root: Path) -> str:
    relative_path = path.relative_to(root)

    if str(relative_path) == ".":
        return "."

    return relative_path.as_posix()


def make_parent_id(path: Path, root: Path) -> str:
    parent = path.parent

    if parent == root:
        return "."

    return parent.relative_to(root).as_posix()


def count_lines(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    return len(lines), sum(1 for line in lines if line.strip())


def estimate_complexity(path: Path, extension: str) -> int | None:
    if extension in PYTHON_EXTENSIONS:
        return estimate_python_complexity(path)

    if extension in CPP_EXTENSIONS or extension in JS_TS_EXTENSIONS:
        text = path.read_text(encoding="utf-8", errors="ignore")
        matches = _BRANCH_PATTERN.findall(text)
        return 1 + len(matches)

    return None


def estimate_python_complexity(path: Path) -> int | None:
    text = path.read_text(encoding="utf-8", errors="ignore")

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None

    branch_nodes = (
        ast.BoolOp,
        ast.ExceptHandler,
        ast.For,
        ast.If,
        ast.IfExp,
        ast.Match,
        ast.Try,
        ast.While,
    )
    complexity = 1

    for node in ast.walk(tree):
        if isinstance(node, branch_nodes):
            complexity += 1
        elif isinstance(node, ast.comprehension):
            complexity += 1

    return complexity


def build_stats(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    languages: Counter[str] = Counter()
    file_count = 0
    folder_count = 0
    total_loc = 0
    total_sloc = 0
    total_complexity = 0
    complexity_files = 0

    for node in nodes:
        if node["type"] == "folder":
            folder_count += 1
            continue

        file_count += 1
        total_loc += node.get("loc") or 0
        total_sloc += node.get("sloc") or 0
        languages[node.get("language", "Unknown")] += 1

        if node.get("complexity") is not None:
            total_complexity += node["complexity"]
            complexity_files += 1

    edge_types = Counter(edge["type"] for edge in edges)

    return {
        "files": file_count,
        "folders": folder_count,
        "edges": len(edges),
        "contains_edges": edge_types["contains"],
        "dependency_edges": edge_types["depends_on"],
        "total_loc": total_loc,
        "total_sloc": total_sloc,
        "total_complexity": total_complexity,
        "average_complexity": (
            round(total_complexity / complexity_files, 2)
            if complexity_files
            else 0
        ),
        "languages": dict(sorted(languages.items())),
    }


def path_to_id_if_inside_root(path: Path, root: Path) -> str | None:
    try:
        path = path.resolve()
        root = root.resolve()
        path.relative_to(root)
    except ValueError:
        return None

    if path.exists() and path.is_file():
        return make_id(path, root)

    return None


def add_dependency_edge(
    edges: list[dict[str, Any]],
    seen_dependency_edges: set[tuple[str, str]],
    source_id: str,
    target_id: str,
) -> None:
    if source_id == target_id:
        return

    edge_key = (source_id, target_id)

    if edge_key in seen_dependency_edges:
        return

    seen_dependency_edges.add(edge_key)
    edges.append(
        {
            "id": f"depends:{source_id}->{target_id}",
            "source": source_id,
            "target": target_id,
            "type": "depends_on",
            "label": "imports",
        }
    )
