"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import cytoscape, { Core, NodeSingular } from "cytoscape";
import dagre from "cytoscape-dagre";

cytoscape.use(dagre);
import type { CytoscapeGraphData } from "@/types/device";
import {
  convertToElements,
  getDeviceClassColor,
  findPathToRoot,
  findDescendants,
} from "@/lib/graph-utils";

interface DeviceGraphProps {
  data: CytoscapeGraphData | null;
  searchQuery: string;
  highlightMode: "none" | "ancestors" | "descendants";
  onNodeSelect: (nodeId: string | null) => void;
  selectedNodeId: string | null;
  isLoading: boolean;
  centerNodeId?: string | null;
}

export default function DeviceGraph({
  data,
  searchQuery,
  highlightMode,
  onNodeSelect,
  selectedNodeId,
  isLoading,
  centerNodeId,
}: DeviceGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [graphStats, setGraphStats] = useState({ nodes: 0, edges: 0 });
  const [layoutProgress, setLayoutProgress] = useState<string | null>(null);

  const initGraph = useCallback(() => {
    if (!containerRef.current || !data) return;

    // Destroy existing instance
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    setLayoutProgress("Converting elements...");
    const elements = convertToElements(data);
    setGraphStats({
      nodes: data.elements.nodes.length,
      edges: data.elements.edges.length,
    });

    setLayoutProgress("Initializing graph...");

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(device_name)",
            "text-valign": "bottom",
            "text-halign": "center",
            "font-size": "8px",
            "text-margin-y": 8,
            width: 12,
            height: 12,
            "background-color": (ele: NodeSingular) =>
              getDeviceClassColor(ele.data("device_class")),
            "border-width": 0,
            "text-background-color": "#1f2937",
            "text-background-opacity": 0.9,
            "text-background-padding": "2px",
            color: "#9ca3af",
            "text-max-width": "70px",
            "text-wrap": "ellipsis",
          },
        },
        {
          selector: "node.center-node",
          style: {
            label: "data(device_name)",
            "text-valign": "bottom",
            "text-halign": "center",
            "font-size": "12px",
            "text-margin-y": 8,
            "border-width": 4,
            "border-color": "#3b82f6",
            width: 30,
            height: 30,
            "text-background-color": "#1f2937",
            "text-background-opacity": 0.95,
            "text-background-padding": "4px",
            color: "#fff",
            "font-weight": "bold",
            "z-index": 999,
          },
        },
        {
          selector: "node:selected",
          style: {
            label: "data(device_name)",
            "text-valign": "bottom",
            "text-halign": "center",
            "font-size": "11px",
            "text-margin-y": 6,
            "border-width": 3,
            "border-color": "#10b981",
            width: 24,
            height: 24,
            "text-background-color": "#1f2937",
            "text-background-opacity": 0.9,
            "text-background-padding": "3px",
            color: "#fff",
          },
        },
        {
          selector: "node.highlighted",
          style: {
            "border-width": 2,
            "border-color": "#8b5cf6",
            width: 18,
            height: 18,
            color: "#c4b5fd",
          },
        },
        {
          selector: "node.search-match",
          style: {
            label: "data(device_name)",
            "text-valign": "bottom",
            "text-halign": "center",
            "font-size": "10px",
            "text-margin-y": 5,
            "border-width": 3,
            "border-color": "#10b981",
            width: 20,
            height: 20,
            "text-background-color": "#1f2937",
            "text-background-opacity": 0.9,
            "text-background-padding": "3px",
            color: "#fff",
          },
        },
        {
          selector: "node.dimmed",
          style: {
            opacity: 0.2,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#4b5563",
            "target-arrow-color": "#4b5563",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.7,
            "curve-style": "bezier",
            opacity: 0.6,
          },
        },
        {
          selector: "edge.highlighted",
          style: {
            width: 2.5,
            "line-color": "#8b5cf6",
            "target-arrow-color": "#8b5cf6",
            opacity: 1,
          },
        },
        {
          selector: "edge.dimmed",
          style: {
            opacity: 0.1,
          },
        },
      ],
      layout: {
        name: "preset",
      },
      minZoom: 0.1,
      maxZoom: 5,
      wheelSensitivity: 0.3,
      pixelRatio: 1,
    });

    // Apply hierarchical layout for subgraphs
    setLayoutProgress("Calculating layout...");

    // Use dagre layout for better hierarchical spacing
    const layoutOptions = {
      name: "dagre",
      rankDir: "TB", // Top to bottom
      nodeSep: 80, // Horizontal separation between nodes
      rankSep: 120, // Vertical separation between ranks
      edgeSep: 40, // Separation between edges
      padding: 50,
      animate: false,
      fit: true,
    } as cytoscape.LayoutOptions;

    cy.layout(layoutOptions).run();

    // Mark center node
    if (centerNodeId) {
      const centerNode = cy.getElementById(centerNodeId);
      if (centerNode.nonempty()) {
        centerNode.addClass("center-node");
      }
    }

    cy.fit(undefined, 50);
    setLayoutProgress(null);

    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      onNodeSelect(node.id());
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        onNodeSelect(null);
      }
    });

    cyRef.current = cy;
  }, [data, centerNodeId, onNodeSelect]);

  useEffect(() => {
    initGraph();

    return () => {
      cyRef.current?.destroy();
    };
  }, [initGraph]);

  // Handle search highlighting
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.nodes().removeClass("search-match");

    if (searchQuery.trim().length >= 2) {
      const query = searchQuery.toLowerCase();
      let matchCount = 0;
      const maxMatches = 100;

      cy.nodes().forEach((node) => {
        if (matchCount >= maxMatches) return;

        const name = node.data("device_name")?.toLowerCase() || "";
        const id = node.data("id")?.toLowerCase() || "";
        const applicant = node.data("applicant")?.toLowerCase() || "";

        if (
          name.includes(query) ||
          id.includes(query) ||
          applicant.includes(query)
        ) {
          node.addClass("search-match");
          matchCount++;
        }
      });

      // Center on first match
      const matches = cy.nodes(".search-match");
      if (matches.length > 0) {
        cy.animate({
          center: { eles: matches.first() },
          zoom: 2,
          duration: 500,
        });
      }
    }
  }, [searchQuery]);

  // Handle selection and path highlighting
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass("highlighted dimmed");

    // Re-apply center-node class
    if (centerNodeId) {
      const centerNode = cy.getElementById(centerNodeId);
      if (centerNode.nonempty()) {
        centerNode.addClass("center-node");
      }
    }

    if (selectedNodeId && highlightMode !== "none") {
      const selectedNode = cy.getElementById(selectedNodeId);

      let highlighted;
      if (highlightMode === "ancestors") {
        highlighted = findPathToRoot(cy, selectedNodeId);
      } else {
        highlighted = findDescendants(cy, selectedNodeId).union(selectedNode);
        highlighted = highlighted.union(highlighted.connectedEdges());
      }

      highlighted.addClass("highlighted");
      cy.elements().difference(highlighted).addClass("dimmed");
    }

    if (selectedNodeId) {
      const node = cy.getElementById(selectedNodeId);
      node.select();
      cy.animate({
        center: { eles: node },
        zoom: Math.max(cy.zoom(), 1.5),
        duration: 300,
      });
    } else {
      cy.nodes().unselect();
    }
  }, [selectedNodeId, highlightMode, centerNodeId]);

  if (isLoading) {
    return (
      <div className="w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading graph data...</p>
          <p className="text-gray-500 text-sm mt-1">This may take a moment for large datasets</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <div
        ref={containerRef}
        className="w-full h-full bg-gray-900 rounded-lg"
        style={{ minHeight: "500px" }}
      />
      {layoutProgress && (
        <div className="absolute inset-0 bg-gray-900/80 flex items-center justify-center rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
            <p className="text-gray-400">{layoutProgress}</p>
          </div>
        </div>
      )}
      <div className="absolute bottom-4 left-4 bg-gray-800/90 px-3 py-2 rounded text-xs text-gray-400">
        {graphStats.nodes.toLocaleString()} nodes · {graphStats.edges.toLocaleString()} edges
      </div>
      <div className="absolute bottom-4 right-4 bg-gray-800/90 px-3 py-2 rounded text-xs text-gray-400">
        Scroll to zoom · Drag to pan · Click node for details
      </div>
    </div>
  );
}
