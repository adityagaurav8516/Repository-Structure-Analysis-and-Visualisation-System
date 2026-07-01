import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  ControlButton,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  SelectionMode,
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
  const [canvasMode, setCanvasMode] = useState("pan");
  const [moveChildrenWithParent, setMoveChildrenWithParent] = useState(false);
  const [edgeVisibility, setEdgeVisibility] = useState({
    contains: true,
    dependencies: true,
  });
  const [graph, setGraph] = useState(EMPTY_GRAPH);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [selectedFlowNodeIds, setSelectedFlowNodeIds] = useState([]);
  const [summaryState, setSummaryState] = useState(EMPTY_SUMMARY);
  const [scanState, setScanState] = useState({
    loading: false,
    error: "",
  });
  const subtreeDragRef = useRef(null);
  const flowInstanceRef = useRef(null);

  const filteredGraph = useMemo(
    () => filterGraph(graph, searchTerm),
    [graph, searchTerm]
  );
  const childrenByParentId = useMemo(
    () => createChildrenByParentId(filteredGraph.nodes),
    [filteredGraph.nodes]
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
  const hasGraph = graph.nodes.length > 0;
  const isLargeGraph = graph.nodes.length >= 2000;
  const isSelectionMode = canvasMode === "select";

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    setNodes(flowNodes);
  }, [flowNodes, setNodes]);

  useEffect(() => {
    setEdges(flowEdges);
  }, [flowEdges, setEdges]);

  const clearInspector = useCallback(() => {
    setSelectedNodeId("");
    setSummaryState(EMPTY_SUMMARY);
  }, []);

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
    clearInspector();
    setSelectedFlowNodeIds([]);

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
    (event, flowNode) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey) {
        clearInspector();
        return;
      }

      const rawNode = flowNode.data.node;

      setSelectedNodeId(rawNode.id);
      requestSummary(rawNode);
    },
    [clearInspector, requestSummary]
  );

  const handleSelectionChange = useCallback(
    ({ nodes: selectedNodes }) => {
      const selectedIds = selectedNodes.map((node) => node.id);

      setSelectedFlowNodeIds(selectedIds);

      if (
        selectedNodeId &&
        (selectedIds.length !== 1 || selectedIds[0] !== selectedNodeId)
      ) {
        clearInspector();
      }
    },
    [clearInspector, selectedNodeId]
  );

  const handleWorkspacePointerDown = useCallback(
    (event) => {
      if (
        event.target.closest(".react-flow__node") ||
        event.target.closest(".inspector")
      ) {
        return;
      }

      clearInspector();
    },
    [clearInspector]
  );

  const handleNodeDragStart = useCallback(
    (_, flowNode) => {
      if (!moveChildrenWithParent) {
        subtreeDragRef.current = null;
        return;
      }

      const descendantIds = getDescendantIds(flowNode.id, childrenByParentId);

      if (descendantIds.size === 0) {
        subtreeDragRef.current = null;
        return;
      }

      const descendantPositions = new Map();

      for (const node of nodes) {
        if (descendantIds.has(node.id)) {
          descendantPositions.set(node.id, { ...node.position });
        }
      }

      if (descendantPositions.size === 0) {
        subtreeDragRef.current = null;
        return;
      }

      subtreeDragRef.current = {
        nodeId: flowNode.id,
        origin: { ...flowNode.position },
        descendantPositions,
      };
    },
    [childrenByParentId, moveChildrenWithParent, nodes]
  );

  const handleNodeDrag = useCallback(
    (_, flowNode) => {
      const dragState = subtreeDragRef.current;

      if (!dragState || dragState.nodeId !== flowNode.id) {
        return;
      }

      const dx = flowNode.position.x - dragState.origin.x;
      const dy = flowNode.position.y - dragState.origin.y;

      if (dx === 0 && dy === 0) {
        return;
      }

      setNodes((currentNodes) =>
        currentNodes.map((node) => {
          const startPosition = dragState.descendantPositions.get(node.id);

          if (!startPosition) {
            return node;
          }

          return {
            ...node,
            position: {
              x: startPosition.x + dx,
              y: startPosition.y + dy,
            },
          };
        })
      );
    },
    [setNodes]
  );

  const handleNodeDragStop = useCallback(() => {
    subtreeDragRef.current = null;
  }, []);

  const handlePaneClick = useCallback(
    () => {
      clearInspector();
    },
    [clearInspector]
  );

  const handleResetGraph = useCallback(() => {
    subtreeDragRef.current = null;
    clearInspector();
    setSelectedFlowNodeIds([]);
    setNodes(resetFlowNodes(flowNodes));
    setEdges(resetFlowEdges(flowEdges));

    window.requestAnimationFrame(() => {
      flowInstanceRef.current?.fitView({
        padding: 0.12,
        duration: 220,
      });
    });
  }, [clearInspector, flowEdges, flowNodes, setEdges, setNodes]);

  function toggleEdgeVisibility(key) {
    setEdgeVisibility((current) => ({
      ...current,
      [key]: !current[key],
    }));
  }

  return (
    <div
      className={`workspace ${selectedNode ? "has-inspector" : ""}`}
      onPointerDown={handleWorkspacePointerDown}
    >
      <aside className="control-panel" aria-label="Repository controls">
        <div className="brand-block">
          <div className="brand-copy">
            <p className="eyebrow">Repository Canvas</p>
            <h1>Repo Atlas</h1>
          </div>
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
            <Stat label="Avg estimated complexity" value={graph.stats.average_complexity} />
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
            {selectedFlowNodeIds.length > 0 && (
              <span>{formatNumber(selectedFlowNodeIds.length)} selected</span>
            )}
          </div>
        </div>
        {isLargeGraph && (
          <div className="canvas-warning">
            Large graph detected. Filtering by folder, file, or language will keep the
            canvas more responsive.
          </div>
        )}

        <div className="flow-canvas">
          <ReactFlow
            className={isSelectionMode ? "selection-mode" : ""}
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            onNodeDragStart={handleNodeDragStart}
            onNodeDrag={handleNodeDrag}
            onNodeDragStop={handleNodeDragStop}
            onEdgeClick={handlePaneClick}
            onPaneClick={handlePaneClick}
            onSelectionChange={handleSelectionChange}
            onInit={(instance) => {
              flowInstanceRef.current = instance;
            }}
            panOnDrag={isSelectionMode ? [1, 2] : true}
            selectionKeyCode={isSelectionMode ? null : "Shift"}
            multiSelectionKeyCode={["Control", "Meta"]}
            selectionMode={SelectionMode.Partial}
            selectionOnDrag={isSelectionMode}
            fitView
            minZoom={0.12}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={24} size={1.4} color="#302f38" />
            <Controls position="bottom-left" showInteractive={false}>
              <ControlButton
                className="control-toggle"
                title="Reset graph"
                aria-label="Reset graph"
                disabled={!hasGraph}
                onClick={handleResetGraph}
              >
                <ResetGraphIcon />
              </ControlButton>
              <ControlButton
                className={`control-toggle ${isSelectionMode ? "active" : ""}`}
                title="Select nodes"
                aria-label="Select nodes"
                aria-pressed={isSelectionMode}
                onClick={() =>
                  setCanvasMode((mode) => (mode === "select" ? "pan" : "select"))
                }
              >
                <SelectToolIcon />
              </ControlButton>
              <ControlButton
                className={`control-toggle ${
                  moveChildrenWithParent ? "active" : ""
                }`}
                title="Move children with parent"
                aria-label="Move children with parent"
                aria-pressed={moveChildrenWithParent}
                onClick={() => setMoveChildrenWithParent((enabled) => !enabled)}
              >
                <SubtreeMoveIcon />
              </ControlButton>
            </Controls>
            <MiniMap
              nodeStrokeWidth={3}
              nodeColor={(n) => (n.data.node.type === "file" ? "#44cf6e" : "#3fa9d6")}
              nodeBorderRadius={4}
              maskColor="rgba(15, 15, 18, 0.72)"
              pannable
              zoomable
              position="bottom-right"
            />
          </ReactFlow>
        </div>
      </main>

      {selectedNode && (
        <Inspector
          node={selectedNode}
          summaryState={summaryState}
          onRefresh={() => requestSummary(selectedNode)}
        />
      )}
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
        <span className="node-glyph" aria-hidden="true">
          {isFile ? <FileGlyph /> : <FolderGlyph />}
        </span>
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

function FolderGlyph() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
      <path
        d="M1.5 3.5A1 1 0 0 1 2.5 2.5h3.19a1 1 0 0 1 .8.4l.82 1.1h5.19a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1z"
        fill="currentColor"
      />
    </svg>
  );
}

