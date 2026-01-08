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

// BasePath for GitHub Pages deployment
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

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
            label: (ele: NodeSingular) => `${ele.data("label")}\n${ele.data("sublabel") || ""}`,
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "10px",
            width: 100,
            height: 50,
            shape: "round-rectangle",
            "background-color": "#1e293b",
            "border-width": 3,
            "border-color": (ele: NodeSingular) =>
              getDeviceClassColor(ele.data("device_class")),
            color: "#f1f5f9",
            "text-wrap": "wrap",
            "text-max-width": "90px",
            "font-weight": "normal",
          },
        },
        {
          selector: "node.center-node",
          style: {
            label: (ele: NodeSingular) => `${ele.data("label")}\n${ele.data("sublabel") || ""}`,
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "12px",
            "border-width": 4,
            "border-color": "#3b82f6",
            "background-color": "#1e3a5f",
            width: 120,
            height: 60,
            color: "#fff",
            "font-weight": "bold",
            "z-index": 999,
          },
        },
        {
          selector: "node:selected",
          style: {
            label: (ele: NodeSingular) => `${ele.data("label")}\n${ele.data("sublabel") || ""}`,
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "11px",
            "border-width": 3,
            "border-color": "#10b981",
            "background-color": "#134e4a",
            width: 110,
            height: 55,
            color: "#fff",
          },
        },
        {
          selector: "node.highlighted",
          style: {
            "border-width": 3,
            "border-color": "#8b5cf6",
            "background-color": "#2e1065",
            width: 105,
            height: 52,
            color: "#e9d5ff",
          },
        },
        {
          selector: "node.search-match",
          style: {
            label: (ele: NodeSingular) => `${ele.data("label")}\n${ele.data("sublabel") || ""}`,
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "11px",
            "border-width": 3,
            "border-color": "#10b981",
            "background-color": "#134e4a",
            width: 110,
            height: 55,
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
      // Ensure we have a marker at or after the most recent device
      const lastMarker = markers[markers.length - 1];
      if (lastMarker < maxYear) {
        markers.push(lastMarker + yearStep);
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
        nodeSep: 120, // Horizontal separation between nodes (increased for larger nodes)
        rankSep: 80, // Vertical separation between ranks
        edgeSep: 50, // Separation between edges
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

    // Track viewport changes for dynamic gridlines, font scaling, and label detail
    const updateViewport = () => {
      const zoom = cy.zoom();
      const pan = cy.pan();
      setViewportTransform({ zoom, panX: pan.x, panY: pan.y });

      // Scale font sizes inversely with zoom (larger base sizes for visibility)
      const scaleFactor = Math.max(0.6, Math.min(1.8, 1 / zoom));
      const baseFontSize = 10 * scaleFactor;
      const centerFontSize = 12 * scaleFactor;
      const selectedFontSize = 11 * scaleFactor;
      const searchFontSize = 11 * scaleFactor;

      // Determine label detail level based on zoom
      // When zoomed in (zoom > 0.5), show full label with device name
      // When zoomed out, show only the device ID
      const showFullLabel = zoom > 0.5;
      const labelFn = showFullLabel
        ? (ele: NodeSingular) => `${ele.data("label")}\n${ele.data("sublabel") || ""}`
        : (ele: NodeSingular) => ele.data("label");

      // Adjust node size based on zoom - smaller when zoomed out
      const baseWidth = showFullLabel ? 100 : 65;
      const baseHeight = showFullLabel ? 50 : 28;

      // Update node styles based on zoom
      cy.style()
        .selector("node")
        .style({
          "font-size": `${baseFontSize}px`,
          "label": labelFn,
          "width": baseWidth,
          "height": baseHeight,
        })
        .selector("node.center-node")
        .style({
          "font-size": `${centerFontSize}px`,
          "label": labelFn,
          "width": showFullLabel ? 120 : 75,
          "height": showFullLabel ? 60 : 32,
        })
        .selector("node:selected")
        .style({
          "font-size": `${selectedFontSize}px`,
          "label": labelFn,
          "width": showFullLabel ? 110 : 70,
          "height": showFullLabel ? 55 : 30,
        })
        .selector("node.search-match")
        .style({
          "font-size": `${searchFontSize}px`,
          "label": labelFn,
          "width": showFullLabel ? 110 : 70,
          "height": showFullLabel ? 55 : 30,
        })
        .update();
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
        <div className="flex flex-col items-center justify-center gap-4 text-gray-500">
          <img src={`${basePath}/loading.gif`} alt="Loading" className="w-48 h-48 md:w-64 md:h-64" />
          <span className="text-base md:text-lg">Loading device database...</span>
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
