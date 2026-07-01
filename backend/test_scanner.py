from __future__ import annotations

from pathlib import Path

from app.ai_summary import summarize_file
from app.cache import SummaryCache
from app.scanner import scan_repo


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_repo_detects_internal_dependencies_and_metrics(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    write_file(repo / "pkg" / "__init__.py", "")
    write_file(
        repo / "pkg" / "util.py",
        "def helper(value):\n    return value + 1\n",
    )
    write_file(
        repo / "app.py",
        "import pkg.util\n\nif __name__ == '__main__':\n    print(pkg.util.helper(1))\n",
    )
    write_file(repo / "frontend" / "view.js", "export const label = 'Repo';\n")
    write_file(
        repo / "frontend" / "main.js",
        "import { label } from './view';\nconsole.log(label);\n",
    )
    write_file(repo / "include" / "util.h", "int add(int left, int right);\n")
    write_file(
        repo / "src" / "main.cpp",
        '#include "../include/util.h"\nint main() { return 0; }\n',
    )

    graph = scan_repo(str(repo))
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    dependency_edges = {
        (edge["source"], edge["target"])
        for edge in graph["edges"]
        if edge["type"] == "depends_on"
    }

    assert nodes_by_id["app.py"]["loc"] == 4
    assert nodes_by_id["app.py"]["complexity"] >= 2
    assert nodes_by_id["frontend/main.js"]["language"] == "JavaScript"
    assert ("app.py", "pkg/util.py") in dependency_edges
    assert ("frontend/main.js", "frontend/view.js") in dependency_edges
    assert ("src/main.cpp", "include/util.h") in dependency_edges
    assert graph["stats"]["dependency_edges"] == 3
    assert graph["stats"]["total_loc"] > 0


def test_scan_repo_resolves_backend_package_imports(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    write_file(repo / "backend" / "app" / "__init__.py", "")
    write_file(repo / "backend" / "app" / "graph_builder.py", "def build():\n    return {}\n")
    write_file(
        repo / "backend" / "app" / "scanner.py",
        "from app.graph_builder import build\n\nresult = build()\n",
    )
    write_file(
        repo / "backend" / "main.py",
        "from app.scanner import result\n\nprint(result)\n",
    )

    graph = scan_repo(str(repo))
    dependency_edges = {
        (edge["source"], edge["target"])
        for edge in graph["edges"]
        if edge["type"] == "depends_on"
    }

    assert ("backend/main.py", "backend/app/scanner.py") in dependency_edges
    assert (
        "backend/app/scanner.py",
        "backend/app/graph_builder.py",
    ) in dependency_edges
    assert graph["stats"]["dependency_edges"] == 2


def test_scan_repo_skips_generated_and_dependency_directories(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    write_file(repo / "app.py", "print('ok')\n")
    write_file(repo / "node_modules" / "pkg" / "index.js", "export default 1;\n")
    write_file(repo / "__pycache__" / "app.pyc", "compiled\n")

    graph = scan_repo(str(repo))
    node_ids = {node["id"] for node in graph["nodes"]}

    assert "app.py" in node_ids
    assert "node_modules/pkg/index.js" not in node_ids
    assert "__pycache__/app.pyc" not in node_ids


def test_summary_cache_reuses_and_invalidates_by_content_hash(tmp_path: Path) -> None:
    repo = tmp_path / "sample"
    source = repo / "app.py"
    write_file(source, "def greet():\n    return 'hello'\n")
    cache = SummaryCache(tmp_path / "summary_cache.json")

    first = summarize_file(
        repo_path=str(repo),
        file_id="app.py",
        provider="local",
        cache=cache,
    )
    second = summarize_file(
        repo_path=str(repo),
        file_id="app.py",
        provider="local",
        cache=cache,
    )

    write_file(source, "def greet(name):\n    return f'hello {name}'\n")
    third = summarize_file(
        repo_path=str(repo),
        file_id="app.py",
        provider="local",
        cache=cache,
    )

    assert first["cached"] is False
    assert second["cached"] is True
    assert third["cached"] is False
    assert first["content_hash"] != third["content_hash"]