function FileGlyph() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
      <path
        d="M3.5 1.5h5.09a1 1 0 0 1 .7.29l2.91 2.91a1 1 0 0 1 .3.71v8.09a1 1 0 0 1-1 1h-8a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1z"
        fill="currentColor"
      />
    </svg>
  );
}

function SelectToolIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
      <path
        d="M5 5h14v14H5z"
        stroke="currentColor"
        strokeDasharray="3 2"
        strokeWidth="1.8"
      />
      <path d="M8 8h3v3H8zM13 13h3v3h-3z" fill="currentColor" />
    </svg>
  );
}

function SubtreeMoveIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
      <path
        d="M12 5v6m0 0H7m5 0h5M7 11v6m10-6v6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path d="M9 3h6v4H9zM4 17h6v4H4zM14 17h6v4h-6z" fill="currentColor" />
    </svg>
  );
}

function ResetGraphIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
      <path
        d="M6.5 8.5A7 7 0 1 1 5 13"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M4 5v5h5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
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
        <Detail label="Estimated complexity" value={formatNumber(node.complexity)} />
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

function createChildrenByParentId(rawNodes) {
  const childrenByParentId = new Map();

  for (const node of rawNodes) {
    if (!node.parent) {
      continue;
    }

    const children = childrenByParentId.get(node.parent) || [];
    children.push(node.id);
    childrenByParentId.set(node.parent, children);
  }

  return childrenByParentId;
}

function getDescendantIds(nodeId, childrenByParentId) {
  const descendants = new Set();
  const stack = [...(childrenByParentId.get(nodeId) || [])];

  while (stack.length > 0) {
    const currentId = stack.pop();

    if (descendants.has(currentId)) {
      continue;
    }

    descendants.add(currentId);
    stack.push(...(childrenByParentId.get(currentId) || []));
  }

  return descendants;
}

function resetFlowNodes(flowNodes) {
  return flowNodes.map((node) => ({
    ...node,
    selected: false,
    dragging: false,
    position: {
      ...node.position,
    },
  }));
}

function resetFlowEdges(flowEdges) {
  return flowEdges.map((edge) => ({
    ...edge,
    selected: false,
  }));
}

export default App;
