export interface Device {
  id: string;
  device_name: string;
  applicant: string;
  contact: string | null;
  decision_date: string;
  device_class: "1" | "2" | "3";
  product_code: string;
  advisory_committee: string;
  specialty: string;
  date_received: string;
  decision_description: string;
  clearance_type: string;
  country_code: string;
  state: string;
  regulation_number: string;
}

export interface DeviceEdge {
  id: string;
  source: string;
  target: string;
  relationship: "predicate";
}

export interface CytoscapeNode {
  data: Device;
}

export interface CytoscapeEdge {
  data: DeviceEdge;
}

export interface CytoscapeGraphData {
  metadata: {
    generated_at: string;
    total_nodes: number;
    total_edges: number;
    nodes_with_predicates: number;
    nodes_without_predicates: number;
    orphan_predicates: number;
  };
  elements: {
    nodes: CytoscapeNode[];
    edges: CytoscapeEdge[];
  };
}
