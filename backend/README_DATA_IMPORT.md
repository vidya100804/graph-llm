## Import external SAP O2C dataset

Rebuild the app database from the JSONL dataset in `sap-o2c-data`:

```bash
cd backend
python import_dataset.py --source C:\Users\91709\Downloads\sap-order-to-cash-dataset\sap-o2c-data --db o2c_imported.db
```

The importer:

- creates or recreates `o2c_imported.db`
- preserves the table names the Flask app already uses
- imports the extra dataset folders as additional SQLite tables
- adds indexes for the main O2C join keys

`app.py` will automatically use `o2c_imported.db` when it exists.
