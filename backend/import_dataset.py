import argparse
import json
import os
import sqlite3
from pathlib import Path


DEFAULT_SOURCE = Path.home() / "Downloads" / "sap-order-to-cash-dataset" / "sap-o2c-data"
DEFAULT_DB = Path(__file__).with_name("o2c.db")

TABLE_NAME_MAP = {
    "journal_entry_items_accounts_receivable": "journal_entries",
    "payments_accounts_receivable": "payments",
}

INDEXES = {
    "sales_order_headers": ["salesOrder", "soldToParty"],
    "sales_order_items": ["salesOrder", "material"],
    "outbound_delivery_headers": ["deliveryDocument"],
    "outbound_delivery_items": ["deliveryDocument", "referenceSdDocument"],
    "billing_document_headers": ["billingDocument", "accountingDocument", "soldToParty"],
    "billing_document_items": ["billingDocument", "referenceSdDocument"],
    "journal_entries": ["accountingDocument", "referenceDocument", "customer"],
    "payments": ["accountingDocument", "invoiceReference", "salesDocument", "customer"],
    "business_partners": ["businessPartner", "customer"],
    "products": ["product"],
    "product_descriptions": ["product"],
    "plants": ["plant"],
}


def quote_ident(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def iter_jsonl_rows(folder: Path):
    for file_path in sorted(folder.glob("*.jsonl")):
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def collect_columns(folder: Path):
    columns = []
    seen = set()
    row_count = 0
    for row in iter_jsonl_rows(folder):
        row_count += 1
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns, row_count


def create_table(conn: sqlite3.Connection, table_name: str, columns):
    col_sql = ", ".join(f'{quote_ident(col)} TEXT' for col in columns)
    conn.execute(f"DROP TABLE IF EXISTS {quote_ident(table_name)}")
    conn.execute(f"CREATE TABLE {quote_ident(table_name)} ({col_sql})")


def insert_rows(conn: sqlite3.Connection, folder: Path, table_name: str, columns):
    placeholders = ", ".join("?" for _ in columns)
    col_sql = ", ".join(quote_ident(col) for col in columns)
    sql = f"INSERT INTO {quote_ident(table_name)} ({col_sql}) VALUES ({placeholders})"

    batch = []
    inserted = 0
    for row in iter_jsonl_rows(folder):
        batch.append([None if row.get(col) is None else str(row.get(col)) for col in columns])
        if len(batch) >= 500:
            conn.executemany(sql, batch)
            inserted += len(batch)
            batch.clear()

    if batch:
        conn.executemany(sql, batch)
        inserted += len(batch)

    return inserted


def create_indexes(conn: sqlite3.Connection):
    for table_name, columns in INDEXES.items():
        for column in columns:
            index_name = f"idx_{table_name}_{column}"
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {quote_ident(index_name)} "
                f"ON {quote_ident(table_name)} ({quote_ident(column)})"
            )


def import_dataset(source_dir: Path, db_path: Path):
    if not source_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {source_dir}")

    folders = sorted(path for path in source_dir.iterdir() if path.is_dir())
    temp_db = db_path.with_suffix(".tmp")
    if temp_db.exists():
        temp_db.unlink()

    summary = []
    conn = sqlite3.connect(temp_db)
    try:
        for folder in folders:
            table_name = TABLE_NAME_MAP.get(folder.name, folder.name)
            columns, discovered_rows = collect_columns(folder)
            if not columns:
                continue
            create_table(conn, table_name, columns)
            inserted_rows = insert_rows(conn, folder, table_name, columns)
            summary.append((table_name, inserted_rows, discovered_rows))

        create_indexes(conn)
        conn.commit()
    finally:
        conn.close()

    os.replace(temp_db, db_path)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Import SAP O2C JSONL dataset into SQLite.")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Path to the sap-o2c-data directory",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Path to the SQLite database to create/update",
    )
    args = parser.parse_args()

    source_dir = Path(args.source).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    summary = import_dataset(source_dir, db_path)
    print(f"Imported {len(summary)} tables into {db_path}")
    for table_name, inserted_rows, discovered_rows in summary:
        print(f"{table_name}: {inserted_rows} rows")
        if inserted_rows != discovered_rows:
            print(f"Warning: discovered {discovered_rows} rows but inserted {inserted_rows} rows for {table_name}")


if __name__ == "__main__":
    main()
