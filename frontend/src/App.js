import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import GraphCanvas from "./components/GraphCanvas";
import { buildGraphData, getNodeColor } from "./lib/graphBuilder";
import "./App.css";

const API = process.env.REACT_APP_API_URL || "";

const NODE_TYPE_LABELS = {
  SalesOrder: "Sales Order",
  Delivery: "Delivery",
  Billing: "Billing",
  JournalEntry: "Journal Entry",
  Payment: "Payment",
  Customer: "Customer",
  Product: "Product",
  Plant: "Plant",
};

const LEGEND_ITEMS = [
  { type: "SalesOrder", label: "Sales Order" },
  { type: "Delivery", label: "Delivery" },
  { type: "Billing", label: "Billing" },
  { type: "JournalEntry", label: "Journal Entry" },
  { type: "Payment", label: "Payment" },
  { type: "Customer", label: "Customer" },
];

function useContainerSize(ref) {
  const [size, setSize] = useState({
    width: typeof window !== "undefined" ? window.innerWidth : 1280,
    height: typeof window !== "undefined" ? window.innerHeight : 720,
  });

  useEffect(() => {
    if (!ref.current) return undefined;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      setSize({
        width: Math.max(320, Math.floor(entry.contentRect.width)),
        height: Math.max(420, Math.floor(entry.contentRect.height)),
      });
    });

    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);

  return size;
}

function EntityBadge({ type, small = false }) {
  const color = getNodeColor(type);
  return (
    <span className={`entity-badge${small ? " is-small" : ""}`} style={{ "--badge-color": color }}>
      {NODE_TYPE_LABELS[type] || type}
    </span>
  );
}

function FlowPath({ selectedNode, graphData }) {
  if (!selectedNode) return null;

  const connectedNodeIds = graphData.links
    .filter((link) => {
      const sourceId = typeof link.source === "object" ? link.source.id : link.source;
      const targetId = typeof link.target === "object" ? link.target.id : link.target;
      return sourceId === selectedNode.id || targetId === selectedNode.id;
    })
    .flatMap((link) => {
      const sourceId = typeof link.source === "object" ? link.source.id : link.source;
      const targetId = typeof link.target === "object" ? link.target.id : link.target;
      return [sourceId, targetId];
    })
    .filter((id) => id !== selectedNode.id);

  const uniqueConnectedNodes = [...new Set(connectedNodeIds)]
    .map((id) => graphData.nodes.find((node) => node.id === id))
    .filter(Boolean);

  const flowOrder = ["SalesOrder", "Delivery", "Billing", "JournalEntry", "Payment", "Customer", "Product", "Plant"];
  const sortedNodes = [...uniqueConnectedNodes].sort(
    (a, b) => flowOrder.indexOf(a.type) - flowOrder.indexOf(b.type)
  );

  return (
    <div className="flow-path">
      {[selectedNode, ...sortedNodes.slice(0, 4)].map((node, index, list) => (
        <React.Fragment key={node.id}>
          <EntityBadge type={node.type} small />
          {index < list.length - 1 && <span className="flow-arrow">→</span>}
        </React.Fragment>
      ))}
    </div>
  );
}

