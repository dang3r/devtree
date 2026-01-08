"use client";

import { useState } from "react";
import type { Device } from "@/types/device";
import { getDeviceClassLabel } from "@/lib/graph-utils";

interface DevicePanelProps {
  device: Device | null;
  onClose: () => void;
  onNavigateToDevice?: (deviceId: string) => void;
  showMobilePanel?: boolean;
  onShowMobilePanel?: () => void;
}

function getDeviceClassBadgeColor(deviceClass: string): string {
  switch (deviceClass) {
    case "3":
      return "bg-red-500";
    case "2":
      return "bg-amber-500";
    case "1":
      return "bg-green-500";
    default:
      return "bg-gray-500";
  }
}

function getPdfUrl(kNumber: string, date: string): string {
  if (kNumber.startsWith("DEN")) {
    return `https://www.accessdata.fda.gov/cdrh_docs/reviews/${kNumber}.pdf`;
  }

  const year_prefix = parseInt(kNumber.slice(1, 3), 10);
  if (year_prefix < 2 || year_prefix > 30) {
    return `https://www.accessdata.fda.gov/cdrh_docs/pdf/${kNumber}.pdf`;
  }
  return `https://www.accessdata.fda.gov/cdrh_docs/pdf${year_prefix}/${kNumber}.pdf`;
}

function getDatabaseUrl(kNumber: string): string {
  if (kNumber.startsWith("DEN")) {
    return `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/denovo.cfm?id=${kNumber}`;
  }
  return `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=${kNumber}`;
}

export default function DevicePanel({ device, onClose, onNavigateToDevice, showMobilePanel = false, onShowMobilePanel }: DevicePanelProps) {
  // Empty state - hide on mobile, show placeholder on desktop
  if (!device) {
    return (
      <div className="hidden md:block w-80 bg-gray-800 p-4 rounded-lg flex-shrink-0">
        <p className="text-gray-400 text-center">
          Select a device to view details
        </p>
        <p className="text-gray-500 text-xs text-center mt-2">
          Click on any node in the graph
        </p>
      </div>
    );
  }

  return (
    <>
      {/* Mobile: Floating button to show details when panel is hidden */}
      {!showMobilePanel && onShowMobilePanel && (
        <button
          onClick={onShowMobilePanel}
          className="md:hidden fixed bottom-4 right-4 z-40 px-4 py-3 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 rounded-full text-white text-sm font-medium shadow-lg flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          View details
        </button>
      )}

      {/* Mobile: Bottom sheet overlay - only show when showMobilePanel is true */}
      {showMobilePanel && (
        <>
          <div className="md:hidden fixed inset-0 z-40" onClick={onClose}>
            <div className="absolute inset-0 bg-black/50" />
          </div>
          <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-gray-800 rounded-t-2xl p-3 max-h-[50vh] overflow-y-auto">
            <div className="w-10 h-1 bg-gray-600 rounded-full mx-auto mb-3" />
            <MobilePanelContent device={device} onClose={onClose} onNavigateToDevice={onNavigateToDevice} />
          </div>
        </>
      )}

      {/* Desktop: Sidebar */}
      <div className="hidden md:block w-96 bg-gray-800 p-5 rounded-lg flex-shrink-0 overflow-y-auto max-h-[calc(100vh-220px)]">
        <DesktopPanelContent device={device} onClose={onClose} onNavigateToDevice={onNavigateToDevice} />
      </div>
    </>
  );
}

