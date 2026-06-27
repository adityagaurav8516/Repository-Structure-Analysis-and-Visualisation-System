import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";
import "./App.css";

import { scanRepository, summarizeFile } from "./api";
import {
  createFlowEdges,
  createFlowNodes,
  filterGraph,
  formatBytes,
  formatNumber,
} from "./graph";

const EMPTY_GRAPH = {
  root: "",
  generated_at: "",
  nodes: [],
  edges: [],
  stats: {},
};

const EMPTY_SUMMARY = {
  fileId: "",
  status: "idle",
  data: null,
  error: "",
};

const nodeTypes = {
  repoNode: RepoNode,
};

function App() {
  const [repoPath, setRepoPath] = useState("");
  const [provider, setProvider] = useState("auto");
  const [searchTerm, setSearchTerm] = useState("");
  const [edgeVisibility, setEdgeVisibility] = useState({
    contains: true,
    dependencies: true,
  });
  const [graph, setGraph] = useState(EMPTY_GRAPH);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [summaryState, setSummaryState] = useState(EMPTY_SUMMARY);
  const [scanState, setScanState] = useState({
    loading: false,
    error: "",
  });

  const filteredGraph = useMemo(
    () => filterGraph(graph, searchTerm),
    [graph, searchTerm]
  );
  const flowNodes = useMemo(
    () => createFlowNodes(filteredGraph.nodes),
    [filteredGraph.nodes]
  );
  const flowEdges = useMemo(
    () => createFlowEdges(filteredGraph.edges, edgeVisibility),
    [filteredGraph.edges, edgeVisibility]
  );
  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) || null,
    [graph.nodes, selectedNodeId]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  const requestSummary = useCallback(
    async (node) => {
      if (!node || node.type !== "file") {
        setSummaryState(EMPTY_SUMMARY);
        return;
      }

      setSummaryState({
        fileId: node.id,
        status: "loading",
        data: null,
        error: "",
      });

      try {
        const data = await summarizeFile({
          repoPath: graph.root || repoPath.trim(),
          fileId: node.id,
          provider,
        });

        setSummaryState((current) => {
          if (current.fileId !== node.id) {
            return current;
          }

          return {
            fileId: node.id,
            status: "success",
            data,
            error: "",
          };
        });
      } catch (error) {
        setSummaryState((current) => {
          if (current.fileId !== node.id) {
            return current;
          }

          return {
            fileId: node.id,
            status: "error",
            data: null,
            error: error.message || "Unable to summarize this file",
          };
        });
      }
    },
    [graph.root, provider, repoPath]
  );

  async function handleScan(event) {
    event.preventDefault();

    const nextRepoPath = repoPath.trim();

    if (!nextRepoPath) {
      return;
    }

    setScanState({
      loading: true,
      error: "",
    });
    setSelectedNodeId("");
    setSummaryState(EMPTY_SUMMARY);

    try {
      const data = await scanRepository(nextRepoPath);

      setGraph({
        root: data.root || nextRepoPath,
        generated_at: data.generated_at || "",
        nodes: data.nodes || [],
        edges: data.edges || [],
        stats: data.stats || {},
      });
    } catch (error) {
      setScanState({
        loading: false,
        error: error.message || "Unable to scan repository",
      });
      return;
    }

    setScanState({
      loading: false,
      error: "",
    });
  }

  const handleNodeClick = useCallback(
    (_, flowNode) => {
      const rawNode = flowNode.data.node;

      setSelectedNodeId(rawNode.id);
      requestSummary(rawNode);
    },
    [requestSummary]
  );

  function toggleEdgeVisibility(key) {
    setEdgeVisibility((current) => ({
      ...current,
      [key]: !current[key],
    }));
  }

  const hasGraph = graph.nodes.length > 0;

  return (
    <div className="workspace">
      <aside className="control-panel" aria-label="Repository controls">
        <div className="brand-block">
          <p className="eyebrow">Repository Map</p>
          <h1>Repo Atlas</h1>
        </div>

        <form className="scan-form" onSubmit={handleScan}>
          <label htmlFor="repo-path">Repository path</label>
          <input
            id="repo-path"
            value={repoPath}
            onChange={(event) => setRepoPath(event.target.value)}
            placeholder="C:\path\to\repository"
          />

          <label htmlFor="provider">AI provider</label>
          <select
            id="provider"
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
          >
            <option value="auto">Auto</option>
            <option value="local">Local heuristic</option>
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini</option>
          </select>

          <button type="submit" disabled={scanState.loading || !repoPath.trim()}>
            {scanState.loading ? "Scanning" : "Scan"}
          </button>
        </form>

        {scanState.error && <p className="error-banner">{scanState.error}</p>}

        <section className="panel-section">
          <div className="section-heading">
            <h2>Overview</h2>
          </div>
          <div className="stat-grid">
            <Stat label="Files" value={graph.stats.files} />
            <Stat label="Folders" value={graph.stats.folders} />
            <Stat label="Imports" value={graph.stats.dependency_edges} />
            <Stat label="LoC" value={graph.stats.total_loc} />
            <Stat label="Avg complexity" value={graph.stats.average_complexity} />
            <Stat label="Edges" value={graph.stats.edges} />
          </div>
        </section>

        <section className="panel-section">
          <div className="section-heading">
            <h2>View</h2>
          </div>
          <label htmlFor="search">Filter</label>
          <input
            id="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="file, folder, language"
          />
          <div className="toggle-stack">
            <label className="toggle">
              <input
                type="checkbox"
                checked={edgeVisibility.dependencies}
                onChange={() => toggleEdgeVisibility("dependencies")}
              />
              <span>Dependency edges</span>
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={edgeVisibility.contains}
                onChange={() => toggleEdgeVisibility("contains")}
              />
              <span>Folder edges</span>
            </label>
          </div>
        </section>

        {hasGraph && (
          <section className="panel-section">
            <div className="section-heading">
              <h2>Languages</h2>
            </div>
            <LanguageList languages={graph.stats.languages} />
          </section>
        )}
      </aside>

      <main className="flow-shell">
        <div className="canvas-header">
          <div>
            <p className="eyebrow">Canvas</p>
            <h2>{graph.root || "No repository loaded"}</h2>
          </div>
          <div className="canvas-counts">
            <span>{formatNumber(filteredGraph.nodes.length)} nodes</span>
            <span>{formatNumber(flowEdges.length)} visible edges</span>
          </div>
        </div>

        <div className="flow-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            fitView
            minZoom={0.12}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={22} size={1} />
            <Controls position="bottom-left" />
            <MiniMap
              nodeStrokeWidth={3}
              pannable
              zoomable
              position="bottom-right"
            />
          </ReactFlow>
        </div>
      </main>

      <Inspector
        node={selectedNode}
        summaryState={summaryState}
        onRefresh={() => requestSummary(selectedNode)}
      />
    </div>
  );
}

