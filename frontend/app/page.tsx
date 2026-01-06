"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import type { CytoscapeGraphData, Device, CytoscapeNode } from "@/types/device";
import { searchDevices, extractSubgraph } from "@/lib/graph-utils";
import SearchBar from "@/components/SearchBar";
import DevicePanel from "@/components/DevicePanel";

const DeviceGraph = dynamic(() => import("@/components/DeviceGraph"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
      <p className="text-gray-400">Loading graph component...</p>
    </div>
  ),
});

export default function Home() {
  const [data, setData] = useState<CytoscapeGraphData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [focusedDeviceId, setFocusedDeviceId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [highlightMode, setHighlightMode] = useState<
    "none" | "ancestors" | "descendants"
  >("none");
  const [depth, setDepth] = useState(5);
  const [viewMode, setViewMode] = useState<"graph" | "timeline">("graph");

  useEffect(() => {
    async function loadData() {
      try {
        setIsLoading(true);
        const response = await fetch("/cytoscape_graph.json");
        if (!response.ok) {
          throw new Error(`Failed to load graph data: ${response.status}`);
        }
        const graphData = await response.json();
        setData(graphData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setIsLoading(false);
      }
    }

    loadData();
  }, []);

  // Search results from the full graph
  const searchResults = useMemo((): CytoscapeNode[] => {
    if (!data || searchQuery.length < 2) return [];
    return searchDevices(data, searchQuery, 20);
  }, [data, searchQuery]);

  // Extract subgraph when a device is focused
  const subgraphData = useMemo((): CytoscapeGraphData | null => {
    if (!data || !focusedDeviceId) return null;
    return extractSubgraph(data, focusedDeviceId, depth, depth);
  }, [data, focusedDeviceId, depth]);

  // Get focused device info
  const focusedDevice = useMemo(() => {
    if (!focusedDeviceId || !data) return null;
    const node = data.elements.nodes.find((n) => n.data.id === focusedDeviceId);
    return node?.data || null;
  }, [focusedDeviceId, data]);

  // Get selected device info (for panel)
  const selectedDevice = useMemo(() => {
    if (!selectedNodeId || !data) return null;
    const node = data.elements.nodes.find((n) => n.data.id === selectedNodeId);
    return node?.data || null;
  }, [selectedNodeId, data]);

  const handleSearchChange = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleDeviceSelect = useCallback((deviceId: string) => {
    setFocusedDeviceId(deviceId);
    setSelectedNodeId(deviceId);
    setHighlightMode("none");
  }, []);

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    if (!nodeId) {
      setHighlightMode("none");
    }
  }, []);

  const handleHighlightModeChange = useCallback(
    (mode: "none" | "ancestors" | "descendants") => {
      setHighlightMode(mode);
    },
    []
  );

  const handleClosePanel = useCallback(() => {
    setSelectedNodeId(null);
    setHighlightMode("none");
  }, []);

  const handleClearFocus = useCallback(() => {
    setFocusedDeviceId(null);
    setSelectedNodeId(null);
    setHighlightMode("none");
  }, []);

  if (error) {
    return (
      <main className="min-h-screen p-4 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-500 mb-2">Error</h1>
          <p className="text-gray-400">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen p-4">
      <div className="max-w-[1800px] mx-auto">
        <header className="mb-4">
          <h1 className="text-2xl font-bold text-white mb-2">
            DevTree - Medical Device Explorer
          </h1>
          <p className="text-gray-400 text-sm">
            Explore FDA 510(k) medical device clearances and their predicate
            relationships.{" "}
            {data && (
              <span className="text-gray-500">
                {data.metadata.total_nodes.toLocaleString()} devices,{" "}
                {data.metadata.total_edges.toLocaleString()} predicate
                relationships.
              </span>
            )}
          </p>
        </header>

        <SearchBar
          searchResults={searchResults}
          onSearchChange={handleSearchChange}
          onDeviceSelect={handleDeviceSelect}
          selectedDeviceId={focusedDeviceId}
          highlightMode={highlightMode}
          onHighlightModeChange={handleHighlightModeChange}
          hasSelection={!!selectedNodeId}
        />

        {/* Subgraph controls - show when device is focused */}
        {focusedDeviceId && focusedDevice && (
          <div className="mt-2 p-3 bg-gray-800 rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <span className="text-gray-400 text-sm">Viewing subgraph of: </span>
                <span className="text-white font-medium">{focusedDevice.device_name}</span>
                <span className="text-gray-500 ml-2 font-mono text-sm">({focusedDeviceId})</span>
              </div>
              {subgraphData && (
                <span className="text-gray-500 text-sm">
                  {subgraphData.metadata.total_nodes} nodes, {subgraphData.metadata.total_edges} edges
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              {/* View mode toggle */}
              <div className="flex rounded-lg overflow-hidden border border-gray-600">
                <button
                  onClick={() => setViewMode("graph")}
                  className={`px-3 py-1 text-sm transition-colors ${
                    viewMode === "graph"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                  }`}
                >
                  Graph
                </button>
                <button
                  onClick={() => setViewMode("timeline")}
                  className={`px-3 py-1 text-sm transition-colors ${
                    viewMode === "timeline"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                  }`}
                >
                  Timeline
                </button>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-400 text-sm">Depth:</span>
                <button
                  onClick={() => setDepth(Math.max(1, depth - 1))}
                  className="px-2 py-1 bg-gray-700 rounded hover:bg-gray-600 text-white"
                >
                  -
                </button>
                <span className="text-white w-6 text-center">{depth}</span>
                <button
                  onClick={() => setDepth(Math.min(10, depth + 1))}
                  className="px-2 py-1 bg-gray-700 rounded hover:bg-gray-600 text-white"
                >
                  +
                </button>
              </div>
              <button
                onClick={handleClearFocus}
                className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-white text-sm"
              >
                Clear
              </button>
            </div>
          </div>
        )}

        <div className="flex gap-4 mt-4">
          <div className="flex-1 h-[calc(100vh-280px)]">
            {!focusedDeviceId ? (
              // Empty state - prompt user to search
              <div className="w-full h-full bg-gray-900 rounded-lg flex items-center justify-center">
                <div className="text-center max-w-md">
                  <div className="text-6xl mb-4">🔍</div>
                  <h2 className="text-xl font-semibold text-white mb-2">
                    Search for a Device
                  </h2>
                  <p className="text-gray-400 mb-4">
                    Enter a device name, 510(k) number, or manufacturer in the search bar above
                    to explore its predicate relationships.
                  </p>
                  {data && !isLoading && (
                    <p className="text-gray-500 text-sm">
                      {data.metadata.total_nodes.toLocaleString()} devices indexed and ready to explore
                    </p>
                  )}
                  {isLoading && (
                    <div className="flex items-center justify-center gap-2 text-gray-500">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
                      <span>Loading device database...</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <DeviceGraph
                data={subgraphData}
                searchQuery=""
                highlightMode={highlightMode}
                onNodeSelect={handleNodeSelect}
                selectedNodeId={selectedNodeId}
                isLoading={isLoading}
                centerNodeId={focusedDeviceId}
                viewMode={viewMode}
              />
            )}
          </div>

          <DevicePanel
            device={selectedDevice as Device | null}
            onClose={handleClosePanel}
          />
        </div>

        <footer className="mt-4 text-center text-gray-500 text-xs">
          <div className="flex justify-center gap-6 mb-2">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-red-500" />
              Class III (High Risk)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-amber-500" />
              Class II (Moderate Risk)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-green-500" />
              Class I (Low Risk)
            </span>
          </div>
          <p>
            Data sourced from FDA 510(k) database. Generated{" "}
            {data?.metadata.generated_at
              ? new Date(data.metadata.generated_at).toLocaleDateString()
              : "..."}
          </p>
        </footer>
      </div>
    </main>
  );
}
