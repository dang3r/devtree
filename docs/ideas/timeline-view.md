# Design Spec: Timeline View for Device Graph

## Overview

Add an alternative visualization mode for device subgraphs that displays nodes on a temporal axis, making it easy to see when devices were cleared and how predicate relationships evolved over time.

## User Flow

1. User searches and selects a device (existing flow)
2. Subgraph loads in **Graph View** (existing dagre layout)
3. User clicks **Timeline View** tab to switch layouts
4. Same nodes/edges, but positioned by decision date

## Layout Design

```
         1985        1990        1995        2000        2005
         ─────────────────────────────────────────────────────►

Depth 0  ●──────────────────────────────────────────────────────
         │
Depth 1  └──────●───────────●───────────────────────────────────
                │           │
Depth 2         └─────●─────┴──────●────────●───────────────────
                      │            │        │
Depth 3               └────────────┴────●───┴──────●────●───────
```

- **X-axis**: Time (decision_date), left = oldest, right = newest
- **Y-axis**: Depth in predicate tree (0 = root/selected device's oldest ancestor)
- **Edges**: Bezier curves connecting parent → child

## UI Components

### View Toggle
- Tab buttons above the graph: `[Graph View] [Timeline View]`
- Active tab highlighted
- Switching snaps to new layout (no animation)

### Timeline Axis
- Horizontal axis at top or bottom showing years
- Tick marks at reasonable intervals (auto-scaled based on date range)
- Optional: vertical gridlines for decades

### Nodes
- Same styling as graph view (color by device class, size by selection state)
- Labels below nodes (may need collision detection or hide at low zoom)

### Interactions
- Same as graph view:
  - Click node to select → shows in DevicePanel
  - Highlight ancestors/descendants modes work the same
  - Pan and zoom

## Technical Approach

Custom Cytoscape layout that positions nodes based on:
- `x = scale(decision_date)`
- `y = depth * rowHeight`

Reuses existing Cytoscape infrastructure, edges "just work".

## Files to Modify

- `frontend/components/DeviceGraph.tsx` - Add layout toggle, implement timeline layout
- `frontend/app/page.tsx` - Add view mode state, pass to DeviceGraph
- `frontend/lib/graph-utils.ts` - Add depth calculation utility

## Future Enhancements (not in v1)

- Animated playback through time
- Time range filter slider
- Swimlanes by company/product code
- Smooth animation when switching views

## Status

In progress.