// Compact mobile panel with essential info and expandable details
function MobilePanelContent({ device, onClose, onNavigateToDevice }: { device: Device; onClose: () => void; onNavigateToDevice?: (deviceId: string) => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="space-y-3">
      {/* Header with name and close */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`px-1.5 py-0.5 rounded text-xs text-white ${getDeviceClassBadgeColor(device.device_class)}`}
            >
              {getDeviceClassLabel(device.device_class)}
            </span>
            <span className="text-gray-400 font-mono text-xs">{device.id}</span>
          </div>
          <h2 className="text-base font-semibold text-white leading-tight">
            {device.device_name}
          </h2>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white p-1"
          aria-label="Close panel"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Key info in compact grid */}
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <p className="text-gray-500 text-xs">Applicant</p>
          <p className="text-white truncate">{device.applicant}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs">Decision</p>
          <p className="text-white">{device.decision_date}</p>
        </div>
      </div>

      {/* Expandable details section */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-center gap-2 py-2 text-gray-400 hover:text-white text-sm border-t border-gray-700"
      >
        <span>{expanded ? "Hide details" : "Show more details"}</span>
        <svg
          className={`w-4 h-4 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="space-y-3 text-sm border-t border-gray-700 pt-3">
          {device.contact && (
            <div>
              <p className="text-gray-500 text-xs">Contact</p>
              <p className="text-white">{device.contact}</p>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-gray-500 text-xs">Product Code</p>
              <p className="text-white font-mono">{device.product_code}</p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">Specialty</p>
              <p className="text-white truncate">{device.specialty}</p>
            </div>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Decision Description</p>
            <p className="text-white">{device.decision_description}</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-gray-500 text-xs">Received</p>
              <p className="text-white">{device.date_received}</p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">Decided</p>
              <p className="text-white">{device.decision_date}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-gray-500 text-xs">Clearance Type</p>
              <p className="text-white">{device.clearance_type}</p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">Regulation</p>
              <p className="text-white font-mono">{device.regulation_number}</p>
            </div>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Location</p>
            <p className="text-white">{device.state}, {device.country_code}</p>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 pt-2 border-t border-gray-700">
        {onNavigateToDevice && (
          <button
            onClick={() => {
              onNavigateToDevice(device.id);
              onClose();
            }}
            className="flex-1 py-2 bg-green-600 hover:bg-green-700 active:bg-green-800 rounded text-white text-sm font-medium"
          >
            Focus
          </button>
        )}
        <button
          onClick={() => {
            const url = `${window.location.origin}/device/${device.id}`;
            navigator.clipboard.writeText(url);
          }}
          className="flex-1 py-2 bg-purple-600 hover:bg-purple-700 active:bg-purple-800 rounded text-white text-sm font-medium"
        >
          Share
        </button>
        <a
          href={getDatabaseUrl(device.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 rounded text-white text-sm font-medium text-center"
        >
          FDA
        </a>
        <a
          href={getPdfUrl(device.id, device.decision_date)}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-2 bg-gray-600 hover:bg-gray-500 active:bg-gray-400 rounded text-white text-sm font-medium text-center"
        >
          PDF
        </a>
      </div>
    </div>
  );
}

// Full desktop panel with all details
function DesktopPanelContent({ device, onClose, onNavigateToDevice }: { device: Device; onClose: () => void; onNavigateToDevice?: (deviceId: string) => void }) {
  return (
    <>
      <div className="flex justify-between items-start mb-4">
        <h2 className="text-lg font-semibold text-white leading-tight pr-2">
          {device.device_name}
        </h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white flex-shrink-0"
          aria-label="Close panel"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div className="space-y-3">
        <div>
          <span
            className={`inline-block px-2 py-1 rounded text-xs text-white ${getDeviceClassBadgeColor(device.device_class)}`}
          >
            {getDeviceClassLabel(device.device_class)}
          </span>
        </div>

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            510(k) Number
          </p>
          <p className="text-white font-mono">{device.id}</p>
        </div>

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            Applicant
          </p>
          <p className="text-white">{device.applicant}</p>
        </div>

        {device.contact && (
          <div>
            <p className="text-gray-400 text-xs uppercase tracking-wide">
              Contact
            </p>
            <p className="text-white">{device.contact}</p>
          </div>
        )}

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            Product Code
          </p>
          <p className="text-white font-mono">{device.product_code}</p>
        </div>

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            Specialty
          </p>
          <p className="text-white">{device.specialty}</p>
        </div>

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            Decision
          </p>
          <p className="text-white">{device.decision_description}</p>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <p className="text-gray-400 text-xs uppercase tracking-wide">
              Received
            </p>
            <p className="text-white text-sm">{device.date_received}</p>
          </div>
          <div>
            <p className="text-gray-400 text-xs uppercase tracking-wide">
              Decided
            </p>
            <p className="text-white text-sm">{device.decision_date}</p>
          </div>
        </div>

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            Clearance Type
          </p>
          <p className="text-white">{device.clearance_type}</p>
        </div>

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            Regulation
          </p>
          <p className="text-white font-mono text-sm">
            {device.regulation_number}
          </p>
        </div>

        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wide">
            Location
          </p>
          <p className="text-white">
            {device.state}, {device.country_code}
          </p>
        </div>

        <div className="pt-3 mt-3 border-t border-gray-700 space-y-2">
          {onNavigateToDevice && (
            <button
              onClick={() => onNavigateToDevice(device.id)}
              className="flex items-center gap-2 text-green-400 hover:text-green-300 text-sm w-full"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              Focus on this device
            </button>
          )}
          <button
            onClick={() => {
              const url = `${window.location.origin}/device/${device.id}`;
              navigator.clipboard.writeText(url);
            }}
            className="flex items-center gap-2 text-purple-400 hover:text-purple-300 text-sm w-full"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
            Copy shareable link
          </button>
          <a
            href={getDatabaseUrl(device.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            View on FDA Database
          </a>
          <a
            href={getPdfUrl(device.id, device.decision_date)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            View Summary PDF
          </a>
        </div>
      </div>
    </>
  );
}
