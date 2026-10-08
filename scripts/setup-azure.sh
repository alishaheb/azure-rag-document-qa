#!/usr/bin/env bash
# One-time setup: resource group + passwordless login for GitHub Actions.
# Usage: ./scripts/setup-azure.sh <github-user>/<repo-name> [location] [resource-group]
# Run after: az login
set -euo pipefail

REPO="${1:?Give the GitHub repository, for example myname/ask-my-docs}"
LOCATION="${2:-swedencentral}"
RG="${3:-rg-ask-my-docs}"
APP_NAME="github-ask-my-docs"

echo "Registering resource providers (one time per subscription)..."
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry \
          Microsoft.Search Microsoft.CognitiveServices Microsoft.Storage \
          Microsoft.ManagedIdentity Microsoft.Insights; do
  az provider register --namespace "$ns" --output none
done

echo "Creating resource group $RG in $LOCATION..."
az group create -n "$RG" -l "$LOCATION" --output none
RG_ID=$(az group show -n "$RG" --query id -o tsv)

echo "Creating app registration for GitHub Actions..."
CLIENT_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
SP_ID=$(az ad sp create --id "$CLIENT_ID" --query id -o tsv 2>/dev/null \
        || az ad sp show --id "$CLIENT_ID" --query id -o tsv)

echo "Trusting GitHub tokens from the main branch of $REPO..."
az ad app federated-credential create --id "$CLIENT_ID" --parameters "{
  \"name\": \"github-main\",
  \"issuer\": \"https://token.actions.githubusercontent.com\",
  \"subject\": \"repo:${REPO}:environment:production\",
  \"audiences\": [\"api://AzureADTokenExchange\"]
}" --output none

echo "Giving the pipeline Owner on the resource group only (needed to create role assignments)..."
az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
  --role Owner --scope "$RG_ID" --output none

echo
echo "Done. In GitHub: Settings > Environments > create 'production'."
echo "Then Settings > Secrets and variables > Actions > Variables, add:"
echo "  AZURE_CLIENT_ID       = $CLIENT_ID"
echo "  AZURE_TENANT_ID       = $(az account show --query tenantId -o tsv)"
echo "  AZURE_SUBSCRIPTION_ID = $(az account show --query id -o tsv)"
echo "  AZURE_RESOURCE_GROUP  = $RG"
echo "  ALERT_EMAIL           = (optional) your email"
echo "  SEARCH_SKU            = (optional) free or basic"
