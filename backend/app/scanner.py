from pathlib import Path
import os

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

def make_id (path: Path, root: Path)->str:
    relative_path = path.relative_to(root)

    if str(relative_path) == ".":
        return "."

    return relative_path.as_posix()
def make_parent_id(path:Path,root:Path)->str:
    parent = path.parent

    if parent == root:
        return "."

    return parent.relative_to(root).as_posix()

def count_lines (path:Path) -> tuple[int,int]:
    text = path.read_text(encoding="utf-8", errors = "ignore")

    lines = text.splitlines()
    loc = len(lines)
    sloc = len([line for line in lines if line.strip()])

    return loc,sloc

def scan_repo (root_path:str):
    root = Path(root_path).resolve()

    nodes = []
    edges = []

    if not root.exists():
        raise FileNotFoundError("...")
        
    if not root.is_dir():
        raise NotADirectoryError("...")     

    root_node = {
        "id":".",
        "name": root.name,
        "type": "folder",
        "parent":None 
    }
    nodes.append(root_node)

    for current_dir, dir_names, file_names in os.walk(root):
        dir_names[:] = sorted(
            dirname for dirname in dir_names
            if dirname not in SKIP_DIRS
        )
        file_names = sorted(file_names)
        
        current = Path(current_dir)
        for dirname in dir_names:
            folder_path = current /dirname

            folder_node = {
                "id":make_id(folder_path,root),
                "name": folder_path.name,
                "type": "folder",
                "parent": make_parent_id(folder_path,root)
            }
            nodes.append(folder_node)
            edge = {
                "source":folder_node["parent"],
                "target":folder_node["id"],
                "type":"contains",
            }
            edges.append(edge)

        for filename in file_names:
            file_path = current / filename
            
            loc, sloc = count_lines(file_path)
            
            file_node = {
                "id":make_id(file_path,root),
                "name":file_path.name,
                "type":"file",
                "parent": make_parent_id(file_path,root),
                "extension": file_path.suffix,
                "size_bytes": file_path.stat().st_size,
                "language": LANGUAGE_BY_EXTENSION.get(file_path.suffix.lower(), "Unknown"),
                "loc": loc,
                "sloc": sloc,
            }
            nodes.append(file_node)
            edge = {
                "source":file_node["parent"],
                "target":file_node["id"],
                "type":"contains"
            }
            edges.append(edge)
    return {
        "nodes": nodes,
        "edges": edges,
    }


print(scan_repo("."))
