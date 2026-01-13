'use client';

import React from 'react';

export default function Research() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-4">
            Research & Insights
          </h1>
          <p className="text-lg text-gray-400 mb-8">
            Exploring interesting questions and patterns in the 510(k) device graph
          </p>
        </div>

        {/* Coming Soon Badge */}
        <div className="inline-flex items-center px-4 py-2 rounded-full bg-purple-900/50 text-purple-300 text-sm font-medium mb-8">
          <svg
            className="w-5 h-5 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          Coming Soon
        </div>

        {/* Future Ideas */}
        <div className="bg-gray-800 rounded-lg p-8 text-left">
          <h2 className="text-xl font-semibold text-gray-200 mb-4">
            Potential Research Questions
          </h2>
          <p className="text-gray-400 mb-4">
            This section will explore interesting questions and insights derived from the 510(k) predicate graph:
          </p>
          <ul className="space-y-3 text-gray-300">
            <li className="flex items-start">
              <span className="text-purple-400 mr-2">•</span>
              <span>Which devices have the most descendants (most frequently used as predicates)?</span>
            </li>
            <li className="flex items-start">
              <span className="text-purple-400 mr-2">•</span>
              <span>What are the longest predicate chains in medical device history?</span>
            </li>
            <li className="flex items-start">
              <span className="text-purple-400 mr-2">•</span>
              <span>How do different device specialties compare in their predicate patterns?</span>
            </li>
            <li className="flex items-start">
              <span className="text-purple-400 mr-2">•</span>
              <span>Which companies are most influential in establishing predicate devices?</span>
            </li>
            <li className="flex items-start">
              <span className="text-purple-400 mr-2">•</span>
              <span>How has device innovation evolved over time across different risk classes?</span>
            </li>
            <li className="flex items-start">
              <span className="text-purple-400 mr-2">•</span>
              <span>What are the common patterns in successful 510(k) submissions?</span>
            </li>
            <li className="flex items-start">
              <span className="text-purple-400 mr-2">•</span>
              <span>Which devices have no predicates (potential first-in-class innovations)?</span>
            </li>
          </ul>
        </div>

        {/* Placeholder for future visualizations */}
        <div className="mt-8 bg-gray-900 border-2 border-dashed border-gray-700 rounded-lg p-8">
          <svg
            className="mx-auto h-12 w-12 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-300">
            Interactive visualizations and analyses coming soon
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            This space will feature interactive charts, statistics, and deep dives into the graph data.
          </p>
        </div>
      </div>
    </div>
  );
}
