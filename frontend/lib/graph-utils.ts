import type { CytoscapeGraphData, CytoscapeNode, CytoscapeEdge } from "@/types/device";
import type { ElementDefinition } from "cytoscape";

export function convertToElements(data: CytoscapeGraphData): ElementDefinition[] {
  const nodes: ElementDefinition[] = data.elements.nodes.map((node) => ({
    data: {
      ...node.data,
      label: node.data.device_name,
    },
  }));

  const edges: ElementDefinition[] = data.elements.edges.map((edge) => ({
    data: edge.data,
  }));

  return [...nodes, ...edges];
}

export function findAncestors(
  cy: cytoscape.Core,
  nodeId: string
): cytoscape.Collection {
  const node = cy.getElementById(nodeId);
  let ancestors = cy.collection();
  let current = node;

  while (current.nonempty()) {
    const incomers = current.incomers("node");
    if (incomers.nonempty()) {
      ancestors = ancestors.union(incomers);
      current = incomers;
    } else {
      break;
    }
  }

  return ancestors;
}

export function findDescendants(
  cy: cytoscape.Core,
  nodeId: string
): cytoscape.Collection {
  const node = cy.getElementById(nodeId);
  let descendants = cy.collection();
  let frontier = node.outgoers("node");

  while (frontier.nonempty()) {
    descendants = descendants.union(frontier);
    frontier = frontier.outgoers("node");
  }

  return descendants;
}

export function findPathToRoot(
  cy: cytoscape.Core,
  nodeId: string
): cytoscape.Collection {
  const node = cy.getElementById(nodeId);
  let path = cy.collection().union(node);
  let current = node;

  while (current.nonempty()) {
    const incomers = current.incomers();
    if (incomers.nonempty()) {
      path = path.union(incomers);
      current = incomers.nodes();
    } else {
      break;
    }
  }

  return path;
}

export function getRootNodes(cy: cytoscape.Core): cytoscape.Collection {
  return cy.nodes().filter((node) => node.incomers("edge").length === 0);
}

export function getDeviceClassColor(deviceClass: string): string {
  switch (deviceClass) {
    case "3":
    case "III":
      return "#ef4444"; // red - high risk
    case "2":
    case "II":
      return "#f59e0b"; // amber - moderate risk
    case "1":
    case "I":
      return "#22c55e"; // green - low risk
    default:
      return "#6b7280"; // gray
  }
}

export function getDeviceClassLabel(deviceClass: string): string {
  switch (deviceClass) {
    case "3":
      return "Class III (High Risk)";
    case "2":
      return "Class II (Moderate Risk)";
    case "1":
      return "Class I (Low Risk)";
    default:
      return `Class ${deviceClass}`;
  }
}

/**
 * Extract a subgraph centered on a node with depth-limited BFS.
 * Traverses ancestors (predicates) and descendants (devices using this one).
 */
export function extractSubgraph(
  data: CytoscapeGraphData,
  centerNodeId: string,
  ancestorDepth: number = 5,
  descendantDepth: number = 5,
  maxNodes: number = 500
): CytoscapeGraphData {
  // Build adjacency maps from raw data
  const nodeMap = new Map<string, CytoscapeNode>();
  const parentsOf = new Map<string, string[]>(); // node -> its predicates (incoming)
  const childrenOf = new Map<string, string[]>(); // node -> devices using it (outgoing)

  for (const node of data.elements.nodes) {
    nodeMap.set(node.data.id, node);
    parentsOf.set(node.data.id, []);
    childrenOf.set(node.data.id, []);
  }

  for (const edge of data.elements.edges) {
    // edge: source -> target means source is predicate of target
    const parents = parentsOf.get(edge.data.target);
    if (parents) parents.push(edge.data.source);
    const children = childrenOf.get(edge.data.source);
    if (children) children.push(edge.data.target);
  }

  // BFS to collect nodes within depth limits
  const includedNodes = new Set<string>();

  // Add center node
  if (!nodeMap.has(centerNodeId)) {
    return {
      metadata: { ...data.metadata, total_nodes: 0, total_edges: 0 },
      elements: { nodes: [], edges: [] }
    };
  }
  includedNodes.add(centerNodeId);

  // BFS upward (ancestors/predicates)
  let frontier = [centerNodeId];
  for (let depth = 0; depth < ancestorDepth && frontier.length > 0 && includedNodes.size < maxNodes; depth++) {
    const nextFrontier: string[] = [];
    for (const nodeId of frontier) {
      const parents = parentsOf.get(nodeId) || [];
      for (const parentId of parents) {
        if (!includedNodes.has(parentId) && includedNodes.size < maxNodes) {
          includedNodes.add(parentId);
          nextFrontier.push(parentId);
        }
      }
    }
    frontier = nextFrontier;
  }

  // BFS downward (descendants/children)
  frontier = [centerNodeId];
  for (let depth = 0; depth < descendantDepth && frontier.length > 0 && includedNodes.size < maxNodes; depth++) {
    const nextFrontier: string[] = [];
    for (const nodeId of frontier) {
      const children = childrenOf.get(nodeId) || [];
      for (const childId of children) {
        if (!includedNodes.has(childId) && includedNodes.size < maxNodes) {
          includedNodes.add(childId);
          nextFrontier.push(childId);
        }
      }
    }
    frontier = nextFrontier;
  }

  // Collect nodes
  const nodes: CytoscapeNode[] = [];
  for (const nodeId of includedNodes) {
    const node = nodeMap.get(nodeId);
    if (node) nodes.push(node);
  }

  // Collect edges between included nodes
  const edges: CytoscapeEdge[] = [];
  for (const edge of data.elements.edges) {
    if (includedNodes.has(edge.data.source) && includedNodes.has(edge.data.target)) {
      edges.push(edge);
    }
  }

  return {
    metadata: {
      ...data.metadata,
      total_nodes: nodes.length,
      total_edges: edges.length,
    },
    elements: { nodes, edges }
  };
}

/**
 * Search devices by name, ID, or applicant.
 * Returns top N matches sorted by relevance.
 */
export function searchDevices(
  data: CytoscapeGraphData,
  query: string,
  maxResults: number = 20
): CytoscapeNode[] {
  if (!query || query.trim().length < 2) return [];

  const q = query.toLowerCase().trim();
  const results: { node: CytoscapeNode; score: number }[] = [];

  for (const node of data.elements.nodes) {
    const id = node.data.id.toLowerCase();
    const name = (node.data.device_name || "").toLowerCase();
    const applicant = (node.data.applicant || "").toLowerCase();

    let score = 0;

    // Exact ID match is highest priority
    if (id === q) score = 100;
    else if (id.startsWith(q)) score = 80;
    else if (id.includes(q)) score = 60;
    // Name matches
    else if (name.startsWith(q)) score = 50;
    else if (name.includes(q)) score = 40;
    // Applicant matches
    else if (applicant.includes(q)) score = 20;

    if (score > 0) {
      results.push({ node, score });
    }
  }

  // Sort by score descending, then by ID
  results.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.node.data.id.localeCompare(b.node.data.id);
  });

  return results.slice(0, maxResults).map(r => r.node);
}
