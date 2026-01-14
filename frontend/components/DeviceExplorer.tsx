"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import type { CytoscapeGraphData, Device, CytoscapeNode } from "@/types/device";
import { searchDevices, extractSubgraph, searchCompanies, extractCompanySubgraph, getCompanyDeviceCount } from "@/lib/graph-utils";
import type { CompanySearchResult } from "@/lib/graph-utils";
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

// BasePath for GitHub Pages deployment
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

interface DeviceExplorerProps {
  initialDeviceId?: string | null;
  initialCompanyName?: string | null;
}

export default function DeviceExplorer({ initialDeviceId = null, initialCompanyName = null }: DeviceExplorerProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [data, setData] = useState<CytoscapeGraphData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [focusedDeviceId, setFocusedDeviceId] = useState<string | null>(initialDeviceId);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(initialDeviceId);
  const [highlightMode, setHighlightMode] = useState<"none" | "ancestors" | "descendants">("none");
  const [depth, setDepth] = useState(5);
  const [viewMode, setViewMode] = useState<"graph" | "timeline">("graph");
  const [focusedCompanyName, setFocusedCompanyName] = useState<string | null>(initialCompanyName);
  const [companyDeviceLimit, setCompanyDeviceLimit] = useState(50);
  const [companyViewMode, setCompanyViewMode] = useState<"company-only" | "with-predicates">("company-only");
  const [showMobilePanel, setShowMobilePanel] = useState(false);

  // Initialize from props
  useEffect(() => {
    if (initialDeviceId) {
      setFocusedDeviceId(initialDeviceId);
      setSelectedNodeId(initialDeviceId);
    }
    if (initialCompanyName) {
      setFocusedCompanyName(initialCompanyName);
    }
  }, [initialDeviceId, initialCompanyName]);

  useEffect(() => {
    async function loadData() {
      try {
        setIsLoading(true);
        const response = await fetch(`${basePath}/cytoscape_graph.json`);
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

  // Company search results
  const companyResults = useMemo((): CompanySearchResult[] => {
    if (!data || searchQuery.length < 2) return [];
    return searchCompanies(data, searchQuery, 5);
  }, [data, searchQuery]);

  // Extract subgraph when a device or company is focused
  const subgraphData = useMemo((): CytoscapeGraphData | null => {
    if (!data) return null;
    if (focusedCompanyName) {
      const predicateDepth = companyViewMode === "with-predicates" ? depth : 0;
      return extractCompanySubgraph(data, focusedCompanyName, companyDeviceLimit, predicateDepth);
    }
    if (focusedDeviceId) {
      return extractSubgraph(data, focusedDeviceId, depth, depth);
    }
    return null;
  }, [data, focusedDeviceId, focusedCompanyName, depth, companyDeviceLimit, companyViewMode]);

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

  // Get focused company device count
  const focusedCompanyDeviceCount = useMemo(() => {
    if (!focusedCompanyName || !data) return 0;
    return getCompanyDeviceCount(data, focusedCompanyName);
  }, [focusedCompanyName, data]);

  const handleSearchChange = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleDeviceSelect = useCallback((deviceId: string) => {
    setFocusedDeviceId(deviceId);
    setFocusedCompanyName(null);
    setSelectedNodeId(deviceId);
    setHighlightMode("none");
    // Preserve tab parameter if present
    const params = new URLSearchParams(searchParams?.toString() || '');
    const tabParam = params.get('tab');
    const queryString = tabParam ? `?tab=${tabParam}` : '';
    router.push(`/device/${deviceId}${queryString}`, { scroll: false });
  }, [router, searchParams]);

  const handleCompanySelect = useCallback((companyName: string) => {
    setFocusedCompanyName(companyName);
    setFocusedDeviceId(null);
    setSelectedNodeId(null);
    setHighlightMode("none");
    // Preserve tab parameter if present
    const params = new URLSearchParams(searchParams?.toString() || '');
    const tabParam = params.get('tab');
    const queryString = tabParam ? `?tab=${tabParam}` : '';
    router.push(`/company/${encodeURIComponent(companyName)}${queryString}`, { scroll: false });
  }, [router, searchParams]);

  const handleNodeSelect = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    if (nodeId) {
      setShowMobilePanel(true);
    } else {
      setHighlightMode("none");
    }
  }, []);

  const handleHighlightModeChange = useCallback((mode: "none" | "ancestors" | "descendants") => {
    setHighlightMode(mode);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedNodeId(null);
    setHighlightMode("none");
    setShowMobilePanel(false);
  }, []);

  const handleClearFocus = useCallback(() => {
    setFocusedDeviceId(null);
    setFocusedCompanyName(null);
    setSelectedNodeId(null);
    setHighlightMode("none");
    // Preserve tab parameter if present
    const params = new URLSearchParams(searchParams?.toString() || '');
    const tabParam = params.get('tab');
    const queryString = tabParam ? `?tab=${tabParam}` : '';
    router.push(`/${queryString}`, { scroll: false });
  }, [router, searchParams]);

  // Navigate to a device from the panel
  const handleNavigateToDevice = useCallback((deviceId: string) => {
    setFocusedDeviceId(deviceId);
    setFocusedCompanyName(null);
    setSelectedNodeId(deviceId);
    setHighlightMode("none");
    // Preserve tab parameter if present
    const params = new URLSearchParams(searchParams?.toString() || '');
    const tabParam = params.get('tab');
    const queryString = tabParam ? `?tab=${tabParam}` : '';
    router.push(`/device/${deviceId}${queryString}`, { scroll: false });
  }, [router, searchParams]);

  // Select a random device
  const handleRandomDevice = useCallback(() => {
    if (!data || data.elements.nodes.length === 0) return;
    const randomIndex = Math.floor(Math.random() * data.elements.nodes.length);
    const randomDevice = data.elements.nodes[randomIndex];
    const deviceId = randomDevice.data.id;
    setFocusedDeviceId(deviceId);
    setFocusedCompanyName(null);
    setSelectedNodeId(deviceId);
    setHighlightMode("none");
    // Preserve tab parameter if present
    const params = new URLSearchParams(searchParams?.toString() || '');
    const tabParam = params.get('tab');
    const queryString = tabParam ? `?tab=${tabParam}` : '';
    router.push(`/device/${deviceId}${queryString}`, { scroll: false });
  }, [data, router, searchParams]);

  if (error) {
    return (
      <main className="min-h-screen p-2 md:p-4 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-500 mb-2">Error</h1>
          <p className="text-gray-400">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen p-2 md:p-4 pt-0">
      <div className="w-full">
        <p className="text-gray-400 text-xs md:text-sm mb-2 md:mb-4">
          Explore FDA 510(k) medical device clearances and their predicate relationships.{" "}
          {data && (
            <span className="text-gray-500">
              {data.metadata.total_nodes.toLocaleString()} devices,{" "}
              {data.metadata.total_edges.toLocaleString()} relationships.
            </span>
          )}
        </p>
        <SearchBar
          searchResults={searchResults}
          companyResults={companyResults}
          onSearchChange={handleSearchChange}
          onDeviceSelect={handleDeviceSelect}
          onCompanySelect={handleCompanySelect}
          onRandomDevice={handleRandomDevice}
          selectedDeviceId={focusedDeviceId}
          highlightMode={highlightMode}
          onHighlightModeChange={handleHighlightModeChange}
          hasSelection={!!selectedNodeId}
          isLoading={isLoading}
        />

        {/* Device subgraph controls - mobile friendly */}
        {focusedDeviceId && focusedDevice && (
          <div className="mt-2 p-2 md:p-4 bg-gray-800 rounded-lg space-y-2 md:space-y-3">
            {/* Top row: device name and clear button */}
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium text-sm md:text-lg truncate">
                  {focusedDevice.device_name}
                </p>
                <p className="text-gray-500 text-xs md:text-sm font-mono">
                  {focusedDeviceId}
                  {subgraphData && (
                    <span className="ml-2">
                      ({subgraphData.metadata.total_nodes} nodes)
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={handleClearFocus}
                className="px-2 md:px-4 py-1 md:py-2 bg-red-600 hover:bg-red-700 active:bg-red-800 rounded text-white text-xs md:text-sm flex-shrink-0"
              >
                Clear
              </button>
            </div>

            {/* Controls row */}
            <div className="flex items-center gap-2 md:gap-4 flex-wrap">
              {/* View mode toggle */}
              <div className="flex rounded overflow-hidden border border-gray-600">
                <button
                  onClick={() => setViewMode("graph")}
                  className={`px-2 md:px-4 py-1 md:py-2 text-xs md:text-sm transition-colors ${
                    viewMode === "graph"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  Graph
                </button>
                <button
                  onClick={() => setViewMode("timeline")}
                  className={`px-2 md:px-4 py-1 md:py-2 text-xs md:text-sm transition-colors ${
                    viewMode === "timeline"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  Timeline
                </button>
              </div>

              {/* Depth control */}
              <div className="flex items-center gap-1 md:gap-2">
                <span className="text-gray-400 text-xs md:text-sm">Depth:</span>
                <button
                  onClick={() => setDepth(Math.max(1, depth - 1))}
                  className="w-6 h-6 md:w-8 md:h-8 bg-gray-700 rounded text-white text-sm md:text-base"
                >
                  -
                </button>
                <span className="text-white w-4 md:w-6 text-center text-xs md:text-base">{depth}</span>
                <button
                  onClick={() => setDepth(Math.min(10, depth + 1))}
                  className="w-6 h-6 md:w-8 md:h-8 bg-gray-700 rounded text-white text-sm md:text-base"
                >
                  +
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Company view controls - mobile friendly */}
        {focusedCompanyName && (
          <div className="mt-2 p-2 md:p-4 bg-gray-800 rounded-lg space-y-2 md:space-y-3">
            {/* Top row: company name and clear button */}
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium text-sm md:text-lg truncate flex items-center gap-1">
                  <span>🏢</span>
                  {focusedCompanyName}
                </p>
                <p className="text-gray-500 text-xs md:text-sm">
                  {focusedCompanyDeviceCount.toLocaleString()} total devices
                  {subgraphData && (
                    <span className="ml-2">
                      (showing {subgraphData.metadata.total_nodes})
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={handleClearFocus}
                className="px-2 md:px-4 py-1 md:py-2 bg-red-600 hover:bg-red-700 active:bg-red-800 rounded text-white text-xs md:text-sm flex-shrink-0"
              >
                Clear
              </button>
            </div>

            {/* Controls row */}
            <div className="flex items-center gap-2 md:gap-4 flex-wrap">
              {/* Device limit */}
              <div className="flex items-center gap-1 md:gap-2">
                <span className="text-gray-400 text-xs md:text-sm">Show:</span>
                <select
                  value={companyDeviceLimit}
                  onChange={(e) => setCompanyDeviceLimit(Number(e.target.value))}
                  className="bg-gray-700 text-white text-xs md:text-sm rounded px-1 md:px-2 py-1 md:py-2 border border-gray-600"
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={200}>200</option>
                </select>
              </div>

              {/* Company-only vs with-predicates toggle */}
              <div className="flex rounded overflow-hidden border border-gray-600">
                <button
                  onClick={() => setCompanyViewMode("company-only")}
                  className={`px-2 md:px-4 py-1 md:py-2 text-xs md:text-sm transition-colors ${
                    companyViewMode === "company-only"
                      ? "bg-green-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  Only
                </button>
                <button
                  onClick={() => {
                    setCompanyViewMode("with-predicates");
                    setDepth(0);
                  }}
                  className={`px-2 md:px-4 py-1 md:py-2 text-xs md:text-sm transition-colors ${
                    companyViewMode === "with-predicates"
                      ? "bg-green-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  +Preds
                </button>
              </div>

              {/* Depth control - only show when with-predicates */}
              {companyViewMode === "with-predicates" && (
                <div className="flex items-center gap-1 md:gap-2">
                  <span className="text-gray-400 text-xs md:text-sm">Depth:</span>
                  <button
                    onClick={() => setDepth(Math.max(0, depth - 1))}
                    className="w-6 h-6 md:w-8 md:h-8 bg-gray-700 rounded text-white text-sm md:text-base"
                  >
                    -
                  </button>
                  <span className="text-white w-4 md:w-6 text-center text-xs md:text-base">{depth}</span>
                  <button
                    onClick={() => setDepth(Math.min(10, depth + 1))}
                    className="w-6 h-6 md:w-8 md:h-8 bg-gray-700 rounded text-white text-sm md:text-base"
                  >
                    +
                  </button>
                </div>
              )}

              {/* Graph/Timeline toggle */}
              <div className="flex rounded overflow-hidden border border-gray-600">
                <button
                  onClick={() => setViewMode("graph")}
                  className={`px-2 md:px-4 py-1 md:py-2 text-xs md:text-sm transition-colors ${
                    viewMode === "graph"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  Graph
                </button>
                <button
                  onClick={() => setViewMode("timeline")}
                  className={`px-2 md:px-4 py-1 md:py-2 text-xs md:text-sm transition-colors ${
                    viewMode === "timeline"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-700 text-gray-300"
                  }`}
                >
                  Timeline
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main content area */}
        <div className="flex gap-2 md:gap-4 mt-2 md:mt-4">
          <div className="flex-1 h-[calc(100vh-200px)] md:h-[calc(100vh-280px)]">
            {!focusedDeviceId && !focusedCompanyName ? (
              // Empty state - prompt user to search
              <div className="w-full h-full bg-gray-900 rounded-lg flex items-center justify-center p-4">
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center gap-4 text-gray-500">
                    <img src={`${basePath}/loading.gif`} alt="Loading" className="w-48 h-48 md:w-64 md:h-64" />
                    <span className="text-base md:text-lg">Loading device database...</span>
                  </div>
                ) : (
                  <div className="text-center max-w-lg">
                    <div className="text-4xl md:text-6xl mb-4">🔍</div>
                    <h2 className="text-lg md:text-xl font-semibold text-white mb-2">
                      Search for a Device or Company
                    </h2>
                    <p className="text-gray-400 text-sm mb-6">
                      Enter a device name, 510(k) number, or manufacturer above.
                    </p>

                    {/* Featured companies */}
                    <div className="mb-6">
                      <p className="text-gray-500 text-xs mb-3 uppercase tracking-wide">Quick access</p>
                      <div className="flex flex-wrap justify-center gap-3 md:gap-5">
                        <button
                          onClick={() => handleCompanySelect("Fitbit, Inc.")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/fitbit.png`} alt="Fitbit" className="h-5 md:h-12 w-auto" />
                        </button>
                        <button
                          onClick={() => handleCompanySelect("Apple, Inc.")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/apple.png`} alt="Apple" className="h-5 md:h-12 w-auto invert" />
                          <span className="text-white text-sm md:text-xl font-medium">Apple</span>
                        </button>
                        <button
                          onClick={() => handleCompanySelect("Theranos, Inc.")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/theranos.png`} alt="Theranos" className="h-4 md:h-10 w-auto invert" />
                        </button>
                        <button
                          onClick={() => handleCompanySelect("Whiterabbit.Ai, Inc.")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/whiterabbit.png`} alt="Whiterabbit AI" className="h-5 md:h-12 w-auto" />
                        </button>
                        <button
                          onClick={() => handleCompanySelect("Three Palm Software, LLC")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/threepalm.png`} alt="Three Palm Software" className="h-5 md:h-12 w-auto" />
                        </button>
                        <button
                          onClick={() => handleCompanySelect("Masimo Corporation")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/masimo.png`} alt="Masimo" className="h-5 md:h-12 w-auto" />
                        </button>
                        <button
                          onClick={() => handleCompanySelect("Roche Diagnostic Systems, Inc.")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/roche.png`} alt="Roche" className="h-5 md:h-12 w-auto" />
                        </button>
                        <button
                          onClick={() => handleCompanySelect("Erad, Inc.")}
                          className="flex items-center gap-2 md:gap-4 px-4 md:px-8 py-2 md:py-6 bg-gray-800 hover:bg-gray-700 active:bg-gray-600 rounded-lg md:rounded-2xl border border-gray-700 transition-colors"
                        >
                          <img src={`${basePath}/logos/erad.webp`} alt="Erad" className="h-5 md:h-12 w-auto" />
                        </button>
                      </div>
                    </div>

                    {data && (
                      <p className="text-gray-500 text-xs">
                        {data.metadata.total_nodes.toLocaleString()} devices ready to explore
                      </p>
                    )}
                  </div>
                )}
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
            onNavigateToDevice={handleNavigateToDevice}
            showMobilePanel={showMobilePanel}
            onShowMobilePanel={() => setShowMobilePanel(true)}
          />
        </div>

        {/* Footer - hidden on mobile */}
        <footer className="mt-4 text-center text-gray-500 text-xs hidden md:block">
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
