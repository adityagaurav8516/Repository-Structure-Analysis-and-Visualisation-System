import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function getNodeColor(type) {
  if (type === "folder") return "#2563eb";
  if (type === "file") return "#16a34a";
  return "#6b7280";
}

function transformToReactFlowNodes(rawNodes) {
  return rawNodes.map((node, index) => {
    const depth = node.id === "." ? 0 : node.id.split("/").length;

    return {
      id: node.id,
      position: {
        x: depth * 260,
        y: index * 90,
      },
      data: {
        label: (
          <div className="repo-node">
            <strong>{node.name}</strong>
            <span>{node.type}</span>
            {node.language && <span>{node.language}</span>}
            {typeof node.lines === "number" && <span>{node.lines} lines</span>}
          </div>
        ),
      },
      style: {
        border: `2px solid ${getNodeColor(node.type)}`,
        borderRadius: 10,
        padding: 10,
        width: 180,
        background: "#ffffff",
      },
    };
  });
}

function transformToReactFlowEdges(rawEdges) {
  return rawEdges.map((edge, index) => ({
    id: edge.id || `edge-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.type || "",
    animated: edge.type === "dependency",
  }));
}

function App() {
  const [repoPath, setRepoPath] = useState("");
  const [rawGraph, setRawGraph] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const initialNodes = useMemo(
    () => transformToReactFlowNodes(rawGraph.nodes),
    [rawGraph.nodes]
  );

  const initialEdges = useMemo(
    () => transformToReactFlowEdges(rawGraph.edges),
    [rawGraph.edges]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  async function scanRepo() {
    setLoading(true);
    setError("");
  
    try {
      const response = await fetch(`${API_BASE_URL}/api/scan`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repo_path: repoPath,
        }),
      });
  
      const contentType = response.headers.get("content-type");
  
      if (!contentType || !contentType.includes("application/json")) {
        const text = await response.text();
        throw new Error(
          `Expected JSON but got HTML/text. First 100 chars: ${text.slice(0, 100)}`
        );
      }
  
      const data = await response.json();
  
      if (!response.ok) {
        throw new Error(data.detail || `Backend error: ${response.status}`);
      }
  
      setRawGraph({
        nodes: data.nodes || [],
        edges: data.edges || [],
      });
    } catch (err) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Repo Visualizer</h1>

        <input
          value={repoPath}
          onChange={(e) => setRepoPath(e.target.value)}
          placeholder="Enter repo path"
        />

        <button onClick={scanRepo} disabled={loading || !repoPath.trim()}>
          {loading ? "Scanning..." : "Scan Repo"}
        </button>

        {error && <p className="error">{error}</p>}

        <div className="stats">
          <p><strong>Nodes:</strong> {rawGraph.nodes.length}</p>
          <p><strong>Edges:</strong> {rawGraph.edges.length}</p>
        </div>
      </aside>

      <main className="canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </main>
    </div>
  );
}

export default App;