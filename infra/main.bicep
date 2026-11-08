// Retail pipeline infrastructure:
// ADLS Gen2 lake, Key Vault (RBAC), Azure SQL (free offer, auto-pause), Data Factory.
// Data Factory pipelines live as JSON in /adf and are not deployed by this file.
targetScope = 'resourceGroup'

@description('Azure region for storage, Key Vault and Data Factory')
param location string = resourceGroup().location

@description('Azure region for the SQL server (free-offer availability can differ by region)')
param sqlLocation string = location

@minLength(3)
@maxLength(9)
@description('Short prefix used to generate resource names')
param prefix string = 'retailde'

param storageAccountName string = take(toLower('st${prefix}${uniqueString(resourceGroup().id)}'), 24)
param keyVaultName string = take('kv-${prefix}-${uniqueString(resourceGroup().id)}', 24)
param sqlServerName string = toLower('sql-${prefix}-${uniqueString(resourceGroup().id)}')
param sqlDatabaseName string = 'retail_dw'
param dataFactoryName string = 'adf-${prefix}-${uniqueString(resourceGroup().id)}'

param sqlAdminLogin string = 'retailadmin'

@secure()
@description('SQL admin password. Never stored in the repo; supplied at deploy time.')
param sqlAdminPassword string

@description('Object ID of the person deploying (optional). Grants data access to the lake and secrets.')
param adminObjectId string = ''

param containerNames array = [
  'bronze'
  'silver'
  'gold'
]

param tags object = {
  project: 'retail-de-pipeline'
  environment: 'learning'
}

// Built-in role definition IDs
var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var keyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var keyVaultSecretsOfficer = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

// ---------- Data lake (ADLS Gen2) ----------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    isHnsEnabled: true
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource lakeContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for name in containerNames: {
  parent: blobService
  name: name
}]

// ---------- Key Vault (RBAC authorization) ----------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

resource secretSqlPassword 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'sql-admin-password'
  properties: {
    value: sqlAdminPassword
  }
}

resource secretSqlLogin 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'sql-admin-login'
  properties: {
    value: sqlAdminLogin
  }
}

// ---------- Azure SQL: server + free-offer database that auto-pauses ----------
resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: sqlServerName
  location: sqlLocation
  tags: tags
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

// 0.0.0.0 to 0.0.0.0 means "allow Azure services" (needed by Data Factory)
resource allowAzureServices 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: sqlLocation
  tags: tags
  sku: {
    name: 'GP_S_Gen5_2'
  }
  properties: {
    useFreeLimit: true
    freeLimitExhaustionBehavior: 'AutoPause'
  }
}

// ---------- Data Factory with a managed identity ----------
resource dataFactory 'Microsoft.DataFactory/factories@2018-06-01' = {
  name: dataFactoryName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
  }
}

// ---------- Access: Data Factory reads and writes the lake, reads secrets ----------
resource adfLakeAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, dataFactory.id, storageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: dataFactory.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource adfSecretsAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, dataFactory.id, keyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUser)
    principalId: dataFactory.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------- Access for the person deploying (optional) ----------
resource adminLakeAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(adminObjectId)) {
  name: guid(storage.id, adminObjectId, storageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: adminObjectId
    principalType: 'User'
  }
}

resource adminSecretsAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(adminObjectId)) {
  name: guid(keyVault.id, adminObjectId, keyVaultSecretsOfficer)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsOfficer)
    principalId: adminObjectId
    principalType: 'User'
  }
}

output storageAccountName string = storage.name
output lakeEndpoint string = storage.properties.primaryEndpoints.dfs
output keyVaultName string = keyVault.name
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDatabase.name
output dataFactoryName string = dataFactory.name
