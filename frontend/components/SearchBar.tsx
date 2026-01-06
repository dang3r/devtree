"use client";

import { useState, useEffect, useRef } from "react";
import type { CytoscapeNode } from "@/types/device";

interface SearchBarProps {
  searchResults: CytoscapeNode[];
  onSearchChange: (query: string) => void;
  onDeviceSelect: (deviceId: string) => void;
  selectedDeviceId: string | null;
  highlightMode: "none" | "ancestors" | "descendants";
  onHighlightModeChange: (mode: "none" | "ancestors" | "descendants") => void;
  hasSelection: boolean;
}

export default function SearchBar({
  searchResults,
  onSearchChange,
  onDeviceSelect,
  selectedDeviceId,
  highlightMode,
  onHighlightModeChange,
  hasSelection,
}: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounced search
  useEffect(() => {
    const timeout = setTimeout(() => {
      onSearchChange(query);
      setShowDropdown(query.length >= 2);
    }, 200);
    return () => clearTimeout(timeout);
  }, [query, onSearchChange]);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleDeviceClick = (deviceId: string) => {
    onDeviceSelect(deviceId);
    setShowDropdown(false);
    setQuery("");
  };

  const getClassBadge = (deviceClass: string) => {
    const colors: Record<string, string> = {
      "1": "bg-green-600",
      "2": "bg-amber-600",
      "3": "bg-red-600",
    };
    return (
      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${colors[deviceClass] || "bg-gray-600"}`}>
        {deviceClass}
      </span>
    );
  };

  return (
    <div className="flex items-center gap-4 p-4 bg-gray-800 rounded-lg">
      <div className="flex-1 relative" ref={dropdownRef}>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query.length >= 2 && setShowDropdown(true)}
          placeholder="Search devices by name, ID, or manufacturer..."
          className="w-full px-4 py-2 bg-gray-700 text-white rounded-md border border-gray-600 focus:border-blue-500 focus:outline-none"
        />

        {/* Search Results Dropdown */}
        {showDropdown && (
          <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-gray-800 border border-gray-600 rounded-md shadow-lg max-h-96 overflow-y-auto">
            {searchResults.length === 0 ? (
              <div className="px-4 py-3 text-gray-400 text-sm">
                No devices found matching "{query}"
              </div>
            ) : (
              <>
                <div className="px-4 py-2 text-xs text-gray-500 border-b border-gray-700">
                  {searchResults.length} result{searchResults.length !== 1 ? "s" : ""} - click to explore
                </div>
                {searchResults.map((node) => (
                  <button
                    key={node.data.id}
                    onClick={() => handleDeviceClick(node.data.id)}
                    className="w-full px-4 py-3 text-left hover:bg-gray-700 border-b border-gray-700 last:border-b-0 transition-colors"
                  >
                    <div className="flex items-start gap-2">
                      {getClassBadge(node.data.device_class)}
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-white truncate">
                          {node.data.device_name}
                        </div>
                        <div className="text-sm text-gray-400 flex items-center gap-2">
                          <span className="font-mono">{node.data.id}</span>
                          <span className="text-gray-600">•</span>
                          <span className="truncate">{node.data.applicant}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Highlight mode buttons - only show when a device is focused */}
      {selectedDeviceId && (
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-sm">Highlight:</span>
          <button
            onClick={() => onHighlightModeChange("none")}
            disabled={!hasSelection}
            className={`px-3 py-1 rounded text-sm ${
              highlightMode === "none"
                ? "bg-blue-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            None
          </button>
          <button
            onClick={() => onHighlightModeChange("ancestors")}
            disabled={!hasSelection}
            className={`px-3 py-1 rounded text-sm ${
              highlightMode === "ancestors"
                ? "bg-purple-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            Ancestors
          </button>
          <button
            onClick={() => onHighlightModeChange("descendants")}
            disabled={!hasSelection}
            className={`px-3 py-1 rounded text-sm ${
              highlightMode === "descendants"
                ? "bg-purple-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            Descendants
          </button>
        </div>
      )}
    </div>
  );
}