function RepoNode({ data, selected }) {
  const node = data.node;
  const isFile = node.type === "file";
  const complexityLabel =
    typeof node.complexity === "number" ? `C${node.complexity}` : "C-";

  return (
    <div className={`repo-flow-node ${node.type} ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-topline">
        <span className="node-type">{isFile ? node.language || "File" : "Folder"}</span>
        {isFile && <span className="node-complexity">{complexityLabel}</span>}
      </div>
      <strong title={node.id}>{node.name}</strong>
      {isFile ? (
        <div className="node-metrics">
          <span>{formatNumber(node.loc)} LoC</span>
          <span>{formatNumber(node.dependency_count)} out</span>
          <span>{formatNumber(node.dependent_count)} in</span>
        </div>
      ) : (
        <span className="node-path">{node.id === "." ? "root" : node.id}</span>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function Inspector({ node, summaryState, onRefresh }) {
  if (!node) {
    return (
      <aside className="inspector" aria-label="Inspector">
        <div className="inspector-empty">
          <p className="eyebrow">Inspector</p>
          <h2>No node selected</h2>
        </div>
      </aside>
    );
  }

  return (
    <aside className="inspector" aria-label="Inspector">
      <div className="inspector-heading">
        <p className="eyebrow">{node.type}</p>
        <h2 title={node.id}>{node.name}</h2>
      </div>

      <dl className="detail-list">
        <Detail label="Path" value={node.id} />
        <Detail label="Language" value={node.language || "Folder"} />
        <Detail label="Size" value={formatBytes(node.size_bytes)} />
        <Detail label="LoC" value={formatNumber(node.loc)} />
        <Detail label="Complexity" value={formatNumber(node.complexity)} />
        <Detail label="Imports out" value={formatNumber(node.dependency_count)} />
        <Detail label="Imports in" value={formatNumber(node.dependent_count)} />
      </dl>

      {node.type === "file" && (
        <section className="summary-section">
          <div className="summary-title-row">
            <h2>Summary</h2>
            <button
              className="secondary-button"
              type="button"
              onClick={onRefresh}
              disabled={summaryState.status === "loading"}
            >
              Refresh
            </button>
          </div>
          <SummaryBody summaryState={summaryState} />
        </section>
      )}
    </aside>
  );
}

function SummaryBody({ summaryState }) {
  if (summaryState.status === "loading") {
    return <p className="summary-copy muted">Summarizing...</p>;
  }

  if (summaryState.status === "error") {
    return <p className="summary-copy error-text">{summaryState.error}</p>;
  }

  if (summaryState.status === "success") {
    return (
      <div className="summary-copy">
        <p>{summaryState.data.summary}</p>
        <div className="summary-meta">
          <span>{summaryState.data.provider}</span>
          <span>{summaryState.data.model}</span>
          <span>{summaryState.data.cached ? "cached" : "fresh"}</span>
        </div>
      </div>
    );
  }

  return <p className="summary-copy muted">Ready</p>;
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{formatNumber(value)}</strong>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function LanguageList({ languages = {} }) {
  const entries = Object.entries(languages).sort((a, b) => b[1] - a[1]);

  if (entries.length === 0) {
    return <p className="muted">No language data</p>;
  }

  return (
    <div className="language-list">
      {entries.slice(0, 7).map(([language, count]) => (
        <div className="language-row" key={language}>
          <span>{language}</span>
          <strong>{formatNumber(count)}</strong>
        </div>
      ))}
    </div>
  );
}

export default App;
