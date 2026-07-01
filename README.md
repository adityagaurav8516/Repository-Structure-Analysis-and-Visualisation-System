# Repo Atlas

Repo Atlas is a localhost workbench for exploring the structure of a source
repository. It scans a directory that the backend can read, builds a graph of
folders, files, and local dependency edges, then renders that graph in an
interactive React Flow canvas with metrics and optional file summaries.

The current project is a functional local-development prototype. It does not
execute code from scanned repositories.

## Current Capabilities

- Scan any readable local repository path from the browser UI.
- Build folder/file containment edges for the repository tree.
- Resolve local dependency edges for:
  - Python `import` and `from ... import ...` statements.
  - JavaScript and TypeScript `import`, `export ... from`, dynamic `import()`,
    and `require()` calls.
  - C and C++ `#include` statements.
- Skip common generated or dependency directories such as `.git`,
  `node_modules`, `__pycache__`, `dist`, `build`, `coverage`, and virtual
  environments.
- Calculate file-level metrics: file size, lines of code, source lines of code,
  estimated complexity, outgoing dependency count, and incoming dependent count.
- Show repository totals for files, folders, edges, imports, lines of code,
  average estimated complexity, and languages.
- Render the graph with draggable nodes, zoom controls, a minimap, search
  filtering, edge visibility toggles, selection mode, reset view, and an option
  to move child nodes with a parent node.
- Summarize selected file nodes through OpenAI, Gemini, or a local heuristic
  fallback.
- Cache summaries by repository path, file path, provider, prompt version, and
  content hash in `backend/.cache/summary_cache.json`.

## Tech Stack

- Backend: FastAPI, Pydantic, Uvicorn, Pytest.
- Frontend: React, Vite, `@xyflow/react`, ESLint.
- Supported scan targets: mixed-language repositories, with the strongest
  dependency resolution currently available for Python, JavaScript/TypeScript,
  and C/C++.

## Repository Layout

```text
backend/
  main.py                 FastAPI app, CORS, and REST endpoints
  app/scanner.py          Repository walk, node creation, and edge assembly
  app/graph_builder.py    File metrics, graph IDs, stats, and edge helpers
  app/parsers/            Python, JS/TS, and C/C++ dependency parsers
  app/ai_summary.py       Summary provider selection and local fallback
  app/cache.py            Content-hash summary cache
  test_scanner.py         Scanner and summary-cache tests

frontend/
  src/App.jsx             Main React Flow workbench and inspector panel
  src/api.js              Backend API client
  src/graph.js            Filtering, layout, formatting, and edge transforms
  src/App.css             App styling
  package.json            Vite scripts and frontend dependencies
```

## Requirements

- Python 3.11 or newer.
- Node.js 20 or newer.
- A repository path that the backend process can read.
- Optional: an OpenAI or Gemini API key for model-backed summaries.

## Quick Start

Run the backend in one terminal:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL, usually:

```text
http://localhost:5173
```

Enter an absolute repository path, choose a summary provider, and select
`Scan`. Click a file node to open the inspector and request a summary.

## Configuration

Frontend configuration:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

If `VITE_API_BASE_URL` is not set, the frontend defaults to
`http://127.0.0.1:8000`.

Backend summary provider configuration:

```text
AI_PROVIDER=auto
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_CHAT_COMPLETIONS_URL=https://api.openai.com/v1/chat/completions
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-1.5-flash
```

`AI_PROVIDER` can be `auto`, `openai`, `gemini`, or `local`. In `auto` mode,
the backend uses OpenAI when `OPENAI_API_KEY` is present, Gemini when
`GEMINI_API_KEY` is present, and the local heuristic otherwise.

## API

`GET /`

Returns a small status message.

`GET /health`

Returns backend health.

```json
{ "status": "healthy" }
```

`POST /api/scan`

Request:

```json
{ "repo_path": "C:/path/to/repository" }
```

Returns:

- `root`: resolved repository path.
- `generated_at`: UTC timestamp for the scan.
- `nodes`: folder and file nodes.
- `edges`: `contains` and `depends_on` edges.
- `stats`: repository-level counts and language totals.

`POST /api/summarize`

Request:

```json
{
  "repo_path": "C:/path/to/repository",
  "file_id": "src/app.py",
  "provider": "auto"
}
```

Returns the selected file path, summary text, provider, model, content hash,
cache status, creation timestamp, and whether the prompt input was truncated.

## Graph Data Model

Nodes use repository-relative IDs. The root folder is `"."`; a file might be
`"frontend/src/App.jsx"`.

Folder nodes include:

- `id`
- `name`
- `type: "folder"`
- `parent`

File nodes include the folder fields plus:

- `extension`
- `size_bytes`
- `language`
- `loc`
- `sloc`
- `complexity`
- `dependency_count`
- `dependent_count`
- `metrics`

Edges include:

- `type: "contains"` for folder/file hierarchy.
- `type: "depends_on"` for resolved local imports/includes.

## Verification

Backend tests:

```powershell
python -m pytest backend
```

Frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

## Security Notes

Repo Atlas is intended for local use. The backend accepts a raw filesystem path
and can scan any path readable by the backend process. Do not expose this API on
a public network without adding authentication, path allowlists, request limits,
and stronger operational controls.

The summarizer reads selected file contents and may send them to OpenAI or
Gemini when those providers are configured and selected. Use the `local`
provider when file contents must stay fully local.

## Known Limitations

- Dependency detection is best-effort static analysis. It resolves local files,
  not installed package dependencies.
- Python parsing uses the standard AST. JavaScript/TypeScript and C/C++ parsing
  use lightweight regular-expression based detection.
- Complexity is an estimate, not a full static-analysis-grade cyclomatic
  complexity calculation.
- The summarizer previews up to 80 KB of a file; larger files are truncated
  before summarization.
- Very large repositories can create thousands of canvas nodes. Filtering helps,
  but future work could add clustering, paging, or a dedicated layout engine.
- The graph layout is deterministic and depth-based. It is predictable, but it
  can become tall for large or deeply nested repositories.
