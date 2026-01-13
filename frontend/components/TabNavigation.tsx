'use client';

import React from 'react';

export type Tab = 'explorer' | 'process' | 'research';

interface TabNavigationProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export default function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  const tabs: { id: Tab; label: string; color: string; activeColor: string }[] = [
    { id: 'explorer', label: 'Explorer', color: 'text-gray-400 hover:text-blue-400', activeColor: 'text-blue-400' },
    { id: 'process', label: 'Process', color: 'text-gray-400 hover:text-green-400', activeColor: 'text-green-400' },
    { id: 'research', label: 'Research', color: 'text-gray-400 hover:text-purple-400', activeColor: 'text-purple-400' },
  ];

  return (
    <nav className="flex gap-4" aria-label="Tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`text-sm font-medium transition-colors ${
            activeTab === tab.id ? tab.activeColor : tab.color
          }`}
          aria-current={activeTab === tab.id ? 'page' : undefined}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
