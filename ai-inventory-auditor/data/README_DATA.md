# AI Inventory Auditor — Sample Dataset

Fictional coursework data, not real company data.

## Contents
- `documents/`: 8 policy/data-dictionary documents with doc_id, title, version, date and owner.
- `products.csv`: 44 products across seven categories.
- `transactions.csv`: 245 stock movements with POSTED, DRAFT, CANCELLED and REJECTED statuses.
- `sample_audit_history.csv`: two example audit records. Your application should create new records in its SQLite DB.

## Rules
- expected_stock = opening_stock + SUM(IN where status=POSTED) - SUM(OUT where status=POSTED)
- DRAFT, CANCELLED and REJECTED transactions do not affect expected_stock.
- variance = physical_count - expected_stock
- Latest policy INV-DOC-002 v2.0: abs(variance) >= 10 => HIGH; 1-9 => NORMAL; zero => no discrepancy ticket.
- If physical_count is missing, do not calculate variance or create a ticket.
- Do not infer the cause of a discrepancy from stock numbers alone.
- After creating an audit request, read it back by audit_id to verify persisted state.

## Deterministic examples
- SP001: opening 100, posted IN 30, posted OUT 45, draft IN 10, physical 80.
  Expected stock=85, variance=-5. The DRAFT transaction must be ignored.
- SP002: opening 50, posted IN 10, posted OUT 5, physical 52.
- SP003: opening 75, posted IN 20, posted OUT 20, physical 75.
- SP004: physical_count is missing; ask for missing data.
