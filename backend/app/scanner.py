import json
import ast
import os
import re
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
                for alias in node.names:
                    imports.append(
                        {
                            "module": f"{node.module}.{alias.name}",
                            "level": node.level,
                        }
                    )
            else:
                for alias in node.names:
                    imports.append(
                        {
                            "module": alias.name,
                            "level": node.level,
                        }
                    )

    return imports


def resolve_module_to_file_id(
    import_info: dict,
    source_path: Path,
    root: Path
) -> str | None:
    module = import_info["module"]
    level = import_info["level"]

    # Decide base directory
    if level == 0:
        base_dir = root
    else:
        base_dir = source_path.parent

        for _ in range(level - 1):
            base_dir = base_dir.parent

    module_path = module.replace(".", "/")

    candidates = [
        base_dir / f"{module_path}.py",
        base_dir / module_path / "__init__.py",
    ]

    for candidate in candidates:
        try:
            candidate = candidate.resolve()

            if candidate.exists() and candidate.is_file():
                return make_id(candidate, root)

        except ValueError:
            continue

    return None


CPP_INCLUDE_RE = re.compile(
    r'^\s*#\s*include\s*([<"])([^>"]+)[>"]',
    re.MULTILINE,
)
def extract_cpp_includes(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")

    includes = []

    for match in CPP_INCLUDE_RE.finditer(text):
        bracket = match.group(1)
        include_path = match.group(2)

        includes.append(
            {
                "path": include_path,
                "is_quoted": bracket == '"',
            }
        )

    return includes

JS_IMPORT_RE = re.compile(
    r"""
    (?:
        import\s+(?:type\s+)?(?:[^'"]*?\s+from\s+)? |
        export\s+(?:type\s+)?[^'"]*?\s+from\s+ |
        require\s*\( |
        import\s*\(
    )
    ['"]([^'"]+)['"]
    """,
    re.VERBOSE,
)
def extract_js_ts_imports(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")

    imports = []

    for match in JS_IMPORT_RE.finditer(text):
        imports.append(match.group(1))

    return imports


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


CPP_HEADER_EXTENSIONS = [".h", ".hh", ".hpp", ".hxx"]
def resolve_cpp_include_to_file_id(
    include_info: dict,
    source_path: Path,
    root: Path,
    ) -> str | None:
    include_path = include_info["path"]
    is_quoted = include_info["is_quoted"]

    current_dir = source_path.parent

    candidates = []

    # #include "x.hpp" usually means relative to current file.
    if is_quoted:
        candidates.append(current_dir / include_path)

    # Allow project-root style includes.
    candidates.append(root / include_path)

    # Common C/C++ project layouts.
    candidates.append(root / "include" / include_path)
    candidates.append(root / "src" / include_path)

    raw = Path(include_path)

    # If extension is omitted, try header extensions.
    if raw.suffix == "":
        extra_candidates = []

        for candidate in candidates:
            for ext in CPP_HEADER_EXTENSIONS:
                extra_candidates.append(Path(str(candidate) + ext))

        candidates.extend(extra_candidates)

    for candidate in candidates:
        target_id = path_to_id_if_inside_root(candidate, root)

        if target_id is not None:
            return target_id

    return None

JS_TS_RESOLVE_EXTENSIONS = [
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".mts",
    ".cts",
    ".json",
    ".css",
]
def resolve_js_ts_import_to_file_id(
    import_path: str,
    source_path: Path,
    root: Path,
    ) -> str | None:
    # Ignore packages like react, express, lodash.
    if not import_path.startswith("."):
        return None

    # Handles imports like "./x?raw" used by some bundlers.
    import_path = import_path.split("?")[0].split("#")[0]

    current_dir = source_path.parent
    base = (current_dir / import_path).resolve()

    candidates = []

    # Exact path: ./style.css
    candidates.append(base)

    # Extensionless import: ./Button -> ./Button.tsx, etc.
    if base.suffix == "":
        for ext in JS_TS_RESOLVE_EXTENSIONS:
            candidates.append(Path(str(base) + ext))

        # Folder import: ./components/Button -> ./components/Button/index.tsx
        for ext in JS_TS_RESOLVE_EXTENSIONS:
            candidates.append(base / f"index{ext}")

    for candidate in candidates:
        target_id = path_to_id_if_inside_root(candidate, root)

        if target_id is not None:
            return target_id

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
            if extension in CPP_EXTENSIONS:
                cpp_files.append(file_path)
            if extension in JS_TS_EXTENSIONS:
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
    cpp_file_ids = set()
    js_ts_file_ids = set()
    all_file_ids = set()

    for path in python_files:
        file_id = make_id(path, root)
        python_file_ids.add(file_id)
        all_file_ids.add(file_id)
    
    for path in cpp_files:
        file_id = make_id(path, root)
        cpp_file_ids.add(file_id)
        all_file_ids.add(file_id)
    
    for path in js_ts_files:
        file_id = make_id(path, root)
        js_ts_file_ids.add(file_id)
        all_file_ids.add(file_id)

    for node in nodes:
        if node["type"] == "file":
            all_file_ids.add(node["id"])

    seen_dependency_edges = set()


    # python dependencies
    for source_path in python_files:
        source_id = make_id(source_path, root)

        imported_modules = extract_python_imports(source_path)

        for import_info in imported_modules:
            target_id = resolve_module_to_file_id(import_info, source_path, root)

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
    

    stats = build_stats(nodes, edges)

    return {"nodes": nodes, "edges": edges, "stats": stats}



if __name__ == "__main__":
    graph = scan_repo(r"C:/Users/adity/desktop/test_repo")

    print("nodes:", len(graph["nodes"]))
    print("edges:", len(graph["edges"]))
    print("dependency edges:", graph["stats"]["dependency_edges"])

    print("\ndependency edges:")
    for edge in graph["edges"]:
        if edge["type"] == "depends_on":
            print(f"{edge['source']} -> {edge['target']}")

    with open("graph.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
