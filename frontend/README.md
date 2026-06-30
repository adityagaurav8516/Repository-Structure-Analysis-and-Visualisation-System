# Frontend

React + Vite + React Flow interface for the repository visualiser.

## Run

```powershell
npm install
npm run dev
```

The app expects the backend API at `VITE_API_BASE_URL`, defaulting to `http://127.0.0.1:8000`.

## Notes

- Nodes are draggable and can be rearranged directly on the canvas.
- File nodes request summaries from the backend when clicked.
- Complexity values shown in the UI are estimated metrics, not full static-analysis-grade cyclomatic complexity.
