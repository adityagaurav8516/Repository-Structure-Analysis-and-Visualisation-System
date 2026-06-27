from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.cache import SummaryCache


MAX_FILE_BYTES_FOR_PROMPT = 80_000
PROMPT_VERSION = "file-summary-v1"
SUPPORTED_PROVIDERS = {"auto", "openai", "gemini", "local"}


class SummaryConfigurationError(RuntimeError):
    pass


class SummaryProviderError(RuntimeError):
    pass


def summarize_file(
    *,
    repo_path: str,
    file_id: str,
    provider: str = "auto",
    cache: SummaryCache | None = None,
) -> dict[str, Any]:
    root = Path(repo_path).resolve()
    target_path = resolve_repo_file(root, file_id)
    content_hash = hash_file(target_path)
    text, truncated = read_text_preview(target_path)
    selected_provider = choose_provider(provider)

    cache = cache or SummaryCache()
    cached = cache.get(
        root=root,
        file_id=file_id,
        content_hash=content_hash,
        provider=selected_provider,
        prompt_version=PROMPT_VERSION,
    )

    if cached:
        return {
            **cached,
            "path": str(target_path),
            "truncated": truncated,
        }

    if selected_provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        summary = summarize_with_openai(file_id=file_id, text=text, model=model)
    elif selected_provider == "gemini":
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        summary = summarize_with_gemini(file_id=file_id, text=text, model=model)
    else:
        model = "local-heuristic"
        summary = summarize_locally(file_id=file_id, text=text)

    record = cache.set(
        root=root,
        file_id=file_id,
        content_hash=content_hash,
        provider=selected_provider,
        model=model,
        prompt_version=PROMPT_VERSION,
        summary=summary,
    )

    return {
        **record,
        "path": str(target_path),
        "truncated": truncated,
    }


def resolve_repo_file(root: Path, file_id: str) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    if file_id == "." or Path(file_id).is_absolute():
        raise ValueError("file_id must be a repository-relative file path")

    target_path = (root / file_id).resolve()

    try:
        target_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("file_id must stay inside the repository root") from exc

    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(f"File does not exist: {file_id}")

    return target_path


def choose_provider(requested_provider: str) -> str:
    provider = (requested_provider or "auto").lower()

    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            "provider must be one of: auto, openai, gemini, local"
        )

    if provider == "auto":
        configured_provider = os.getenv("AI_PROVIDER", "auto").lower()

        if configured_provider in {"openai", "gemini", "local"}:
            provider = configured_provider

    if provider == "auto":
        if os.getenv("OPENAI_API_KEY"):
            return "openai"

        if os.getenv("GEMINI_API_KEY"):
            return "gemini"

        return "local"

    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise SummaryConfigurationError("OPENAI_API_KEY is not configured")

    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        raise SummaryConfigurationError("GEMINI_API_KEY is not configured")

    return provider


def hash_file(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def read_text_preview(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    truncated = len(raw) > MAX_FILE_BYTES_FOR_PROMPT

    if truncated:
        raw = raw[:MAX_FILE_BYTES_FOR_PROMPT]

    return raw.decode("utf-8", errors="ignore"), truncated


def summarize_with_openai(*, file_id: str, text: str, model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise SummaryConfigurationError("OPENAI_API_KEY is not configured")

    url = os.getenv(
        "OPENAI_CHAT_COMPLETIONS_URL",
        "https://api.openai.com/v1/chat/completions",
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "You explain source files to developers in plain language.",
            },
            {
                "role": "user",
                "content": build_prompt(file_id=file_id, text=text),
            },
        ],
    }
    data = post_json(
        url,
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SummaryProviderError("OpenAI response did not include a summary") from exc


def summarize_with_gemini(*, file_id: str, text: str, model: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise SummaryConfigurationError("GEMINI_API_KEY is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": build_prompt(file_id=file_id, text=text)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 180,
        },
    }
    data = post_json(url, payload)

    try:
        parts = data["candidates"][0]["content"]["parts"]
        return " ".join(part["text"] for part in parts if "text" in part).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SummaryProviderError("Gemini response did not include a summary") from exc


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Content-Type": "application/json",
        **(headers or {}),
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise SummaryProviderError(
            f"AI provider returned HTTP {exc.code}: {error_body[:300]}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SummaryProviderError(f"AI provider request failed: {exc}") from exc


def build_prompt(*, file_id: str, text: str) -> str:
    return (
        "Explain what this code does in 3 simple sentences.\n"
        f"File path: {file_id}\n\n"
        "Code:\n"
        f"```\n{text}\n```"
    )


def summarize_locally(*, file_id: str, text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    definitions = extract_definition_names(text)
    imports = extract_import_names(text)

    first_sentence = (
        f"{file_id} is a source file with {len(lines)} non-empty lines."
    )

    if definitions:
        second_sentence = (
            "It defines "
            + ", ".join(definitions[:4])
            + (" and related helpers." if len(definitions) > 4 else ".")
        )
    else:
        second_sentence = "It mostly contains configuration, data, markup, or styling."

    if imports:
        third_sentence = (
            "It depends on "
            + ", ".join(imports[:4])
            + (" and other modules." if len(imports) > 4 else ".")
        )
    else:
        third_sentence = "No direct imports were detected in the previewed content."

    return " ".join([first_sentence, second_sentence, third_sentence])


def extract_definition_names(text: str) -> list[str]:
    patterns = [
        r"^\s*(?:async\s+)?def\s+([A-Za-z_][\w]*)",
        r"^\s*class\s+([A-Za-z_][\w]*)",
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w]*)",
        r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][\w]*)\s*=",
    ]
    names: list[str] = []

    for pattern in patterns:
        names.extend(re.findall(pattern, text, flags=re.MULTILINE))

    return list(dict.fromkeys(names))


def extract_import_names(text: str) -> list[str]:
    patterns = [
        r"^\s*import\s+([\w.]+)",
        r"^\s*from\s+([\w.]+)\s+import",
        r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]",
        r"from\s+[\"']([^\"']+)[\"']",
        r"require\([\"']([^\"']+)[\"']\)",
    ]
    names: list[str] = []

    for pattern in patterns:
        names.extend(re.findall(pattern, text, flags=re.MULTILINE))

    return list(dict.fromkeys(names))
