import re
from pathlib import Path

from app.graph_builder import path_to_id_if_inside_root


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