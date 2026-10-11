# Deploy VerseRAG for $0

The deployment uses Render's free static site for the React frontend and a free web service for FastAPI, plus a Neon free PostgreSQL database with `pgvector`. The API sends embedding and answer-generation requests to Hugging Face Inference Providers. The code does not place provider credentials in the browser bundle.

Free plans have usage limits and can change. Render's free web services sleep after 15 minutes idle and have 512 MB RAM. Neon currently lists 1 GB storage and 100 compute hours per project monthly. Hugging Face free accounts currently include $0.10 monthly inference credit; generation or embedding can stop when the credit runs out. With no paid billing enabled, usage limits may make the app unavailable until quota resets.

## Provider setup

1. Create a Neon free project in the Singapore region and run `CREATE EXTENSION IF NOT EXISTS vector;` in its SQL editor. Copy the pooled connection string into Render's `DATABASE_URL` secret. The project created for this deployment is named `VerseRAG`.
2. Create a fine-grained Hugging Face token with Inference Providers access. Store it in Render as `HF_TOKEN`; never commit it or put it in a `VITE_` variable.
3. Create a Render Blueprint from this repository using [`render.yaml`](render.yaml). It declares the free backend and static frontend services. Provide `DATABASE_URL` and `HF_TOKEN` when Render asks for the secret values.
4. Wait for both services to build. The API initializes the `vector` extension and application tables on startup. Visit the frontend service URL. The API's `/health` and `/health/db` endpoints report service and database status.

## Notes

- Render free web services sleep after inactivity, so the first request may take about a minute. Neon stores uploaded document content and embeddings persistently.
- Hosted embedding and answer generation consume Hugging Face's monthly free credit. Keep the account's paid usage disabled for a strict $0 limit.
- Local development continues to use Ollama and local sentence-transformer embeddings by default. The Render environment selects Hugging Face for both.
