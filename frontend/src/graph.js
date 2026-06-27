import { MarkerType } from "@xyflow/react";

const DEPTH_SPACING = 300;
const ROW_SPACING = 112;

export function filterGraph(graph, searchTerm) {
  const query = searchTerm.trim().toLowerCase();

  if (!query) {
    return graph;
  }

  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const visibleIds = new Set();

  for (const node of graph.nodes) {
    if (getSearchText(node).includes(query)) {
      visibleIds.add(node.id);
      addAncestors(node, nodesById, visibleIds);
    }
  }

  return {
    ...graph,
    nodes: graph.nodes.filter((node) => visibleIds.has(node.id)),
    edges: graph.edges.filter(
      (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)
    ),
  };
}

export function createFlowNodes(rawNodes) {
  const laneCounts = new Map();
  const sortedNodes = [...rawNodes].sort(compareGraphNodes);

  return sortedNodes.map((node) => {
    const depth = node.id === "." ? 0 : node.id.split("/").length;
    const lane = laneCounts.get(depth) || 0;

    laneCounts.set(depth, lane + 1);

    return {
      id: node.id,
      type: "repoNode",
      position: {
        x: depth * DEPTH_SPACING,
        y: lane * ROW_SPACING,
      },
      data: {
        node,
      },
    };
  });
}

export function createFlowEdges(rawEdges, edgeVisibility) {
  return rawEdges
    .filter((edge) => {
      if (edge.type === "contains") {
        return edgeVisibility.contains;
      }

      if (edge.type === "depends_on") {
        return edgeVisibility.dependencies;
      }

      return true;
    })
    .map((edge, index) => {
      const isDependency = edge.type === "depends_on";

      return {
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        label: isDependency ? edge.label || "imports" : "",
        animated: isDependency,
        className: isDependency ? "flow-edge dependency-edge" : "flow-edge contains-edge",
        markerEnd: isDependency
          ? {
              type: MarkerType.ArrowClosed,
              width: 16,
              height: 16,
              color: "#b45309",
            }
          : undefined,
      };
    });
}

export function formatBytes(bytes) {
  if (typeof bytes !== "number") {
    return "n/a";
  }

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatNumber(value) {
  if (typeof value !== "number") {
    return "0";
  }

  return new Intl.NumberFormat().format(value);
}

function compareGraphNodes(left, right) {
  if (left.id === ".") {
    return -1;
  }

  if (right.id === ".") {
    return 1;
  }

  const leftDepth = left.id.split("/").length;
  const rightDepth = right.id.split("/").length;

  if (leftDepth !== rightDepth) {
    return leftDepth - rightDepth;
  }

  if (left.type !== right.type) {
    return left.type === "folder" ? -1 : 1;
  }

  return left.id.localeCompare(right.id);
}

function addAncestors(node, nodesById, visibleIds) {
  let parentId = node.parent;

  while (parentId) {
    visibleIds.add(parentId);
    parentId = nodesById.get(parentId)?.parent;
  }
}

function getSearchText(node) {
  return [
    node.id,
    node.name,
    node.type,
    node.language,
    node.extension,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}
