"use client";

import type { Device } from "@/types/device";
import { getDeviceClassLabel } from "@/lib/graph-utils";

interface DevicePanelProps {
  device: Device | null;
  onClose: () => void;
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


  // If the Knumber is < K02*, it uses the old format
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

export default function DevicePanel({ device, onClose }: DevicePanelProps) {
  if (!device) {
    return (
      <div className="w-80 bg-gray-800 p-4 rounded-lg flex-shrink-0">
        <p className="text-gray-400 text-center">
          Select a device to view details
        </p>
        <p className="text-gray-500 text-xs text-center mt-2">
          Click on any node in the graph, or use search to find a device
        </p>
      </div>
    );
  }

  return (
    <div className="w-80 bg-gray-800 p-4 rounded-lg flex-shrink-0 overflow-y-auto max-h-[calc(100vh-220px)]">
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
    </div>
  );
}
