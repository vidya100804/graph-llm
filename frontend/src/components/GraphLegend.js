import React from "react";
import { getNodeColor } from "../lib/graphBuilder";

const LEGEND_ITEMS = [
  { type: "SalesOrder", label: "Sales Order" },
  { type: "Delivery", label: "Delivery" },
  { type: "Billing", label: "Billing" },
  { type: "JournalEntry", label: "Journal Entry" },
  { type: "Payment", label: "Payment" },
  { type: "Customer", label: "Customer" },
  { type: "Product", label: "Product" },
  { type: "Plant", label: "Plant" },
];

export default function GraphLegend() {
  return (
    <div
      style={{
        background: "#FFFFFF",
        border: "1px solid #E7E7E3",
        borderRadius: 14,
        padding: "14px 16px",
        display: "flex",
        flexWrap: "wrap",
        gap: "10px 16px",
        boxShadow: "0 6px 18px rgba(0,0,0,0.04)",
        alignItems: "center",
      }}
    >
      <div style={{ width: "100%", fontSize: 12, letterSpacing: "0.08em", color: "#6B7280", fontWeight: 700 }}>
        ENTITY TYPES
      </div>
      {LEGEND_ITEMS.map((item) => (
        <div key={item.type} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              backgroundColor: getNodeColor(item.type),
              display: "inline-block",
            }}
          />
          <span style={{ fontSize: 11, color: "#6B7280" }}>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
