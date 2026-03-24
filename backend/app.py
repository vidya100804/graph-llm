import json
import os
import re
import sqlite3

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_BUILD_DIR = os.path.join(PROJECT_DIR, "frontend", "build")

load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__, static_folder=FRONTEND_BUILD_DIR, static_url_path="/")
CORS(app)

DEFAULT_DB_PATH = os.path.join(BASE_DIR, "o2c_imported.db")
LEGACY_DB_PATH = os.path.join(BASE_DIR, "o2c.db")
DB_PATH = os.environ.get(
    "O2C_DB_PATH",
    DEFAULT_DB_PATH if os.path.exists(DEFAULT_DB_PATH) else LEGACY_DB_PATH,
)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_APP_NAME = os.environ.get("OPENROUTER_APP_NAME", "Dodge AI O2C Explorer")
OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "http://localhost:5000")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama3-8b-8192")

DOCUMENT_FIELDS = {
    "salesorder",
    "salesorderitem",
    "deliverydocument",
    "billingdocument",
    "accountingdocument",
    "referencedocument",
    "referencesddocument",
    "paymentdocument",
    "journalentry",
    "product",
    "material",
    "customer",
    "soldtoparty",
    "plant",
    "shippingpoint",
    "productionplant",
}

SCHEMA = """
You are Dodge AI, an intelligent data analyst assistant for an SAP Order-to-Cash (O2C) system.
If the user asks a question that requires querying the SAP database (e.g., searching orders, deliveries, billings, payments, customers, products), generate a valid SQLite SQL query starting exactly with 'SELECT'.
If the user asks a general question about you, your capabilities, or your tech stack (e.g. what API or LLM you use), respond directly in friendly natural language (do NOT start with 'SELECT').
Do not use markdown backticks for SQL queries.

DATABASE SCHEMA:
- sales_order_headers: salesOrder(PK), salesOrderType, salesOrganization, soldToParty, creationDate, totalNetAmount, overallDeliveryStatus, overallOrdReltdBillgStatus, transactionCurrency, requestedDeliveryDate, headerBillingBlockReason, deliveryBlockReason
- sales_order_items: salesOrder, salesOrderItem, material, requestedQuantity, netAmount, materialGroup, productionPlant, storageLocation, salesDocumentRjcnReason, itemBillingBlockReason, transactionCurrency
- outbound_delivery_headers: deliveryDocument(PK), creationDate, overallGoodsMovementStatus, overallPickingStatus, shippingPoint, deliveryBlockReason
- outbound_delivery_items: deliveryDocument, deliveryDocumentItem, referenceSdDocument(=salesOrder), referenceSdDocumentItem(=salesOrderItem), plant, storageLocation, actualDeliveryQuantity
- billing_document_headers: billingDocument(PK), billingDocumentType, creationDate, billingDocumentDate, billingDocumentIsCancelled, totalNetAmount, transactionCurrency, companyCode, fiscalYear, accountingDocument, soldToParty
- billing_document_items: billingDocument, billingDocumentItem, material, billingQuantity, netAmount, transactionCurrency, referenceSdDocument(=deliveryDocument in this imported dataset), referenceSdDocumentItem(=deliveryDocumentItem)
- journal_entries: accountingDocument, accountingDocumentItem, companyCode, fiscalYear, glAccount, referenceDocument(=billingDocument), transactionCurrency, amountInTransactionCurrency, postingDate, documentDate, accountingDocumentType, customer, clearingDate
- payments: accountingDocument, accountingDocumentItem, clearingDate, amountInTransactionCurrency, transactionCurrency, customer, postingDate, clearingAccountingDocument
- products: product(PK), productType, grossWeight, weightUnit, productGroup, baseUnit, division
- product_descriptions: product(PK), language, productDescription

KEY RELATIONSHIPS:
- sales_order_headers -> outbound_delivery_items via odi.referenceSdDocument = soh.salesOrder
- outbound_delivery_items -> outbound_delivery_headers via odi.deliveryDocument = odh.deliveryDocument
- outbound_delivery_headers -> billing_document_items via bdi.referenceSdDocument = odh.deliveryDocument
- billing_document_items -> billing_document_headers via bdi.billingDocument = bdh.billingDocument
- billing_document_headers -> journal_entries via je.referenceDocument = bdh.billingDocument
- billing_document_headers -> payments via p.accountingDocument = bdh.accountingDocument
- sales_order_items -> products via soi.material = products.product
- products -> product_descriptions via products.product = product_descriptions.product

STATUS NOTES:
- overallDeliveryStatus: A=Not started, B=Partial, C=Fully delivered
- overallOrdReltdBillgStatus: empty=Not billed, A=Not started, B=Partial, C=Fully billed

If querying the database, return ONLY the SQL starting with SELECT (Limit 50).
If answering a general question, return ONLY your natural language answer.
"""

