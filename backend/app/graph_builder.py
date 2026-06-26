from pathlib import Path


SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",

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
PYTHON_EXTENSIONS = {
    ".py",
    ".pyw",
    ".pyi",
}
CPP_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cxx",
    ".h", ".hh", ".hpp", ".hxx",
}
JS_TS_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx",
    ".mjs", ".cjs", ".mts", ".cts",
}


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
    loc = len(lines)
    sloc = len([line for line in lines if line.strip()])

    return loc, sloc


def build_stats(nodes: list, edges: list) -> dict:
    file_count = 0
    folder_count = 0
    total_loc = 0
    total_sloc = 0
    languages = {}

    for node in nodes:
        if node["type"] == "file":
            file_count += 1

            total_loc += node.get("loc") or 0
            total_sloc += node.get("sloc") or 0

            language = node.get("language", "Unknown")

            if language not in languages:
                languages[language] = 0

            languages[language] += 1

        elif node["type"] == "folder":
            folder_count += 1
    dependency_edges = 0
    contains_edges = 0
    for edge in edges:
        if edge["type"] == "depends_on":
            dependency_edges += 1
        elif edge["type"] == "contains":
            contains_edges += 1
            
    return {
        "files": file_count,
        "folders": folder_count,
        "edges": len(edges),
        "contains_edges": contains_edges,
        "dependency_edges": dependency_edges,
        "total_loc": total_loc,
        "total_sloc": total_sloc,
        "languages": languages,
    }


def path_to_id_if_inside_root(path: Path, root: Path) -> str | None:
    try:
        path = path.resolve()
        root = root.resolve()

        path.relative_to(root)

        if path.exists() and path.is_file():
            return make_id(path, root)

        return None

    except ValueError:
        return None


def add_dependency_edge(
    edges: list,
    seen_dependency_edges: set,
    source_id: str,
    target_id: str,
    ):
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
        }
    )
