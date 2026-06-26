import re
from pathlib import Path

from app.graph_builder import path_to_id_if_inside_root


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
