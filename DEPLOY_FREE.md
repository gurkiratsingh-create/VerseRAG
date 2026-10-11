# Deploy VerseRAG for $0

The deployment uses Render's free static site for the React frontend and a free web service for FastAPI, plus a Neon free PostgreSQL database with `pgvector`. The API creates embeddings locally with FastEmbed's quantized ONNX MiniLM model and returns the best matching evidence sentence with its citation. It does not require paid inference credits or a provider token.

Free plans have usage limits and can change. Render's free web services sleep after 15 minutes idle and have 512 MB RAM. Neon currently lists 1 GB storage and 100 compute hours per project monthly. FastEmbed downloads the public ONNX model the first time the API needs an embedding; it runs on the free API instance.

## Provider setup

1. Create a Neon free project in the Singapore region and run `CREATE EXTENSION IF NOT EXISTS vector;` in its SQL editor. Copy the pooled connection string into Render's `DATABASE_URL` secret. The project created for this deployment is named `VerseRAG`.
2. Create a Render Blueprint from this repository using [`render.yaml`](render.yaml). It declares the free backend and static frontend services. Provide `DATABASE_URL` when Render asks for the secret value.
3. Wait for both services to build. The API initializes the `vector` extension and application tables on startup. Visit the frontend service URL. The API's `/health` and `/health/db` endpoints report service and database status.

## Notes

- Render free web services sleep after inactivity, so the first request may take about a minute. Neon stores uploaded document content and embeddings persistently.
- Extractive answers quote the strongest matching sentence and cite its source; they do not synthesize an answer with a generative model.
- Local development continues to use Ollama and local sentence-transformer embeddings by default. The Render environment selects FastEmbed and extractive answers.
