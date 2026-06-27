from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from app.graph_builder import (
    SKIP_DIRS,
    LANGUAGE_BY_EXTENSION,
    TEXT_EXTENSIONS,
    PYTHON_EXTENSIONS,
    CPP_EXTENSIONS,
    JS_TS_EXTENSIONS,
    make_id,
    make_parent_id,
    count_lines,
    estimate_complexity,
    add_dependency_edge,
    build_stats,
)

from app.parsers.python_parser import (
    extract_python_imports,
    resolve_python_import_to_file_id,
)

from app.parsers.cpp_parser import (
    extract_cpp_includes,
    resolve_cpp_include_to_file_id,
)

from app.parsers.js_parser import (
    extract_js_ts_imports,
    resolve_js_ts_import_to_file_id,
)

def scan_repo(root_path: str) -> dict:
    root = Path(root_path).resolve()

    nodes = []
    edges = []

    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    root_node = {
        "id": ".",
        "name": root.name,
        "type": "folder",
        "parent": None,
    }
    nodes.append(root_node)

    python_files = []
    cpp_files = []
    js_ts_files = []

    for current_dir, dir_names, file_names in os.walk(root):
        dir_names[:] = sorted(
            dirname for dirname in dir_names if dirname not in SKIP_DIRS
        )
        file_names = sorted(file_names)
        current = Path(current_dir)

        for dirname in dir_names:
            folder_path = current / dirname

            folder_node = {
                "id": make_id(folder_path, root),
                "name": folder_path.name,
                "type": "folder",
                "parent": make_parent_id(folder_path, root),
            }
            nodes.append(folder_node)
            
            edges.append(
                {
                    "id": f"contains:{folder_node['parent']}->{folder_node['id']}",
                    "source": folder_node["parent"],
                    "target": folder_node["id"],
                    "type": "contains",
                    "label": "contains",
                }
            )

        for filename in file_names:
            file_path = current / filename
            extension = file_path.suffix.lower()

            if extension in TEXT_EXTENSIONS:
                loc, sloc = count_lines(file_path)
                complexity = estimate_complexity(file_path, extension)
            else:
                loc, sloc, complexity = None, None, None

            if extension in PYTHON_EXTENSIONS:
                python_files.append(file_path)
            elif extension in CPP_EXTENSIONS:
                cpp_files.append(file_path)
            elif extension in JS_TS_EXTENSIONS:
                js_ts_files.append(file_path)

            file_node = {
                "id": make_id(file_path, root),
                "name": file_path.name,
                "type": "file",
                "parent": make_parent_id(file_path, root),
                "extension": extension,
                "size_bytes": file_path.stat().st_size,
                "language": LANGUAGE_BY_EXTENSION.get(extension, "Unknown"),
                "loc": loc,
                "sloc": sloc,
                "complexity": complexity,
                "metrics": {
                    "loc": loc,
                    "sloc": sloc,
                    "complexity": complexity,
                },
            }
            nodes.append(file_node)
            edge = {
                "id": f"contains:{file_node['parent']}->{file_node['id']}",
                "source": file_node["parent"],
                "target": file_node["id"],
                "type": "contains",
                "label": "contains",
            }
            edges.append(edge)

    python_file_ids = set()

    all_file_ids = set()

    for path in python_files:
        file_id = make_id(path, root)
        python_file_ids.add(file_id)
        all_file_ids.add(file_id)
    
    for path in cpp_files:
        all_file_ids.add(make_id(path, root))

    for path in js_ts_files:
        all_file_ids.add(make_id(path, root))

    for node in nodes:
        if node["type"] == "file":
            all_file_ids.add(node["id"])

    seen_dependency_edges: set[tuple[str, str]] = set()

    # python dependencies
    for source_path in python_files:
        source_id = make_id(source_path, root)

        imported_modules = extract_python_imports(source_path)

        for import_info in imported_modules:
            target_id = resolve_python_import_to_file_id(import_info, source_path, root)

            if target_id is None:
                continue

            if target_id in python_file_ids:
                add_dependency_edge(
                    edges,
                    seen_dependency_edges,
                    source_id,
                    target_id,
                )

    # c/cpp dependencies
    for source_path in cpp_files:
        source_id = make_id(source_path, root)

        includes = extract_cpp_includes(source_path)

        for include_info in includes:
            target_id = resolve_cpp_include_to_file_id(
                include_info,
                source_path,
                root,
            )

            if target_id is None:
                continue

            if target_id in all_file_ids:
                add_dependency_edge(
                    edges,
                    seen_dependency_edges,
                    source_id,
                    target_id,
                )
    # js/ts dependencies
    for source_path in js_ts_files:
        source_id = make_id(source_path, root)

        imports = extract_js_ts_imports(source_path)

        for import_path in imports:
            target_id = resolve_js_ts_import_to_file_id(
                import_path,
                source_path,
                root,
            )

            if target_id is None:
                continue

            if target_id in all_file_ids:
                add_dependency_edge(
                    edges,
                    seen_dependency_edges,
                    source_id,
                    target_id,
                )

    annotate_dependency_counts(nodes, edges)

    stats = build_stats(nodes, edges)

    return {
        "root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
        "stats": stats,
    }


def annotate_dependency_counts(nodes: list[dict], edges: list[dict]) -> None:
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}

    for edge in edges:
        if edge["type"] != "depends_on":
            continue

        outgoing[edge["source"]] = outgoing.get(edge["source"], 0) + 1
        incoming[edge["target"]] = incoming.get(edge["target"], 0) + 1

    for node in nodes:
        if node["type"] != "file":
            continue

        node["dependency_count"] = outgoing.get(node["id"], 0)
        node["dependent_count"] = incoming.get(node["id"], 0)
