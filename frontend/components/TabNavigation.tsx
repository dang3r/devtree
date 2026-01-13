'use client';

import React from 'react';

export type Tab = 'explorer' | 'process' | 'research';

interface TabNavigationProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export default function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  const tabs: { id: Tab; label: string; description: string }[] = [
    { id: 'explorer', label: 'Device Explorer', description: 'Interactive graph of 510(k) predicate relationships' },
    { id: 'process', label: 'Process Overview', description: 'Understanding the 510(k) clearance process' },
    { id: 'research', label: 'Research', description: 'Insights and analysis (coming soon)' },
  ];

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <nav className="flex space-x-8 overflow-x-auto" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                transition-colors duration-200
                ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
              aria-current={activeTab === tab.id ? 'page' : undefined}
            >
              <div className="flex flex-col items-start">
                <span>{tab.label}</span>
                <span className="text-xs font-normal text-gray-400 mt-0.5">
                  {tab.description}
                </span>
              </div>
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
