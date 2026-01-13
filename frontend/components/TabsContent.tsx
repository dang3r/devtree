'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import DeviceExplorer from "@/components/DeviceExplorer";
import TabNavigation, { Tab } from "@/components/TabNavigation";
import ProcessOverview from "@/components/ProcessOverview";
import Research from "@/components/Research";
import Contact from "@/components/Contact";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

export default function TabsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<Tab>('explorer');

  // Initialize tab from URL on mount
  useEffect(() => {
    const tabParam = searchParams?.get('tab');
    if (tabParam && ['contact', 'explorer', 'process', 'research'].includes(tabParam)) {
      setActiveTab(tabParam as Tab);
    }
  }, [searchParams]);

  // Update URL when tab changes
  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    // Update URL without full page reload
    const params = new URLSearchParams(searchParams?.toString() || '');
    params.set('tab', tab);
    router.push(`?${params.toString()}`, { scroll: false });
  };

  const handleLogoClick = () => {
    setActiveTab('explorer');
    router.push('/', { scroll: false });
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
        {activeTab === 'explorer' && <DeviceExplorer />}
        {activeTab === 'process' && <ProcessOverview />}
        {activeTab === 'research' && <Research />}
      </div>
    </div>
  );
}