DOMAIN_KEYWORDS = [
    "order",
    "orders",
    "delivery",
    "deliveries",
    "billing",
    "billings",
    "invoice",
    "invoices",
    "payment",
    "payments",
    "journal",
    "journals",
    "sales",
    "material",
    "materials",
    "product",
    "products",
    "plant",
    "plants",
    "customer",
    "customers",
    "partner",
    "partners",
    "document",
    "documents",
    "sap",
    "erp",
    "o2c",
    "amount",
    "quantity",
    "status",
    "flow",
    "trace",
    "highest",
    "lowest",
    "count",
    "shipped",
    "billed",
    "paid",
    "pending",
    "incomplete",
    "broken",
    "complete",
]

OFF_TOPIC_PATTERNS = [
    r"\b(weather|capital|president|recipe|movie|song|joke|poem|story|write me|explain.*history)\b",
    r"\b(what is \d+|calculate|solve|math|equation)\b",
    r"\b(who is|who was|famous|celebrity|sport|football|cricket)\b",
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def q(sql, params=()):
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def placeholders(items):
    return ",".join("?" for _ in items)


def is_domain_query(query):
    q_lower = query.lower()
    for pat in OFF_TOPIC_PATTERNS:
        if re.search(pat, q_lower):
            return False
    if find_document_id(query):
        return True
    compact = q_lower.replace("-", " ")
    return any(keyword in compact for keyword in DOMAIN_KEYWORDS)


def get_llm_config():
    preferred_provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    providers = []
    if preferred_provider:
        providers.append(preferred_provider)
    providers.extend(["openrouter", "groq"])

    seen = set()
    for provider in providers:
        if provider in seen:
            continue
        seen.add(provider)
        if provider == "openrouter" and OPENROUTER_API_KEY:
            return {
                "provider": "openrouter",
                "api_key": OPENROUTER_API_KEY,
                "url": OPENROUTER_URL,
                "model": OPENROUTER_MODEL,
                "extra_headers": {
                    "HTTP-Referer": OPENROUTER_SITE_URL,
                    "X-Title": OPENROUTER_APP_NAME,
                },
            }
        if provider == "groq" and GROQ_API_KEY:
            return {
                "provider": "groq",
                "api_key": GROQ_API_KEY,
                "url": GROQ_URL,
                "model": GROQ_MODEL,
                "extra_headers": {},
            }
    return None


def call_llm(system, user_msg):
    config = get_llm_config()
    if not config:
        return None, "No LLM API key configured"

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
        **config["extra_headers"],
    }
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0,
        "max_tokens": 500,
    }
    try:
        response = requests.post(config["url"], headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip(), None
    except Exception as exc:
        return None, str(exc)


def call_llm_answer(sql_result, original_question):
    system = """You are an SAP O2C data analyst.
Provide a clear, concise answer grounded only in the provided rows.
Be specific with numbers and identifiers when present.
If the result is empty, say no matching data was found.
Keep the response under 120 words."""
    user = f"Question: {original_question}\n\nData: {json.dumps(sql_result[:20])}"
    return call_llm(system, user)


def format_amount(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return str(value)


def extract_highlight_data(results):
    highlighted = []
    extra_nodes = []
    seen = set()
    for row in results[:30]:
        for key, value in row.items():
            if value is None:
                continue
            k_norm = key.lower().replace("_", "")
            val = str(value).strip()
            if not val or val in seen:
                continue
            
            node_type = None
            label_prefix = ""
            if k_norm in ("salesorder", "salesorderitem"):
                node_type, label_prefix = "SalesOrder", "SO"
            elif k_norm in ("deliverydocument",):
                node_type, label_prefix = "Delivery", "DEL"
            elif k_norm in ("billingdocument", "referencedocument", "referencesddocument"):
                node_type, label_prefix = "Billing", "BILL"
            elif k_norm in ("accountingdocument", "journalentry"):
                node_type, label_prefix = "JournalEntry", "JE"
            elif k_norm in ("paymentdocument", "clearingaccountingdocument"):
                node_type, label_prefix = "Payment", "PAY"
            elif k_norm in ("product", "material"):
                node_type, label_prefix = "Product", "PROD"
            elif k_norm in ("customer", "soldtoparty"):
                node_type, label_prefix = "Customer", "CUST"
            elif k_norm in ("plant", "shippingpoint", "productionplant"):
                node_type, label_prefix = "Plant", "PLANT"

            if node_type:
                seen.add(val)
                highlighted.append(val)
                extra_nodes.append({
                    "id": f"{node_type}:{val}",
                    "doc_id": val,
                    "label": f"{label_prefix} {val}",
                    "type": node_type,
                    "properties": row
                })
    return highlighted[:25], extra_nodes[:25]


def merge_highlight_payload(results, highlighted_ids=None, extra_nodes=None):
    auto_highlighted, auto_extra_nodes = extract_highlight_data(results)
    merged_ids = []
    merged_extra = []
    seen_ids = set()
    seen_extra = set()

    for value in (highlighted_ids or []) + auto_highlighted:
        value = str(value).strip()
        if value and value not in seen_ids:
            seen_ids.add(value)
            merged_ids.append(value)

    for node in (extra_nodes or []) + auto_extra_nodes:
        node_id = node.get("id")
        if node_id and node_id not in seen_extra:
            seen_extra.add(node_id)
            merged_extra.append(node)

    return merged_ids[:25], merged_extra[:25]


def make_chat_response(
    answer,
    data=None,
    sql=None,
    guardrail_triggered=False,
    trace_flow=None,
    highlighted_ids=None,
    extra_nodes=None,
):
    results = data or []
    h_ids, x_nodes = merge_highlight_payload(results, highlighted_ids, extra_nodes)
    return jsonify(
        {
            "answer": answer,
            "sql": sql,
            "data": results[:50],
            "highlighted_ids": h_ids,
            "extra_nodes": x_nodes,
            "guardrail_triggered": guardrail_triggered,
            "trace_flow": trace_flow or [],
        }
    )


def find_document_id(user_query):
    match = re.search(r"\b(\d{6,10})\b", user_query)
    return match.group(1) if match else None


def detect_document_types(doc_id):
    checks = [
        ("SalesOrder", "SELECT salesOrder AS id FROM sales_order_headers WHERE salesOrder = ? LIMIT 1"),
        ("Delivery", "SELECT deliveryDocument AS id FROM outbound_delivery_headers WHERE deliveryDocument = ? LIMIT 1"),
        ("Billing", "SELECT billingDocument AS id FROM billing_document_headers WHERE billingDocument = ? LIMIT 1"),
        ("JournalEntry", "SELECT accountingDocument AS id FROM journal_entries WHERE accountingDocument = ? LIMIT 1"),
        ("Payment", "SELECT accountingDocument AS id FROM payments WHERE accountingDocument = ? LIMIT 1"),
    ]
    found = []
    for label, sql in checks:
        if q(sql, (doc_id,)):
            found.append(label)
    return found


def build_not_found_answer(user_query, doc_id=None):
    query_lower = user_query.lower()
    if doc_id:
        found_types = detect_document_types(doc_id)
        if found_types:
            return (
                f"I couldn't match that exact request, but document {doc_id} exists in the dataset as "
                f"{', '.join(found_types)}. Try asking for its trace flow or linked documents."
            )
        return f"I couldn't find document {doc_id} anywhere in this dataset."

    if ("billing" in query_lower or "billed" in query_lower) and "without delivery" in query_lower:
        return "This result is valid for the current dataset: I found 0 billing documents without a linked delivery."

    if ("delivery" in query_lower or "deliveries" in query_lower) and "without billing" in query_lower:
        return "I didn't find any deliveries without linked billing in the current result set."

    return (
        "I didn't find matching rows for that question in this dataset. Try asking with a document ID, "
        "customer, status, date, amount, or a trace-flow question."
    )


def trace_flow_for_billing(doc_id):
    rows = q(
        """
        SELECT DISTINCT bdh.billingDocument, bdi.referenceSdDocument AS deliveryDocument,
               odi.referenceSdDocument AS salesOrder, je.accountingDocument AS journalEntry,
               p.accountingDocument AS paymentDocument, p.clearingAccountingDocument AS clearingDocument
        FROM billing_document_headers bdh
        LEFT JOIN billing_document_items bdi ON bdi.billingDocument = bdh.billingDocument
        LEFT JOIN outbound_delivery_items odi ON odi.deliveryDocument = bdi.referenceSdDocument
        LEFT JOIN journal_entries je ON je.referenceDocument = bdh.billingDocument
        LEFT JOIN payments p ON p.accountingDocument = bdh.accountingDocument
        WHERE bdh.billingDocument = ?
        LIMIT 20
        """,
        (doc_id,),
    )
    if not rows:
        return None

    row = rows[0]
    trace_flow = []
    highlighted_ids = []

    for key, label, entity_type in [
        ("salesOrder", "Sales Order", "SalesOrder"),
        ("deliveryDocument", "Delivery", "Delivery"),
        ("billingDocument", "Billing", "Billing"),
        ("journalEntry", "Journal Entry", "JournalEntry"),
        ("paymentDocument", "Payment", "Payment"),
    ]:
        value = row.get(key)
        if value:
            value = str(value)
            trace_flow.append({"type": entity_type, "label": label, "id": value})
            highlighted_ids.append(value)

    summary = []
    if row.get("salesOrder"):
        summary.append(f"sales order {row['salesOrder']}")
    if row.get("deliveryDocument"):
        summary.append(f"delivery {row['deliveryDocument']}")
    if row.get("journalEntry"):
        summary.append(f"journal entry {row['journalEntry']}")
    if row.get("paymentDocument"):
        summary.append(f"payment {row['paymentDocument']}")

    if summary:
        answer = f"Billing document {doc_id} is linked to " + ", ".join(summary) + "."
    else:
        answer = f"I found billing document {doc_id}, but I could not trace any downstream or upstream links."

    return make_chat_response(
        answer,
        rows,
        trace_flow=trace_flow,
        highlighted_ids=highlighted_ids,
    )


def trace_flow_for_sales_order(doc_id):
    rows = q(
        """
        SELECT DISTINCT soh.salesOrder, odi.deliveryDocument, bdh.billingDocument,
               je.accountingDocument AS journalEntry, p.accountingDocument AS paymentDocument
        FROM sales_order_headers soh
        LEFT JOIN outbound_delivery_items odi ON odi.referenceSdDocument = soh.salesOrder
        LEFT JOIN billing_document_items bdi ON bdi.referenceSdDocument = odi.deliveryDocument
        LEFT JOIN billing_document_headers bdh ON bdh.billingDocument = bdi.billingDocument
        LEFT JOIN journal_entries je ON je.referenceDocument = bdh.billingDocument
        LEFT JOIN payments p ON p.accountingDocument = bdh.accountingDocument
        WHERE soh.salesOrder = ?
        LIMIT 30
        """,
        (doc_id,),
    )
    if not rows:
        return None

    deliveries = sorted({str(row["deliveryDocument"]) for row in rows if row.get("deliveryDocument")})
    billings = sorted({str(row["billingDocument"]) for row in rows if row.get("billingDocument")})
    journals = sorted({str(row["journalEntry"]) for row in rows if row.get("journalEntry")})
    payments_found = sorted({str(row["paymentDocument"]) for row in rows if row.get("paymentDocument")})

    trace_flow = [{"type": "SalesOrder", "label": "Sales Order", "id": str(doc_id)}]
    highlighted_ids = [str(doc_id)]

    if deliveries:
        trace_flow.append({"type": "Delivery", "label": "Delivery", "id": deliveries[0]})
        highlighted_ids.extend(deliveries[:10])
    if billings:
        trace_flow.append({"type": "Billing", "label": "Billing", "id": billings[0]})
        highlighted_ids.extend(billings[:10])
    if journals:
        trace_flow.append({"type": "JournalEntry", "label": "Journal Entry", "id": journals[0]})
        highlighted_ids.extend(journals[:10])
    if payments_found:
        trace_flow.append({"type": "Payment", "label": "Payment", "id": payments_found[0]})
        highlighted_ids.extend(payments_found[:10])

    answer = (
        f"Sales order {doc_id} links to {len(deliveries)} delivery document(s), "
        f"{len(billings)} billing document(s), {len(journals)} journal entry document(s), "
        f"and {len(payments_found)} payment document(s)."
    )

    return make_chat_response(
        answer,
        rows,
        trace_flow=trace_flow,
        highlighted_ids=highlighted_ids,
    )


def graph_payload(limit_orders=None):
    sales_order_sql = """
        SELECT salesOrder, salesOrderType, soldToParty, totalNetAmount, transactionCurrency,
               creationDate, overallDeliveryStatus, overallOrdReltdBillgStatus
        FROM sales_order_headers
        ORDER BY creationDate DESC, salesOrder DESC
    """
    sales_orders = q(
        f"{sales_order_sql}\nLIMIT ?" if limit_orders else sales_order_sql,
        (limit_orders,) if limit_orders else (),
    )
    if not sales_orders:
        return {"nodes": [], "edges": [], "meta": {"sales_orders": 0}}

    sales_order_ids = [row["salesOrder"] for row in sales_orders]
    order_placeholder = placeholders(sales_order_ids)

    deliveries = q(
        f"""
        SELECT DISTINCT odh.deliveryDocument, odh.creationDate, odh.overallGoodsMovementStatus,
               odh.overallPickingStatus, odh.shippingPoint, odi.referenceSdDocument
        FROM outbound_delivery_items odi
        JOIN outbound_delivery_headers odh ON odh.deliveryDocument = odi.deliveryDocument
        WHERE odi.referenceSdDocument IN ({order_placeholder})
        ORDER BY odh.creationDate DESC, odh.deliveryDocument DESC
        """,
        tuple(sales_order_ids),
    )

    delivery_ids = [row["deliveryDocument"] for row in deliveries]
    billings = []
    journals = []
    payments = []
    if delivery_ids:
        delivery_placeholder = placeholders(delivery_ids)
        billings = q(
            f"""
            SELECT DISTINCT bdh.billingDocument, bdh.billingDocumentDate, bdh.totalNetAmount,
                   bdh.transactionCurrency, bdh.billingDocumentIsCancelled, bdh.accountingDocument,
                   bdi.referenceSdDocument AS referenceDeliveryDocument
            FROM billing_document_items bdi
            JOIN billing_document_headers bdh ON bdh.billingDocument = bdi.billingDocument
            WHERE bdi.referenceSdDocument IN ({delivery_placeholder})
            ORDER BY bdh.billingDocumentDate DESC, bdh.billingDocument DESC
            """,
            tuple(delivery_ids),
        )

    billing_ids = [row["billingDocument"] for row in billings]
    bd_items = []
    
    accounting_documents = [row["accountingDocument"] for row in billings if row.get("accountingDocument")]
    if billing_ids:
        billing_placeholder = placeholders(billing_ids)
        bd_items = q(
            f"""
            SELECT billingDocument, material
            FROM billing_document_items
            WHERE billingDocument IN ({billing_placeholder})
            """,
            tuple(billing_ids),
        )
        journals = q(
            f"""
            SELECT DISTINCT accountingDocument, referenceDocument, transactionCurrency,
                   amountInTransactionCurrency, postingDate, accountingDocumentType, customer
            FROM journal_entries
            WHERE referenceDocument IN ({billing_placeholder})
            ORDER BY postingDate DESC, accountingDocument DESC
            """,
            tuple(billing_ids),
        )
    if accounting_documents:
        accounting_placeholder = placeholders(accounting_documents)
        payments = q(
            f"""
            SELECT DISTINCT accountingDocument, clearingAccountingDocument, clearingDate,
                   amountInTransactionCurrency, transactionCurrency, customer, postingDate
            FROM payments
            WHERE accountingDocument IN ({accounting_placeholder})
            ORDER BY clearingDate DESC, accountingDocument DESC
            """,
            tuple(accounting_documents),
        )

    so_items = []
    if sales_order_ids:
        order_placeholder = placeholders(sales_order_ids)
        so_items = q(
            f"""
            SELECT salesOrder, material, productionPlant
            FROM sales_order_items
            WHERE salesOrder IN ({order_placeholder})
            """,
            tuple(sales_order_ids),
        )

    nodes = []
    edges = []
    node_map = {}
    edge_keys = set()

    def add_node(entity_type, record, key_field, label_prefix):
        raw_id = str(record[key_field])
        node_id = f"{entity_type}:{raw_id}"
        if node_id not in node_map:
            node = {
                "id": node_id,
                "doc_id": raw_id,
                "label": f"{label_prefix} {raw_id}",
                "type": entity_type,
                "properties": record,
            }
            node_map[node_id] = node
            nodes.append(node)
        return node_id

    def add_edge(source, target, label):
        edge_key = (source, target, label)
        if edge_key not in edge_keys:
            edge_keys.add(edge_key)
            edges.append({"source": source, "target": target, "label": label})

    sales_order_node_map = {}
    customer_node_map = {}
    plant_node_map = {}
    product_node_map = {}

    for row in sales_orders:
        so_node = add_node("SalesOrder", row, "salesOrder", "SO")
        sales_order_node_map[row["salesOrder"]] = so_node
        
        customer = row.get("soldToParty")
        if customer:
            if customer not in customer_node_map:
                customer_node_map[customer] = add_node("Customer", {"customer": customer}, "customer", "CUST")
            add_edge(customer_node_map[customer], so_node, "PLACED_ORDER")

    for item in so_items:
        so_node = sales_order_node_map.get(item["salesOrder"])
        if not so_node: continue
        
        material = item.get("material")
        if material:
            if material not in product_node_map:
                product_node_map[material] = add_node("Product", {"product": material}, "product", "PROD")
            add_edge(so_node, product_node_map[material], "INCLUDES_PRODUCT")
            
        plant = item.get("productionPlant")
        if plant:
            if plant not in plant_node_map:
                plant_node_map[plant] = add_node("Plant", {"plant": plant}, "plant", "PLANT")
            add_edge(so_node, plant_node_map[plant], "SOURCED_FROM")

    delivery_node_map = {}
    for row in deliveries:
        delivery_node_map[row["deliveryDocument"]] = add_node("Delivery", row, "deliveryDocument", "DEL")
        parent_order = row["referenceSdDocument"]
        if parent_order in sales_order_node_map:
            add_edge(sales_order_node_map[parent_order], delivery_node_map[row["deliveryDocument"]], "HAS_DELIVERY")

    billing_node_map = {}
    for row in billings:
        billing_node_map[row["billingDocument"]] = add_node("Billing", row, "billingDocument", "BILL")
        parent_delivery = row["referenceDeliveryDocument"]
        if parent_delivery in delivery_node_map:
            add_edge(delivery_node_map[parent_delivery], billing_node_map[row["billingDocument"]], "HAS_BILLING")

    for item in bd_items:
        bill_node = billing_node_map.get(item["billingDocument"])
        if not bill_node: continue
        
        material = item.get("material")
        if material:
            if material not in product_node_map:
                product_node_map[material] = add_node("Product", {"product": material}, "product", "PROD")
            add_edge(bill_node, product_node_map[material], "BILLED_PRODUCT")

    accounting_to_billing = {row["accountingDocument"]: row["billingDocument"] for row in billings if row.get("accountingDocument")}

    for row in journals:
        journal_node_id = add_node("JournalEntry", row, "accountingDocument", "JE")
        parent_billing = row["referenceDocument"]
        if parent_billing in billing_node_map:
            add_edge(billing_node_map[parent_billing], journal_node_id, "POSTED_TO")

    for row in payments:
        payment_node_id = add_node("Payment", row, "accountingDocument", "PAY")
        parent_billing = accounting_to_billing.get(row["accountingDocument"])
        if parent_billing in billing_node_map:
            add_edge(billing_node_map[parent_billing], payment_node_id, "PAID_BY")

    connected_node_ids = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
    connected_nodes = [node for node in nodes if node["id"] in connected_node_ids]

    meta = {
        "sales_orders": len([node for node in connected_nodes if node["type"] == "SalesOrder"]),
        "deliveries": len([node for node in connected_nodes if node["type"] == "Delivery"]),
        "billing_docs": len([node for node in connected_nodes if node["type"] == "Billing"]),
        "journal_entries": len([node for node in connected_nodes if node["type"] == "JournalEntry"]),
        "payments": len([node for node in connected_nodes if node["type"] == "Payment"]),
        "customers": len([node for node in connected_nodes if node["type"] == "Customer"]),
        "products": len([node for node in connected_nodes if node["type"] == "Product"]),
        "plants": len([node for node in connected_nodes if node["type"] == "Plant"]),
        "edges": len(edges),
    }
    return {"nodes": connected_nodes, "edges": edges, "meta": meta}


def run_builtin_query(user_query):
    query_lower = user_query.lower()
    doc_id = find_document_id(user_query)

    if ("billing" in query_lower or "billed" in query_lower) and "without delivery" in query_lower:
        rows = q(
            """
            SELECT DISTINCT bdh.billingDocument, bdh.billingDocumentDate, bdh.totalNetAmount,
                   bdh.transactionCurrency, bdh.soldToParty, bdh.accountingDocument
            FROM billing_document_headers bdh
            LEFT JOIN billing_document_items bdi ON bdi.billingDocument = bdh.billingDocument
            WHERE bdi.referenceSdDocument IS NULL
               OR TRIM(COALESCE(bdi.referenceSdDocument, '')) = ''
            ORDER BY bdh.billingDocumentDate DESC, bdh.billingDocument DESC
            LIMIT 50
            """
        )
        if rows:
            answer = f"I found {len(rows)} billing document(s) without a linked delivery in this result page."
        else:
            answer = "This result is valid for the current dataset: I found 0 billing documents without a linked delivery."
        return make_chat_response(answer, rows)

    if doc_id and "journal" in query_lower and "billing" in query_lower:
        rows = q(
            """
            SELECT bdh.billingDocument, bdh.accountingDocument, je.accountingDocument AS journalEntry,
                   je.postingDate, je.amountInTransactionCurrency, je.transactionCurrency
            FROM billing_document_headers bdh
            LEFT JOIN journal_entries je ON je.referenceDocument = bdh.billingDocument
            WHERE bdh.billingDocument = ?
            LIMIT 10
            """,
            (doc_id,),
        )
        if rows:
            journal_entry = rows[0]["journalEntry"]
            if journal_entry:
                answer = f"The journal entry linked to billing document {doc_id} is {journal_entry}."
            else:
                answer = f"Billing document {doc_id} exists, but I did not find a linked journal entry."
            return make_chat_response(answer, rows)
        return make_chat_response(build_not_found_answer(user_query, doc_id))

    if doc_id and ("trace" in query_lower or "flow" in query_lower):
        billing_trace = trace_flow_for_billing(doc_id)
        if billing_trace is not None:
            return billing_trace

        sales_order_trace = trace_flow_for_sales_order(doc_id)
        if sales_order_trace is not None:
            return sales_order_trace

        return make_chat_response(build_not_found_answer(user_query, doc_id))

    if "total billed amount" in query_lower or ("total" in query_lower and "billed" in query_lower and "amount" in query_lower):
        rows = q(
            """
            SELECT COUNT(*) AS billingDocuments,
                   ROUND(SUM(CAST(totalNetAmount AS REAL)), 2) AS totalBilledAmount,
                   MIN(transactionCurrency) AS transactionCurrency
            FROM billing_document_headers
            WHERE billingDocumentIsCancelled = 'False'
            """
        )
        if rows:
            row = rows[0]
            answer = (
                f"The total billed amount is {format_amount(row['totalBilledAmount'])} "
                f"{row['transactionCurrency']} across {row['billingDocuments']} billing documents."
            )
            return make_chat_response(answer, rows)

    if "how many deliveries" in query_lower or "count deliveries" in query_lower:
        rows = q("SELECT COUNT(*) AS deliveries FROM outbound_delivery_headers")
        answer = f"There are {rows[0]['deliveries']} deliveries in the dataset."
        return make_chat_response(answer, rows)

    if "list all products" in query_lower or query_lower.strip() == "list products":
        rows = q(
            """
            SELECT p.product, COALESCE(pd.productDescription, '') AS productDescription, p.productGroup, p.division
            FROM products p
            LEFT JOIN product_descriptions pd
              ON pd.product = p.product AND pd.language = 'EN'
            ORDER BY p.product
            LIMIT 50
            """
        )
        answer = f"I found {len(rows)} products in the first page of results."
        return make_chat_response(answer, rows)

    if "highest" in query_lower and "billing" in query_lower and "product" in query_lower:
        rows = q(
            """
            SELECT bdi.material AS product,
                   COALESCE(pd.productDescription, '') AS productDescription,
                   COUNT(DISTINCT bdi.billingDocument) AS billingDocuments
            FROM billing_document_items bdi
            LEFT JOIN product_descriptions pd
              ON pd.product = bdi.material AND pd.language = 'EN'
            GROUP BY bdi.material, pd.productDescription
            ORDER BY billingDocuments DESC, bdi.material
            LIMIT 10
            """
        )
        if rows:
            leader = rows[0]
            answer = (
                f"Product {leader['product']} has the highest billing volume in this result set "
                f"with {leader['billingDocuments']} billing documents."
            )
            return make_chat_response(answer, rows)

    if ("highest" in query_lower or "top" in query_lower) and "customer" in query_lower and (
        "billed" in query_lower or "billing" in query_lower or "amount" in query_lower
    ):
        rows = q(
            """
            SELECT bdh.soldToParty AS customer,
                   COUNT(DISTINCT bdh.billingDocument) AS billingDocuments,
                   ROUND(SUM(CAST(bdh.totalNetAmount AS REAL)), 2) AS totalBilledAmount,
                   MIN(bdh.transactionCurrency) AS transactionCurrency
            FROM billing_document_headers bdh
            WHERE bdh.billingDocumentIsCancelled = 'False'
            GROUP BY bdh.soldToParty
            ORDER BY totalBilledAmount DESC, billingDocuments DESC, customer
            LIMIT 10
            """
        )
        if rows:
            leader = rows[0]
            answer = (
                f"Customer {leader['customer']} has the highest billed amount in this result set "
                f"with {format_amount(leader['totalBilledAmount'])} {leader['transactionCurrency']} "
                f"across {leader['billingDocuments']} billing documents."
            )
            return make_chat_response(answer, rows)

    if ("highest" in query_lower or "top" in query_lower) and ("delivery" in query_lower or "deliveries" in query_lower):
        rows = q(
            """
            SELECT odi.referenceSdDocument AS salesOrder,
                   COUNT(DISTINCT odi.deliveryDocument) AS deliveries
            FROM outbound_delivery_items odi
            GROUP BY odi.referenceSdDocument
            ORDER BY deliveries DESC, salesOrder
            LIMIT 10
            """
        )
        if rows:
            leader = rows[0]
            answer = f"Sales order {leader['salesOrder']} has the most deliveries in this result set with {leader['deliveries']} delivery document(s)."
            return make_chat_response(answer, rows)

    if "total paid amount" in query_lower or ("total" in query_lower and "paid" in query_lower and "amount" in query_lower):
        rows = q(
            """
            SELECT COUNT(DISTINCT accountingDocument) AS paymentDocuments,
                   ROUND(SUM(CAST(amountInTransactionCurrency AS REAL)), 2) AS totalPaidAmount,
                   MIN(transactionCurrency) AS transactionCurrency
            FROM payments
            """
        )
        if rows:
            row = rows[0]
            answer = (
                f"The total payment amount is {format_amount(row['totalPaidAmount'])} "
                f"{row['transactionCurrency']} across {row['paymentDocuments']} payment documents."
            )
            return make_chat_response(answer, rows)

    if "delivered" in query_lower and "not billed" in query_lower:
        rows = q(
            """
            SELECT salesOrder, overallDeliveryStatus, overallOrdReltdBillgStatus, totalNetAmount, transactionCurrency
            FROM sales_order_headers
            WHERE overallDeliveryStatus = 'C'
              AND COALESCE(overallOrdReltdBillgStatus, '') IN ('', 'A', 'B')
            ORDER BY salesOrder
            LIMIT 50
            """
        )
        answer = f"I found {len(rows)} delivered sales orders that are not fully billed in this result page."
        return make_chat_response(answer, rows)

    if "broken" in query_lower or "incomplete" in query_lower:
        rows = q(
            """
            SELECT soh.salesOrder,
                   soh.overallDeliveryStatus,
                   soh.overallOrdReltdBillgStatus,
                   COUNT(DISTINCT odi.deliveryDocument) AS deliveries,
                   COUNT(DISTINCT bdh.billingDocument) AS billingDocuments
            FROM sales_order_headers soh
            LEFT JOIN outbound_delivery_items odi ON odi.referenceSdDocument = soh.salesOrder
            LEFT JOIN billing_document_items bdi ON bdi.referenceSdDocument = odi.deliveryDocument
            LEFT JOIN billing_document_headers bdh ON bdh.billingDocument = bdi.billingDocument
            GROUP BY soh.salesOrder, soh.overallDeliveryStatus, soh.overallOrdReltdBillgStatus
            HAVING soh.overallDeliveryStatus != 'C'
               OR COALESCE(soh.overallOrdReltdBillgStatus, '') != 'C'
               OR COUNT(DISTINCT odi.deliveryDocument) = 0
               OR COUNT(DISTINCT bdh.billingDocument) = 0
            ORDER BY deliveries, billingDocuments, soh.salesOrder
            LIMIT 50
            """
        )
        answer = f"I found {len(rows)} sales orders with incomplete downstream flow in this result page."
        return make_chat_response(answer, rows)

    return None


@app.route("/api/graph")
def get_graph():
    limit = request.args.get("limit", type=int)
    return jsonify(graph_payload(limit_orders=limit))


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user_query = (data.get("query") or "").strip()
    if not user_query:
        return jsonify({"error": "Empty query"}), 400

    if not is_domain_query(user_query):
        return make_chat_response(
            "I can answer questions about the SAP Order-to-Cash dataset and graph only. Ask about sales orders, deliveries, billing, journals, payments, customers, products, amounts, statuses, or trace flows."
        )

    builtin = run_builtin_query(user_query)
    if builtin is not None:
        return builtin

    sql_raw, llm_error = call_llm(SCHEMA, f"Question: {user_query}")
    if llm_error or not sql_raw:
        return make_chat_response(build_not_found_answer(user_query, find_document_id(user_query)))

    sql = re.sub(r"```sql|```", "", sql_raw).strip()
    if not sql.upper().startswith("SELECT"):
        return make_chat_response(sql)

    sql = sql.split(";")[0].strip()

    try:
        results = q(sql)
    except Exception as exc:
        return make_chat_response(
            f"I generated a query, but it could not be executed safely: {exc}",
            sql=sql,
        )

    if not results:
        answer = build_not_found_answer(user_query, find_document_id(user_query))
    else:
        answer, answer_error = call_llm_answer(results, user_query)
        if answer_error or not answer:
            answer = f"Found {len(results)} result(s)."

    return make_chat_response(answer, results, sql=sql)


@app.route("/api/stats")
def stats():
    return jsonify(
        {
            "sales_orders": q("SELECT COUNT(*) AS n FROM sales_order_headers")[0]["n"],
            "deliveries": q("SELECT COUNT(*) AS n FROM outbound_delivery_headers")[0]["n"],
            "billing_docs": q("SELECT COUNT(*) AS n FROM billing_document_headers")[0]["n"],
            "journal_entries": q("SELECT COUNT(*) AS n FROM journal_entries")[0]["n"],
            "payments": q("SELECT COUNT(*) AS n FROM payments")[0]["n"],
            "products": q("SELECT COUNT(*) AS n FROM products")[0]["n"],
        }
    )


@app.route("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "llm": "openrouter",
            "model": OPENROUTER_MODEL,
        }
    )


@app.route("/")
def index():
    index_path = os.path.join(FRONTEND_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(FRONTEND_BUILD_DIR, "index.html")
    return "Dodge AI O2C Graph API - Running"


@app.route("/<path:path>")
def frontend_assets(path):
    asset_path = os.path.join(FRONTEND_BUILD_DIR, path)
    if os.path.exists(asset_path):
        return send_from_directory(FRONTEND_BUILD_DIR, path)
    index_path = os.path.join(FRONTEND_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(FRONTEND_BUILD_DIR, "index.html")
    return "Not Found", 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=False, use_reloader=False, host="0.0.0.0", port=port)
