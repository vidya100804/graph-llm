export function normalizeType(type) {
  return type;
}

export function getNodeColor(type) {
  const colors = {
    SalesOrder: "#3B82F6",
    Delivery: "#22C55E",
    Billing: "#F59E0B",
    JournalEntry: "#A855F7",
    Payment: "#10B981",
    Customer: "#EC4899",
    Product: "#0EA5E9",
    Plant: "#EAB308",
  };
  return colors[type] || "#94A3B8";
}

function polarPoint(cx, cy, radius, angle) {
  return {
    x: cx + Math.cos(angle) * radius,
    y: cy + Math.sin(angle) * radius,
  };
}

function spread(nodes, cx, cy, radiusStart, radiusStep, angleStart, angleSweep, slotsPerRing = 22) {
  const total = Math.max(1, nodes.length);
  return nodes.map((node, index) => {
    const ring = Math.floor(index / slotsPerRing);
    const slot = index % slotsPerRing;
    const slotCount = Math.min(slotsPerRing, total - ring * slotsPerRing) || 1;
    const angle = angleStart + (slot / slotCount) * angleSweep;
    const radius = radiusStart + ring * radiusStep;
    return {
      ...node,
      ...polarPoint(cx, cy, radius, angle),
    };
  });
}

function buildAdjacency(apiGraph) {
  const adjacency = new Map();
  const degree = new Map();

  for (const node of apiGraph?.nodes || []) {
    adjacency.set(node.id, new Set());
    degree.set(node.id, 0);
  }

  for (const edge of apiGraph?.edges || []) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set());
    adjacency.get(edge.source).add(edge.target);
    adjacency.get(edge.target).add(edge.source);
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
  }

  return { adjacency, degree };
}

function positionNodes(apiGraph, nodes) {
  const count = nodes.length;

  // Spread nodes out in a large initial circle so they don't start tangled
  // This helps D3 sort them out cleanly into a well-spaced UI
  return nodes.map((node, i) => {
    const angle = (i / count) * Math.PI * 2;
    // Spawn between 50 and 400 radius
    const r = 50 + Math.random() * 350;
    return {
      ...node,
      degree: apiGraph.edges.filter(e => e.source === node.id || e.target === node.id).length,
      x: Math.cos(angle) * r,
      y: Math.sin(angle) * r,
    };
  });
}


export function buildGraphData(apiGraph) {
  const baseNodes = (apiGraph?.nodes || []).map((node) => ({
    id: node.id,
    label: node.label,
    type: normalizeType(node.type),
    docId: node.doc_id,
    properties: node.properties || {},
  }));

  const nodes = positionNodes(apiGraph, baseNodes);

  const links = (apiGraph?.edges || []).map((edge, index) => ({
    id: `${edge.source}-${edge.target}-${edge.label}-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.label,
  }));

  return { nodes, links };
}