function TraceFlowCard({ steps }) {
  return (
    <div className="trace-card">
      <div className="trace-card__header">Document Flow</div>
      <div className="trace-card__body">
        {steps.map((step, index) => {
          const color = getNodeColor(step.type);
          return (
            <div key={`${step.id}-${index}`} className="trace-step">
              <div className="trace-step__rail">
                <span className="trace-step__dot" style={{ "--step-color": color }} />
                {index < steps.length - 1 && <span className="trace-step__line" />}
              </div>
              <div className="trace-step__content">
                <div className="trace-step__label">{step.label}</div>
                <div className="trace-step__id" style={{ "--step-color": color }}>
                  {step.id}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ResultModal({ rows, columns, onClose, onDownload }) {
  if (!rows.length) return null;

  return (
    <div className="results-modal-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="results-modal" onClick={(event) => event.stopPropagation()}>
        <div className="results-modal__header">
          <div>
            <div className="results-modal__eyebrow">Chat Results</div>
            <div className="results-modal__title">{rows.length} matching rows</div>
          </div>
          <div className="results-modal__actions">
            <button type="button" className="secondary-button" onClick={() => onDownload(rows)}>
              Download CSV
            </button>
            <button type="button" className="icon-button" onClick={onClose} aria-label="Close results">
              ×
            </button>
          </div>
        </div>
        <div className="results-modal__table-wrap">
          <table className="results-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`row-${rowIndex}`}>
                  {columns.map((column) => (
                    <td key={`${rowIndex}-${column}`}>
                      {row?.[column] === null || row?.[column] === undefined || row?.[column] === ""
                        ? "—"
                        : String(row[column])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const graphWrapRef = useRef(null);
  const chatEndRef = useRef(null);
  const { width, height } = useContainerSize(graphWrapRef);

  const [graphApiData, setGraphApiData] = useState({ nodes: [], edges: [], meta: {} });
  const [stats, setStats] = useState({});
  const [health, setHealth] = useState({ status: "loading" });
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! I can help you analyze the Order to Cash process." },
  ]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [highlightNodes, setHighlightNodes] = useState(new Set());
  const [showGranularOverlay, setShowGranularOverlay] = useState(true);
  const [chatOpen, setChatOpen] = useState(true);
  const [resultsModal, setResultsModal] = useState({ open: false, rows: [] });

  useEffect(() => {
    async function load() {
      const [graphRes, healthRes, statsRes] = await Promise.all([
        axios.get(`${API}/api/graph`),
        axios.get(`${API}/api/health`),
        axios.get(`${API}/api/stats`),
      ]);

      setGraphApiData(graphRes.data);
      setHealth(healthRes.data);
      setStats(statsRes.data || {});
    }

    load().catch(() => setHealth({ status: "offline" }));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  const graphData = useMemo(() => buildGraphData(graphApiData), [graphApiData]);

  const resultColumns = useMemo(() => {
    if (!resultsModal.rows.length) return [];
    const keys = new Set();
    resultsModal.rows.forEach((row) => Object.keys(row || {}).forEach((key) => keys.add(key)));
    return Array.from(keys);
  }, [resultsModal.rows]);

  const selectedNodeConnectionCount = useMemo(() => {
    if (!selectedNode) return 0;
    return graphData.links.filter((link) => {
      const sourceId = typeof link.source === "object" ? link.source.id : link.source;
      const targetId = typeof link.target === "object" ? link.target.id : link.target;
      return sourceId === selectedNode.id || targetId === selectedNode.id;
    }).length;
  }, [selectedNode, graphData.links]);

  async function sendMessage() {
    if (!input.trim() || chatLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((current) => [...current, { role: "user", text: userMessage }]);
    setChatLoading(true);

    try {
      const response = await axios.post(`${API}/api/chat`, { query: userMessage });
      const payload = response.data;

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: payload.answer,
          data: payload.data || [],
          traceFlow: payload.trace_flow || null,
        },
      ]);

      const newExtraNodes = payload.extra_nodes || [];
      if (newExtraNodes.length) {
        setGraphApiData((previous) => {
          const existingIds = new Set((previous.nodes || []).map((node) => node.id));
          const additions = newExtraNodes.filter((node) => !existingIds.has(node.id));
          if (!additions.length) return previous;

          return {
            ...previous,
            nodes: [
              ...(previous.nodes || []),
              ...additions.map((node) => ({
                ...node,
                x: (Math.random() - 0.5) * 1000,
                y: (Math.random() - 0.5) * 1000,
              })),
            ],
          };
        });
      }

      const existingIds = (payload.highlighted_ids || []).flatMap((docId) =>
        graphData.nodes
          .filter((node) => node.docId === docId || node.id === docId)
          .map((node) => node.id)
      );

      setHighlightNodes(new Set([...existingIds, ...newExtraNodes.map((node) => node.id)]));
      setChatOpen(true);
    } catch {
      setMessages((current) => [
        ...current,
        { role: "assistant", text: "Error reaching the server. Please make sure the backend is running." },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  function downloadCSV(rows) {
    if (!rows.length) return;

    const columns = Object.keys(rows[0] || {});
    const header = columns.join(",");
    const body = rows.map((row) => columns.map((column) => JSON.stringify(row[column] ?? "")).join(",")).join("\n");
    const blob = new Blob([`${header}\n${body}`], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `dodge-ai-results-${Date.now()}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const statCards = [
    { label: "Sales Orders", value: stats.sales_orders ?? 0, color: getNodeColor("SalesOrder") },
    { label: "Deliveries", value: stats.deliveries ?? 0, color: getNodeColor("Delivery") },
    { label: "Billing Docs", value: stats.billing_docs ?? 0, color: getNodeColor("Billing") },
    { label: "Journal Entries", value: stats.journal_entries ?? 0, color: getNodeColor("JournalEntry") },
    { label: "Payments", value: stats.payments ?? 0, color: getNodeColor("Payment") },
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">AI</div>
          <div>
            <div className="brand-title">Dodge AI</div>
            <div className="brand-subtitle">O2C Graph Explorer</div>
          </div>
        </div>

        <div className="topbar-divider" />

        <div className="stats-strip">
          {statCards.map((card) => (
            <div key={card.label} className="stat-pill" style={{ "--pill-color": card.color }}>
              <span className="stat-pill__dot" />
              <span className="stat-pill__value">{card.value}</span>
              <span className="stat-pill__label">{card.label}</span>
            </div>
          ))}
        </div>

        <div className="topbar-actions">
          <div className="graph-counts">
            {graphData.nodes.length} nodes · {graphData.links.length} edges
          </div>
          <button
            type="button"
            className={`chip-button${showGranularOverlay ? " is-active" : ""}`}
            onClick={() => setShowGranularOverlay((value) => !value)}
          >
            {showGranularOverlay ? "Overlay On" : "Overlay Off"}
          </button>
          <button
            type="button"
            className="chip-button"
            onClick={() => {
              setHighlightNodes(new Set());
              setSelectedNode(null);
            }}
          >
            Clear
          </button>
          <button type="button" className="primary-button" onClick={() => setChatOpen((value) => !value)}>
            {chatOpen ? "Close Chat" : "Open Chat"}
          </button>
        </div>
      </header>

      <main className="workspace">
        <section className="graph-panel">
          <div className="graph-surface" ref={graphWrapRef}>
            <GraphCanvas
              graphData={graphData}
              highlightNodes={highlightNodes}
              onNodeClick={setSelectedNode}
              width={width}
              height={height}
              showGranularOverlay={showGranularOverlay}
            />

            <aside className="legend-card">
              <div className="card-eyebrow">Entity Types</div>
              <div className="legend-list">
                {LEGEND_ITEMS.map((item) => (
                  <div key={item.type} className="legend-row">
                    <span className="legend-row__dot" style={{ backgroundColor: getNodeColor(item.type) }} />
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
            </aside>

            {selectedNode && (
              <aside className="detail-card">
                <div className="detail-card__header">
                  <div>
                    <EntityBadge type={selectedNode.type} />
                    <div className="detail-card__title">{selectedNode.label}</div>
                    <div className="detail-card__meta">{selectedNodeConnectionCount} connected edges</div>
                  </div>
                  <button
                    type="button"
                    className="icon-button"
                    onClick={() => setSelectedNode(null)}
                    aria-label="Close details"
                  >
                    ×
                  </button>
                </div>

                <div className="detail-card__section">
                  <div className="card-eyebrow">Flow</div>
                  <FlowPath selectedNode={selectedNode} graphData={graphData} />
                </div>

                <div className="detail-card__section">
                  <div className="card-eyebrow">Properties</div>
                  <div className="detail-grid">
                    {Object.entries(selectedNode.properties || {})
                      .filter(([, value]) => value !== null && value !== "")
                      .map(([key, value]) => (
                        <div key={key} className="detail-grid__row">
                          <span className="detail-grid__key">{key}</span>
                          <span className="detail-grid__value">{String(value)}</span>
                        </div>
                      ))}
                  </div>
                </div>
              </aside>
            )}
          </div>
        </section>

        <aside className={`chat-panel${chatOpen ? " is-open" : ""}`}>
          <div className="chat-header">
            <div className="chat-avatar">AI</div>
            <div>
              <div className="chat-title">Dodge AI</div>
              <div className="chat-status">
                <span className={`chat-status__dot${health.status === "ok" ? " is-online" : ""}`} />
                {health.status === "ok" ? "Online" : "Connecting..."}
              </div>
            </div>
          </div>

          <div className="chat-messages">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`message-row is-${message.role}`}>
                {message.role === "assistant" && <div className="message-avatar">AI</div>}
                <div className="message-bubble">
                  <div>{message.text}</div>
                  {!!message.traceFlow?.length && <TraceFlowCard steps={message.traceFlow} />}
                  {!!message.data?.length && (
                    <div className="message-actions">
                      <button
                        type="button"
                        className="outline-button"
                        onClick={() => setResultsModal({ open: true, rows: message.data })}
                      >
                        View {message.data.length} results
                      </button>
                      {message.data.length > 1 && (
                        <button type="button" className="ghost-button" onClick={() => downloadCSV(message.data)}>
                          Download CSV
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {chatLoading && (
              <div className="message-row is-assistant">
                <div className="message-avatar">AI</div>
                <div className="typing-indicator">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          <div className="chat-input-wrap">
            <div className="chat-input-box">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Ask about the O2C process..."
                rows={2}
              />
              <button
                type="button"
                className="send-button"
                onClick={sendMessage}
                disabled={chatLoading || !input.trim()}
                aria-label="Send message"
              >
                ▶
              </button>
            </div>
          </div>
        </aside>
      </main>

      {resultsModal.open && (
        <ResultModal
          rows={resultsModal.rows}
          columns={resultColumns}
          onClose={() => setResultsModal({ open: false, rows: [] })}
          onDownload={downloadCSV}
        />
      )}
    </div>
  );
}
