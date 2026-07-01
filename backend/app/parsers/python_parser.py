import ast
from pathlib import Path
from app.graph_builder import make_id



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


def resolve_python_import_to_file_id(
    import_info: dict,
    source_path: Path,
    root: Path
) -> str | None:
    module = import_info["module"]
    level = import_info["level"]

    if level == 0:
        base_dirs = get_absolute_import_base_dirs(source_path, root)
    else:
        base_dir = source_path.parent

        for _ in range(level - 1):
            base_dir = base_dir.parent
        base_dirs = [base_dir]

    module_path = module.replace(".", "/")

    for base_dir in base_dirs:
        candidates = [
            base_dir / f"{module_path}.py",
            base_dir / module_path / "__init__.py",
        ]

        for candidate in candidates:
            try:
                candidate = candidate.resolve()
                candidate.relative_to(root.resolve())

                if candidate.exists() and candidate.is_file():
                    return make_id(candidate, root)

            except ValueError:
                continue

    return None


def get_absolute_import_base_dirs(source_path: Path, root: Path) -> list[Path]:
    base_dirs = []
    current = source_path.parent.resolve()
    root = root.resolve()

    while True:
        try:
            current.relative_to(root)
        except ValueError:
            break

        base_dirs.append(current)

        if current == root:
            break

        current = current.parent

    return base_dirs
