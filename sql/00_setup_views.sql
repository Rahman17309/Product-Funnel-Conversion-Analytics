-- 00 · Register the cleaned parquet tables as views.
-- Run from the repo root:  duckdb -c ".read sql/00_setup_views.sql"
CREATE OR REPLACE VIEW sessions       AS SELECT * FROM 'data/processed/sessions_clean.parquet';
CREATE OR REPLACE VIEW events         AS SELECT * FROM 'data/processed/events_clean.parquet';
CREATE OR REPLACE VIEW orders         AS SELECT * FROM 'data/processed/orders_clean.parquet';
CREATE OR REPLACE VIEW session_funnel AS SELECT * FROM 'data/processed/session_funnel.parquet';
