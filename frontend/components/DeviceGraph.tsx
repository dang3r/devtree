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
  calculateNodeDepths,
  parseDateToTimestamp,
} from "@/lib/graph-utils";

interface DeviceGraphProps {
  data: CytoscapeGraphData | null;
  searchQuery: string;
  highlightMode: "none" | "ancestors" | "descendants";
  onNodeSelect: (nodeId: string | null) => void;
  selectedNodeId: string | null;
  isLoading: boolean;
  centerNodeId?: string | null;
  viewMode?: "graph" | "timeline";
}

export default function DeviceGraph({
  data,
  searchQuery,
  highlightMode,
  onNodeSelect,
  selectedNodeId,
  isLoading,
  centerNodeId,
  viewMode = "graph",
}: DeviceGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [graphStats, setGraphStats] = useState({ nodes: 0, edges: 0 });
  const [layoutProgress, setLayoutProgress] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<{ min: Date; max: Date } | null>(null);
  const [yearMarkers, setYearMarkers] = useState<number[]>([]);
  const [viewportTransform, setViewportTransform] = useState({ zoom: 1, panX: 0, panY: 0 });
  const timelineMetaRef = useRef<{ minTime: number; maxTime: number; graphPadding: number } | null>(null);

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

    // Apply layout based on view mode
    setLayoutProgress("Calculating layout...");

    if (viewMode === "timeline") {
      // Timeline layout: X = date, Y = depth
      const depths = calculateNodeDepths(cy);

      // Gather date range
      let minDate = Infinity;
      let maxDate = -Infinity;
      const nodeDates = new Map<string, number>();

      cy.nodes().forEach((node) => {
        const dateStr = node.data("decision_date");
        const timestamp = parseDateToTimestamp(dateStr);
        if (timestamp !== null) {
          nodeDates.set(node.id(), timestamp);
          minDate = Math.min(minDate, timestamp);
          maxDate = Math.max(maxDate, timestamp);
        }
      });

      // Fallback if no valid dates
      if (minDate === Infinity) {
        minDate = 0;
        maxDate = 1;
      }

      // Add some padding to date range
      const dateRange = maxDate - minDate || 1;
      const padding = dateRange * 0.05;
      minDate -= padding;
      maxDate += padding;

      // Calculate layout dimensions
      const containerWidth = containerRef.current?.clientWidth || 1000;
      const containerHeight = containerRef.current?.clientHeight || 600;
      const graphPadding = 80;
      const rowHeight = 100;
      const maxDepth = Math.max(...Array.from(depths.values()), 0);

      // Position nodes
      cy.nodes().forEach((node) => {
        const nodeDate = nodeDates.get(node.id());
        const depth = depths.get(node.id()) ?? 0;

        // X position based on date
        let x: number;
        if (nodeDate !== undefined) {
          x = graphPadding + ((nodeDate - minDate) / (maxDate - minDate)) * (containerWidth - 2 * graphPadding);
        } else {
          // Fallback for nodes without dates - position based on depth
          x = graphPadding + (depth / (maxDepth + 1)) * (containerWidth - 2 * graphPadding);
        }

        // Y position based on depth
        const y = graphPadding + depth * rowHeight;

        node.position({ x, y });
      });

      cy.fit(undefined, 50);

      // Store timeline metadata for dynamic gridlines
      timelineMetaRef.current = { minTime: minDate, maxTime: maxDate, graphPadding };

      // Store date range for axis display
      const minYear = new Date(minDate).getFullYear();
      const maxYear = new Date(maxDate).getFullYear();

      // Generate year markers (every 5 years for cleaner display, or every year if range is small)
      const yearRange = maxYear - minYear;
      const yearStep = yearRange > 20 ? 5 : yearRange > 10 ? 2 : 1;
      const markers: number[] = [];
      const startYear = Math.ceil(minYear / yearStep) * yearStep;
      for (let year = startYear; year <= maxYear; year += yearStep) {
        markers.push(year);
      }
      setYearMarkers(markers);

      setDateRange({
        min: new Date(minDate),
        max: new Date(maxDate),
      });
    } else {
      setDateRange(null);
      setYearMarkers([]);
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
    }

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

    // Track viewport changes for dynamic gridlines
    const updateViewport = () => {
      const zoom = cy.zoom();
      const pan = cy.pan();
      setViewportTransform({ zoom, panX: pan.x, panY: pan.y });
    };

    cy.on("zoom pan", updateViewport);
    updateViewport(); // Initial state

    cyRef.current = cy;
  }, [data, centerNodeId, onNodeSelect, viewMode]);

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
      {/* Timeline axis display with year markers and gridlines */}
      {viewMode === "timeline" && dateRange && timelineMetaRef.current && (
        <>
          {/* Year markers and vertical gridlines */}
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            {yearMarkers.map((year) => {
              const meta = timelineMetaRef.current!;
              const containerWidth = containerRef.current?.clientWidth || 1000;

              // Calculate the graph X position for this year (same formula as layout)
              const yearTime = new Date(year, 0, 1).getTime();
              const graphX = meta.graphPadding + ((yearTime - meta.minTime) / (meta.maxTime - meta.minTime)) * (containerWidth - 2 * meta.graphPadding);

              // Transform to screen coordinates using viewport
              const screenX = graphX * viewportTransform.zoom + viewportTransform.panX;

              // Skip if outside visible range
              if (screenX < -50 || screenX > containerWidth + 50) return null;

              return (
                <div
                  key={year}
                  className="absolute top-0 bottom-0 flex flex-col items-center"
                  style={{ left: `${screenX}px` }}
                >
                  {/* Dotted vertical line */}
                  <div
                    className="flex-1 border-l border-dashed border-gray-600/40"
                    style={{ marginTop: '40px' }}
                  />
                  {/* Year label at top */}
                  <div className="absolute top-2 -translate-x-1/2 bg-gray-800/95 px-2 py-1 rounded text-xs text-gray-400 whitespace-nowrap">
                    {year}
                  </div>
                </div>
              );
            })}
          </div>
          {/* Time axis label */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-gray-800/90 px-3 py-1 rounded text-xs text-gray-500 pointer-events-none z-10">
            Time →
          </div>
        </>
      )}
      <div className="absolute bottom-4 left-4 bg-gray-800/90 px-3 py-2 rounded text-xs text-gray-400">
        {graphStats.nodes.toLocaleString()} nodes · {graphStats.edges.toLocaleString()} edges
        {viewMode === "timeline" && " · Timeline view"}
      </div>
      <div className="absolute bottom-4 right-4 bg-gray-800/90 px-3 py-2 rounded text-xs text-gray-400">
        Scroll to zoom · Drag to pan · Click node for details
      </div>
    </div>
  );
}
