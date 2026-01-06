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
      </div>
    </div>
  );
}
