# Azure resources
- Resource group: rg-retail-de (centralindia)
- Storage account: <your storage name>, ADLS Gen2, Standard_LRS
- Containers: bronze, silver, gold
- Cost controls: $1 budget alert, free account, never upgraded, delete the resource group when finished


- SQL server: <server name>, database retail_dw (free offer, auto-pause until next month)
- Schema: gold (see sql/azure_schema.sql)
- Key Vault: <vault name>, RBAC authorization; secrets: sql-admin-login, sql-admin-password
- Rule: no passwords, connection strings, tenant or subscription IDs in the repo

- pl_ingest_weather: ForEach over 5 cities, REST (Open-Meteo) to bronze/weather/ingest_date=.../city=<name>.json
  (needed an Accept-Encoding: identity header because the REST connector failed to decode the compressed response)
- pl_backfill_orders: ForEach over 7 dates, Execute Pipeline reusing pl_ingest_orders

- Data flow: ADF ingests orders and weather to ADLS bronze; local DuckDB pipeline produces gold; gold is exported
  as typed Parquet to ADLS gold; ADF pipeline pl_load_gold_to_sql truncates and loads the Azure SQL gold schema
- Secrets: SQL password read from Key Vault by ADF through its managed identity (Key Vault Secrets User)
- Reconciliation: row counts and total revenue in Azure SQL equal the local warehouse

## Infrastructure as code
- infra/main.bicep recreates: ADLS Gen2 (bronze, silver, gold), Key Vault (RBAC), Azure SQL server and
  free-offer database (auto-pause on exhaustion), Data Factory with a managed identity, and role assignments
- Data Factory pipelines are stored as JSON in /adf (not deployed by Bicep)
- Checked with az bicep build and lint, a what-if against the live group, and a test deployment into a
  temporary resource group (5 resources, 3 containers, free SQL database with auto-pause), then deleted
- The SQL password is a secure parameter supplied at deploy time; it is never stored in the repo
- A wrong built-in role ID failed the first test deployment; IDs are now verified with `az role definition list`