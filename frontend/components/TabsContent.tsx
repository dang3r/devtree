'use client';

import { useState, useEffect } from 'react';
import DeviceExplorer from "@/components/DeviceExplorer";
import TabNavigation, { Tab } from "@/components/TabNavigation";
import ProcessOverview from "@/components/ProcessOverview";
import Research from "@/components/Research";
import Contact from "@/components/Contact";
import type { CytoscapeGraphData } from "@/types/device";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
const dataUrl = process.env.NEXT_PUBLIC_DATA_URL || `${basePath}/cytoscape_graph.json`;

// Map URL paths to tabs
const pathToTab: Record<string, Tab> = {
  '/background': 'process',
  '/research': 'research',
  '/contact': 'contact',
};

// Map tabs to URL paths
const tabToPath: Record<Tab, string> = {
  'explorer': '/',
  'process': '/background/',
  'research': '/research/',
  'contact': '/contact/',
};

// Parse URL and return tab, deviceId, companyName
function parseUrl(path: string): { tab: Tab; deviceId: string | null; companyName: string | null } {
  const normalizedPath = path.replace(basePath, "").replace(/\/$/, "") || "/";

  // Check for tab routes first
  const matchedTab = pathToTab[normalizedPath];
  if (matchedTab) {
    return { tab: matchedTab, deviceId: null, companyName: null };
  }

  // Check for device/company routes (explorer tab)
  const deviceMatch = normalizedPath.match(/^\/device\/([^/?]+)/);
  const companyMatch = normalizedPath.match(/^\/company\/([^/?]+)/);

  if (deviceMatch) {
    return { tab: 'explorer', deviceId: decodeURIComponent(deviceMatch[1]), companyName: null };
  } else if (companyMatch) {
    return { tab: 'explorer', deviceId: null, companyName: decodeURIComponent(companyMatch[1]) };
  }

  return { tab: 'explorer', deviceId: null, companyName: null };
}

// Get initial state from URL (runs on client only)
function getInitialState() {
  if (typeof window === 'undefined') {
    return { tab: 'explorer' as Tab, deviceId: null, companyName: null };
  }
  return parseUrl(window.location.pathname);
}

// Update URL without triggering navigation (for SPA static export)
function updateUrl(path: string) {
  window.history.pushState({}, '', path);
}

export default function TabsContent() {
  // Track if we're mounted on the client
  const [mounted, setMounted] = useState(false);

  // Single state object to avoid multiple re-renders
  const [state, setState] = useState(getInitialState);
  const { tab: activeTab, deviceId, companyName } = state;

  // Graph data - loaded once and shared across all DeviceExplorer renders
  const [graphData, setGraphData] = useState<CytoscapeGraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError, setGraphError] = useState<string | null>(null);

  // Set mounted and correct state on client
  useEffect(() => {
    setState(parseUrl(window.location.pathname));
    setMounted(true);
  }, []);

  // Load graph data once on mount
  useEffect(() => {
    async function loadGraphData() {
      try {
        setGraphLoading(true);
        const response = await fetch(dataUrl);
        if (!response.ok) {
          throw new Error(`Failed to load graph data: ${response.status}`);
        }
        const data = await response.json();
        setGraphData(data);
      } catch (err) {
        setGraphError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setGraphLoading(false);
      }
    }
    loadGraphData();
  }, []);

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      const newState = parseUrl(window.location.pathname);
      setState(newState);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Don't render until mounted to avoid hydration mismatch flash
  if (!mounted) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-950">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  // Update URL when tab changes
  const handleTabChange = (tab: Tab) => {
    setState({ tab, deviceId: null, companyName: null });
    updateUrl(tabToPath[tab]);
  };

  const handleLogoClick = () => {
    setState({ tab: 'explorer', deviceId: null, companyName: null });
    updateUrl('/');
  };

  return (
    <div className="flex flex-col h-screen bg-gray-950">
      {/* Header with logo and tabs */}
      <header className="p-2 md:p-4">
        <div className="flex items-center gap-4">
          <h1
            className="flex items-center gap-2 text-lg md:text-2xl font-bold text-white cursor-pointer hover:text-blue-400 transition-colors"
            onClick={handleLogoClick}
          >
            <img src={`${basePath}/devtree.png`} alt="DevTree" className="h-6 md:h-8 w-auto" />
            DevTree
          </h1>
          <TabNavigation activeTab={activeTab} onTabChange={handleTabChange} />
        </div>
      </header>
      <div className="flex-1 overflow-auto">
        {activeTab === 'contact' && <Contact />}
        {activeTab === 'explorer' && (
          <DeviceExplorer
            initialDeviceId={deviceId}
            initialCompanyName={companyName}
            graphData={graphData}
            isLoading={graphLoading}
            error={graphError}
          />
        )}
        {activeTab === 'process' && <ProcessOverview />}
        {activeTab === 'research' && <Research />}
      </div>
    </div>
  );
}
