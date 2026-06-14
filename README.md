# Claim Structurer

Claim Structurer is a local-first GenAI web app for turning industrial claim files into a structured claim knowledge graph.

The app accepts PDF, PNG/JPEG, DOCX, and XLSX files. It stores uploads locally, tracks jobs in SQLite, and extracts the claim graph described by `industrial_claim_kg_uml_document_source.puml`: `Claim`, `Event`, `Party`, `FinancialItem`, `Document`, and `Source`.

## Stack

- Backend: Python, FastAPI, SQLite, Pydantic
- AI adapter: Azure AI Projects / Microsoft Foundry via `AIProjectClient.get_openai_client()`
- Frontend: Streamlit
- Local verification: explicit dev/test mock mode only

## Run Locally

```powershell
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# Edit .env and set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_NAME.
az login
python -m uvicorn backend.app.main:app --reload --port 8000
python -m streamlit run frontend/app.py
```

Open the Streamlit URL, typically `http://localhost:8501`.

## Azure Configuration

By default, the backend runs in API-only Azure mode. Missing Azure configuration causes jobs to fail with a clear configuration error instead of falling back to mock or local parsing.

The backend automatically loads `.env` from the repo root. Real shell environment
variables take precedence over values in `.env`.

Required `.env` values:

```dotenv
CLAIM_STRUCTURER_EXTRACTION_MODE=azure
FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
FOUNDRY_MODEL_NAME=<vision-capable-model-deployment>
```

PDF uploads are pre-processed with
[`LenDoStuff/claim-file-splitter`](https://github.com/LenDoStuff/claim-file-splitter)
through its public `split_claim_file_azure(...)` API before graph extraction.
The splitter is required for PDFs; the app does not keep the uploaded PDF as a
replacement document when splitter config or API calls fail.

Splitter configuration:

```dotenv
CLAIM_STRUCTURER_PDF_SPLITTER_MODE=required
CLAIM_STRUCTURER_PDF_SPLITTER_DEFAULT_CATEGORY=other
CLAIM_STRUCTURER_DOCUMENT_CATEGORIES_PATH=config/document_categories.json
CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_PAGE_BATCH_SIZE=5
CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_RENDER_DPI=160
CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_IMAGE_FORMAT=jpeg
CLAIM_STRUCTURER_DOCUMENT_EXTRACTION_IMAGE_QUALITY=85
```

Document categories are configured in `config/document_categories.json`. The
category objects use the same schema as `claim-file-splitter`: `name`,
`filename_prefix`, and `description`. The app uses the category `name` as
`document_type`, derives display groups from the name, and sorts documents by
the category order in the config file. If the splitter returns a category that
is not configured, the app fails clearly rather than guessing a local mapping.

The splitter accepts either the app's Foundry variables above or its native
variable names:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
AZURE_OPENAI_DEPLOYMENT=<vision-capable-model-deployment>
```

The Azure adapter uses:

- PDF documents split by `claim-file-splitter`, then rendered and extracted with Responses API `input_image` content in 5-page batches.
- PNG/JPEG input through Responses API `input_image` content.
- DOCX/XLSX input through Responses API `input_file` content.
- A second structured extraction pass that merges document-level outputs into the final claim graph.

For local UI demos or tests only, opt into the isolated mock extractor:

```dotenv
CLAIM_STRUCTURER_EXTRACTION_MODE=mock
```

## API

- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/documents`
- `GET /api/jobs/{job_id}/graph`
- `GET /api/documents/{document_id}/source/{source_id}`
- `GET /api/documents/{document_id}/file`

Supported v1 formats: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.docx`, `.xlsx`.
Legacy `.doc` and `.xls` files are rejected with a clear error.

## Tests

```powershell
python -m pytest
python -m streamlit run frontend/app.py
```
