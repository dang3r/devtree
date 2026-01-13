'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import DeviceExplorer from "@/components/DeviceExplorer";
import TabNavigation, { Tab } from "@/components/TabNavigation";
import ProcessOverview from "@/components/ProcessOverview";
import Research from "@/components/Research";

export default function TabsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<Tab>('explorer');

  // Initialize tab from URL on mount
  useEffect(() => {
    const tabParam = searchParams?.get('tab');
    if (tabParam && ['explorer', 'process', 'research'].includes(tabParam)) {
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

  return (
    <div className="flex flex-col h-screen">
      <TabNavigation activeTab={activeTab} onTabChange={handleTabChange} />
      <div className="flex-1 overflow-auto">
        {activeTab === 'explorer' && <DeviceExplorer />}
        {activeTab === 'process' && <ProcessOverview />}
        {activeTab === 'research' && <Research />}
      </div>
    </div>
  );
}
