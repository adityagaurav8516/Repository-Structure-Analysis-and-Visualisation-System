import ast
import os
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
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".cpp": "C++",
    ".hpp": "C++ Header",
    ".c": "C",
    ".h": "C Header",
    ".java": "Java",
}
TEXT_EXTENSIONS = set(LANGUAGE_BY_EXTENSION.keys())


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
    dependecy_edges = 0
    for edge in edges:
        if edge["type"] == "depends_on":
            dependecy_edges += 1
    return {
        "files": file_count,
        "folders": folder_count,
        "edges": len(edges),
        "total_loc": total_loc,
        "total_sloc": total_sloc,
        "languages": languages,
        "dependency_edges": dependecy_edges,
    }


def extract_python_imports(path: Path) -> list[dict]:
    imports = []

    text = path.read_text(encoding="utf-8", errors="ignore")

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "module": alias.name,
                        "level": 0,
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imports.append(
                    {
                        "module": node.module,
                        "level": node.level,
                    }
                )

    return imports
    # for line in text.splitlines():
    #     line = line.strip()
    #     if line.startswith("import "):
    #         module = line.replace("import ","").split()[0]
    #         imports.append(module)

    #     elif line.startswith("from "):
    #         parts = line.split()
    #         if len(parts) >=2:
    #             module = parts[1]
    #             imports.append(module)

    # return imports


def resolve_module_to_file_id(
    import_info: dict, source_path: Path, root: Path
) -> str | None:
    module = import_info["module"]
    level = import_info["level"]

    if level == 0:
        return module.replace(".", "/")
    current_dir = source_path.parent
    for _ in range(level - 1):
        current_dir = current_dir.parent

    target_path = current_dir / module.replace(".", "/")
    target_path = target_path.with_suffix(".py")

    try:
        return make_id(target_path, root)
    except ValueError:
        return None


def scan_repo(root_path: str):
    root = Path(root_path).resolve()

    nodes = []
    edges = []

    if not root.exists():
        raise FileNotFoundError("...")

    if not root.is_dir():
        raise NotADirectoryError("...")

    root_node = {"id": ".", "name": root.name, "type": "folder", "parent": None}
    nodes.append(root_node)

    python_files = []

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
            edge = {
                "source": folder_node["parent"],
                "target": folder_node["id"],
                "type": "contains",
            }
            edges.append(edge)

        for filename in file_names:
            file_path = current / filename
            extension = file_path.suffix.lower()

            if extension in TEXT_EXTENSIONS:
                loc, sloc = count_lines(file_path)
            else:
                loc, sloc = None, None

            if extension == ".py":
                python_files.append(file_path)

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
            }
            nodes.append(file_node)
            edge = {
                "id": f"contains:{file_node['parent']}->{file_node['id']}",
                "source": file_node["parent"],
                "target": file_node["id"],
                "type": "contains",
            }
            edges.append(edge)

    python_file_ids = set()

    for path in python_files:
        python_file_ids.add(make_id(path, root))

    seen_dependency_edges = set()

    for source_path in python_files:
        source_id = make_id(source_path, root)

        imported_modules = extract_python_imports(source_path)

        for import_info in imported_modules:
            target_id = resolve_module_to_file_id(import_info, source_path, root)

            if target_id is None:
                continue

            if target_id in python_file_ids:
                edge_key = (source_id, target_id)

                if edge_key in seen_dependency_edges:
                    continue
                seen_dependency_edges.add(edge_key)
                edge = {
                    "id": f"depends:{source_id}->{target_id}",
                    "source": source_id,
                    "target": target_id,
                    "type": "depends_on",
                }
                edges.append(edge)

    stats = build_stats(nodes, edges)

    return {"nodes": nodes, "edges": edges, "stats": stats}


if __name__ == "__main__":
    graph = scan_repo("../..")

    print("nodes:", len(graph["nodes"]))
    print("edges:", len(graph["edges"]))
    print("dependency edges:", graph["stats"]["dependency_edges"])
    # print(extract_python_imports(Path("scanner.py")))
