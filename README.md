# REPO ATLAS - Repository Structure Analysis and Visualisation System

An interactive developer tool for scanning a local repository, extracting folder/file relationships, detecting internal imports, displaying code metrics, and summarizing individual files with AI.

## Features

- FastAPI backend that scans local repositories without running the target code.
- Dependency detection for Python imports, JavaScript/TypeScript imports, and C/C++ includes.
- Metrics per file: lines of code, source lines of code, file size, dependency counts, and estimated complexity.
- React + React Flow frontend with draggable nodes, zooming, filtering, minimap, and dependency/folder edge toggles.
- File inspector panel that requests a short AI summary when a file node is clicked.
- Local summary cache keyed by repository path, file path, provider, prompt version, and content hash.
- Local heuristic summary fallback when no AI API key is configured.

## Project Structure

```text
backend/
  main.py                 FastAPI app and REST endpoints
  app/scanner.py          Repository traversal and graph assembly
  app/graph_builder.py    Metrics, IDs, stats, and edge helpers
  app/parsers/            Python, JS/TS, and C/C++ dependency parsers
  app/ai_summary.py       AI provider middleware and local fallback
  app/cache.py            Content-hash summary cache
frontend/
  src/App.jsx             React Flow workbench and inspector
  src/api.js              Backend API client
  src/graph.js            Graph filtering and React Flow transforms
```

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- A local repository path that the backend process can read

## Backend Setup

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The API will be available at:

```text
http://127.0.0.1:8000
```

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

The app will be available at:

```text
http://localhost:5173
```

## Environment Variables

The frontend uses:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

For real AI summaries, configure one provider in the backend environment:

```text
AI_PROVIDER=auto
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
```

If no AI key is configured, the backend uses the local heuristic summary provider.

See [backend/.env.example](backend/.env.example) and [frontend/.env.example](frontend/.env.example).

## API Endpoints

- `GET /health` returns backend health.
- `POST /api/scan` accepts `{ "repo_path": "C:/path/to/repo" }` and returns graph nodes, edges, and stats.
- `POST /api/summarize` accepts `{ "repo_path": "...", "file_id": "src/app.py", "provider": "auto" }` and returns a cached or fresh summary.

## Security Note

The repository path is currently a raw text field. This is intended for localhost development and demos only. The backend can scan any filesystem path that the backend process can read, so do not expose this API publicly without adding path allowlists, authentication, and request limits.

## Known Limitations

- Complexity is estimated. Python uses AST traversal, while JavaScript/TypeScript and C/C++ use a lightweight token heuristic rather than full language ASTs.
- Very large repositories can produce thousands of React Flow nodes. Use the filter controls for large graphs; future versions could add clustering, pagination, or a dedicated layout engine.
- Node layout is depth/lane based, which is predictable but can become tall for huge monorepos.

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
