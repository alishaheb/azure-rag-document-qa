# Ask My Documents

Upload documents and ask questions about them. The answers come from your documents only, with sources.

Built on Azure with Azure OpenAI, Azure AI Search, Blob Storage and Container Apps. All infrastructure is code (Bicep). GitHub Actions tests and deploys each change. No keys or passwords are used anywhere.

> Add a screenshot and a link to your 2–3 minute demo video here.

## What this project shows

- **Cloud:** Azure Container Apps, Blob Storage, AI Search, Azure OpenAI, Container Registry
- **AI:** retrieval-augmented generation (RAG) with hybrid (keyword + vector) search
- **Infrastructure as code:** one Bicep file creates everything
- **CI/CD:** GitHub Actions: lint, test, build, deploy, smoke test
- **Security:** managed identity, RBAC, OIDC, no keys (see [docs/architecture.md](docs/architecture.md))
- **Monitoring:** Application Insights, failed-request email alert

See the [architecture diagram](docs/architecture.md).

## Project structure

```
app/                 FastAPI app
  main.py            web endpoints (/upload, /ask, /health)
  azure_services.py  all Azure calls (Storage, Search, OpenAI)
  text_utils.py      text extraction and chunking
  static/index.html  web page
tests/               unit tests (no Azure needed)
infra/main.bicep     all Azure resources
scripts/             one-time setup script
.github/workflows/   CI/CD pipeline
```

## Before you start

- An Azure subscription. Students: [Azure for Students](https://azure.microsoft.com/free/students/).
- Azure CLI (`az`), Python 3.11+, Git, and Docker (Docker only for local container tests).
- **Cost:** AI Search `basic` and Container Registry `Basic` cost money each month even when idle. Use `searchSku=free` to save money. Set a budget alert: Azure portal > Cost Management > Budgets.
- **Models:** the defaults are `gpt-5-mini` (version `2025-08-07`) and `text-embedding-3-small` (version `1`). Models retire often. Before you deploy, check the [model retirement page](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/model-retirements) and model availability in your region. Change them with the `chatModelName` and `chatModelVersion` parameters.

## Option A: Deploy with GitHub Actions (recommended)

1. Push this project to a new GitHub repository.
2. Log in and run the setup script:
   ```bash
   az login
   chmod +x scripts/setup-azure.sh
   ./scripts/setup-azure.sh <your-github-user>/<repo-name> swedencentral
   ```
3. In GitHub, go to **Settings > Environments** and create an environment named `production`.
4. Go to **Settings > Secrets and variables > Actions > Variables**. Add the variables that the script printed.
5. Push to `main` (or run the workflow by hand). The pipeline:
   1. runs lint and tests,
   2. deploys the infrastructure,
   3. builds and pushes the Docker image,
   4. deploys the new image,
   5. checks `/health`.
6. Open the URL from the "Smoke test" step.

## Option B: Deploy by hand

```bash
az login
az group create -n rg-ask-my-docs -l swedencentral

# First deployment (uses a sample image)
az deployment group create -g rg-ask-my-docs -n main -f infra/main.bicep \
  -p developerPrincipalId=$(az ad signed-in-user show --query id -o tsv)

ACR=$(az deployment group show -g rg-ask-my-docs -n main --query properties.outputs.registryName.value -o tsv)

# Build the image in Azure, then deploy it
az acr build -r $ACR -t ask-my-docs:v1 .
az deployment group create -g rg-ask-my-docs -n main -f infra/main.bicep \
  -p containerImage=$ACR.azurecr.io/ask-my-docs:v1
```

Note: `az acr build` can be blocked on some free or student subscriptions. If so, use Docker: `az acr login -n $ACR`, then `docker build` and `docker push`.

## Run on your computer

You need a deployment with `developerPrincipalId` set (Option B does this). Role changes can take a few minutes to work.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env    # fill in the values from the deployment outputs
set -a; source .env; set +a
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Tests

```bash
pytest -q        # unit tests, no Azure needed
ruff check .     # lint
```

## Clean up (stop all costs)

```bash
az group delete -n rg-ask-my-docs --yes
```

After deletion, Azure OpenAI accounts stay "soft-deleted" for some time. To use the same name again, purge it: Azure portal > Azure AI services > Manage deleted resources.

## Limits and ideas for next steps

- Scanned PDFs (images) are not supported. Next step: add Azure AI Document Intelligence (OCR).
- No user login. Anyone with the URL can upload. Next step: add Entra ID login (Container Apps "Easy Auth").
- No evaluation. Next step: make a small set of test questions and measure answer quality.
- Public endpoints. Next step: private endpoints and a virtual network.

## Lessons learned

> Write 3–5 problems you had and how you solved them. Employers read this section.
