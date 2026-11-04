# Azure resources
- Resource group: rg-retail-de (centralindia)
- Storage account: <your storage name>, ADLS Gen2, Standard_LRS
- Containers: bronze, silver, gold
- Cost controls: $1 budget alert, free account, never upgraded, delete the resource group when finished


- SQL server: <server name>, database retail_dw (free offer, auto-pause until next month)
- Schema: gold (see sql/azure_schema.sql)
- Key Vault: <vault name>, RBAC authorization; secrets: sql-admin-login, sql-admin-password
- Rule: no passwords, connection strings, tenant or subscription IDs in the repo