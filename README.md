# VerseRAG

**Version-aware Retrieval-Augmented Generation for policy and document
question answering.**

VerseRAG is a document question-answering application designed to
retrieve evidence from versioned documents and answer questions with
source citations. It supports document ingestion, version publishing,
date-aware answers, semantic search, and comparison between document
versions.

The project combines a React + Vite frontend with a FastAPI backend,
PostgreSQL with `pgvector`, sentence-transformer embeddings, and an
Ollama-hosted language model.

> **Project status:** Prototype / portfolio project. The evaluation
> results below are from a small, synthetic employee-handbook dataset.
> They are not a general benchmark or a guarantee of factual
> correctness.

## Contents

-   [Features](#features)
-   [Architecture](#architecture)
-   [Technology stack](#technology-stack)
-   [Repository structure](#repository-structure)
-   [How version-aware answering
    works](#how-version-aware-answering-works)
-   [Evaluation](#evaluation)
-   [Requirements](#requirements)
-   [Local setup](#local-setup)
-   [Run the application](#run-the-application)
-   [API overview](#api-overview)
-   [Configuration](#configuration)
-   [Evaluation script](#evaluation-script)
-   [Deployment notes](#deployment-notes)
-   [Limitations](#limitations)
-   [Roadmap](#roadmap)

## Features

-   **Document ingestion:** Upload PDF and TXT documents.
-   **Document versioning:** Store multiple versions of a document under
    a shared document key.
-   **Draft and publish workflow:** Upload versions as drafts and
    publish them explicitly.
-   **Semantic retrieval:** Generate embeddings with
    `sentence-transformers/all-MiniLM-L6-v2` and store vectors in
    PostgreSQL using `pgvector`.
-   **Date-aware question answering:** Ask questions as of a specified
    date so the system can retrieve evidence from the applicable
    document version.
-   **Source citations:** Include source identifiers in generated
    answers and validate that cited IDs exist among the supplied
    passages.
-   **Version comparison:** Compare two versions to identify changes.
-   **Local LLM inference:** Generate answers through Ollama, using the
    configured local model.
-   **Evaluation workflow:** Run an evaluation over a CSV question set
    and export per-question results and a summary.

## Architecture

``` text
                    +-------------------------+
                    |     React + Vite UI     |
                    +------------+------------+
                                 | HTTP
                    +------------v------------+
                    |       FastAPI API       |
                    | Upload / versioning     |
                    | Search / answer         |
                    | Version comparison      |
                    +-------+---------+-------+
                            |         |
                 +----------v--+  +---v----------------+
                 | PostgreSQL  |  | Ollama             |
                 | + pgvector  |  | Local LLM inference|
                 +-------------+  +--------------------+
                            ^
                            |
                 Sentence-transformer
                    text embeddings
```

### Request flow

1.  A user uploads a document and supplies its document key, version
    label, and effective date.
2.  The backend extracts text, splits it into chunks, creates
    embeddings, and stores the version and chunks in PostgreSQL.
3.  A user searches or asks a question, optionally specifying an `as_of`
    date.
4.  The backend retrieves relevant evidence from the applicable
    version(s).
5.  The LLM generates an answer from the supplied passages and adds
    source identifiers.
6.  The API returns the answer and citation metadata to the frontend.

The diagram describes the application's intended flow; verify details
against the current code before treating it as a formal architecture
specification.

## Technology stack

  -----------------------------------------------------------------------
  Layer                               Technology
  ----------------------------------- -----------------------------------
  Frontend                            React, TypeScript, Vite

  Backend API                         Python, FastAPI

  Database                            PostgreSQL

  Vector search                       `pgvector`

  Embeddings                          Sentence Transformers,
                                      `all-MiniLM-L6-v2` (384 dimensions)

  Local LLM                           Ollama, configured by
                                      `OLLAMA_MODEL`

  Backend testing                     pytest

  Evaluation                          Python CSV evaluation script
  -----------------------------------------------------------------------

## Repository structure

``` text
VerseRAG/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── models.py
│   │   ├── ingestion.py
│   │   ├── embeddings.py
│   │   ├── routes.py
│   │   └── llm.py
│   ├── tests/
│   ├── evaluation_results/
│   ├── backfill_embeddings.py
│   ├── evaluate_rag.py
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   └── ...
├── docker-compose.yml
└── README.md
```

Do not commit local-only or generated directories such as `.venv`,
`node_modules`, `.pytest_cache`, or `.env`.

## How version-aware answering works

A document is identified by a stable `document_key` and can have
multiple versions. Each version has a label, effective date, and
publication status. Its content is split into chunks, and each chunk has
an embedding stored in PostgreSQL.

For a question with an `as_of` date, the application is intended to use
the version applicable to that date, rather than simply returning the
newest uploaded version. Retrieved passages are supplied to the LLM as
evidence. The generated answer uses source identifiers such as `[S1]`,
which are checked against the IDs provided to the generation function.

Citation ID validation only verifies that a cited source identifier
exists in the supplied passage list. It does **not** prove that the
cited passage logically supports the associated claim.

## Evaluation

The current evaluation used a synthetic Northstar employee-handbook
dataset with two versions and 18 questions covering policies that
changed over time, policies shared by both versions, and questions for
which the handbook does not provide a specific answer.

### Latest recorded results

  Metric                                                      Result
  --------------------------- --------------------------------------
  Total questions                                                 18
  Successful requests                                        18 / 18
  Failed requests                                                  0
  Temporal version accuracy     100% (14 version-specific questions)
  Answer keyword match                                        72.22%
  Citation ID validity                                          100%
  Answers with citations                                        100%
  Mean latency                                21,660.73 ms (21.66 s)
  Median latency                              22,324.19 ms (22.32 s)

### How to interpret these results

-   **Temporal version accuracy:** The expected version appeared among
    the returned citations for all 14 questions with a specific expected
    version. This does not establish that every retrieved passage came
    from the correct version or that the answer was factually correct.
-   **Answer keyword match:** This is a lexical check against
    expected-answer text, not semantic or human-judged factual accuracy.
    Correctly phrased answers can fail it, and a keyword match can still
    contain an error.
-   **Citation ID validity:** This confirms that citation IDs refer to
    IDs supplied to the model. It does not establish factual support.
-   **Answers with citations:** All evaluated answers contained
    citations according to the script's check. Citation presence alone
    does not establish citation quality.
-   **Latency:** Mean and median are from this evaluation run and can
    vary with hardware, model loading, database state, and local system
    load. They are not a production latency guarantee.

The evaluation is small and synthetic. Results should be expanded with
manually reviewed answers and evidence-support checks before making
claims about production-level reliability.

### Dataset coverage

The evaluation set includes questions about annual leave entitlement and
request notice, leave carry-forward limits and expiry, payslip error
reporting deadlines, expense claim deadlines, performance review
frequency, core collaboration hours and gift policies, remote-work
scenarios, and information not stated in the handbook.

The evaluation CSV is not assumed to be included in the repository. Add
it intentionally if you want others to reproduce the results, and ensure
it contains no private or sensitive data.

## Requirements

-   Python 3.12 (the project has been run with Python 3.12).
-   Node.js and pnpm compatible with the frontend lockfile.
-   Docker Desktop, or a PostgreSQL instance with the `pgvector`
    extension.
-   Ollama installed locally and a model downloaded.
-   Git.

## Local setup

### 1. Clone the repository

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd VerseRAG
```

Replace `<YOUR_GITHUB_REPOSITORY_URL>` with your repository URL after
pushing it to GitHub.

### 2. Start PostgreSQL with pgvector

If the included `docker-compose.yml` defines the database service, start
it from the repository root:

``` bash
docker compose up -d
```

Check the compose file for the configured database name, username,
password, and host port. The local configuration used during development
was:

``` dotenv
DATABASE_URL=postgresql+psycopg://verse_user:local_dev_password@127.0.0.1:55432/verserag
```

These are development values, not credentials to reuse for a public
deployment. Change them for your own environment.

### 3. Configure the backend

``` bash
cd backend
python -m venv .venv
```

Activate the environment on Windows PowerShell:

``` powershell
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `backend/.env` and configure the database connection and Ollama
settings:

``` dotenv
DATABASE_URL=postgresql+psycopg://<USER>:<PASSWORD>@127.0.0.1:<PORT>/<DATABASE>
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

Use values matching your local database and Ollama setup. Never commit
`.env` files or secrets.

### 4. Start Ollama

Install Ollama from its official website, start the Ollama service, and
pull the configured model:

``` bash
ollama pull llama3.2
```

Make sure the model name matches `OLLAMA_MODEL`. If you use a different
model, update the environment variable accordingly.

### 5. Start the backend

From the `backend/` directory, with the virtual environment active:

``` bash
python -m uvicorn app.main:app --reload
```

Expected local URLs:

-   API: `http://127.0.0.1:8000`
-   Interactive API documentation: `http://127.0.0.1:8000/docs`
-   Health endpoint: `http://127.0.0.1:8000/health`

The exact health response depends on the current implementation.

### 6. Start the frontend

Open a second terminal:

``` bash
cd frontend
pnpm install
pnpm dev
```

Use the local URL printed by Vite. If the frontend requires an API base
URL, configure it using the variable name expected by the frontend
source. Vite-exposed environment variables typically use the `VITE_`
prefix; do not put secrets in frontend environment variables because
they are exposed to the browser.

## Run the tests

From the `backend/` directory:

``` bash
python -m pytest -q
```

Ensure dependencies are installed and any integration tests have their
required services available. A passing test suite does not replace
evaluation of answer quality against the document corpus.

## API overview

The backend currently exposes these principal routes:

  -------------------------------------------------------------------------------------------------------------------
  Method                  Endpoint                                                            Purpose
  ----------------------- ------------------------------------------------------------------- -----------------------
  `POST`                  `/documents/upload`                                                 Upload a PDF/TXT
                                                                                              document version

  `GET`                   `/documents/{document_key}/versions`                                List versions for a
                                                                                              document

  `POST`                  `/documents/{document_key}/versions/{version_label}/publish`        Publish a version

  `POST`                  `/documents/search`                                                 Search document
                                                                                              evidence

  `POST`                  `/documents/answer`                                                 Ask a question and
                                                                                              return a grounded
                                                                                              answer

  `GET`                   `/documents/{document_key}/compare?from_version=v1&to_version=v2`   Compare two versions

  `GET`                   `/documents`                                                        List documents

  `GET`                   `/health`                                                           Health check
  -------------------------------------------------------------------------------------------------------------------

Consult `http://127.0.0.1:8000/docs` for live request and response
schemas. Verify parameters, response shapes, and authentication behavior
against the current API implementation.

## Configuration

  ----------------------------------------------------------------------------
  Variable                Purpose                 Example
  ----------------------- ----------------------- ----------------------------
  `DATABASE_URL`          PostgreSQL connection   `postgresql+psycopg://...`
                          string                  

  `OLLAMA_URL`            Ollama server base URL  `http://localhost:11434`

  `OLLAMA_MODEL`          Model name used for     `llama3.2`
                          generation              
  ----------------------------------------------------------------------------

The application may have additional settings in `backend/app/config.py`.
Check that file before deployment.

## Evaluation script

The evaluation script is located at `backend/evaluate_rag.py`. It reads
a CSV question set, calls the answer endpoint, and writes per-question
results and a summary under `backend/evaluation_results/`.

Install the HTTP client if it is not already included in the
requirements:

``` bash
python -m pip install requests
```

With PostgreSQL, Ollama, the backend, and the test document versions
available, run from the `backend/` directory:

``` bash
python evaluate_rag.py --csv "..\VerseRAG_Evaluation_Questions.csv"
```

Update the CSV path to match where you saved the dataset. The script's
summary metrics have the limitations described in the Evaluation
section. Keep generated result files and test datasets only if you
intentionally want to publish them.

## Deployment notes

The local development setup is not automatically production-ready.

-   **Frontend:** A Vite frontend can be deployed as a static site on a
    suitable hosting platform.
-   **FastAPI:** Choose a host that supports the application's Python
    dependencies and request patterns.
-   **Database:** Use a hosted PostgreSQL instance with `pgvector`
    enabled.
-   **LLM:** The default Ollama URL points to a local service. A
    deployed backend cannot reach your personal computer's `localhost`.
    Use an appropriately hosted inference endpoint or deploy the model
    on infrastructure you control.
-   **File uploads:** Check host request-size limits, execution
    timeouts, temporary storage behavior, and PDF processing
    constraints.
-   **Environment variables:** Configure secrets in the hosting
    provider's environment settings, never in source code.
-   **CORS:** Restrict browser origins to the deployed frontend domain.
-   **Database security:** Use strong credentials, TLS where supported,
    and least-privilege access.

A free-tier deployment may be possible, but database, inference,
execution, storage, and bandwidth quotas vary by provider. Confirm
current limits before choosing a hosting design.

## Limitations

-   The current evaluation set has only 18 questions from a synthetic
    two-version handbook.
-   Keyword matching is not semantic answer evaluation.
-   Citation ID validation does not verify whether cited evidence
    supports each claim.
-   Version correctness is measured by the presence of the expected
    version among citations, not by complete retrieval purity.
-   Local LLM inference has noticeable latency and depends on available
    hardware.
-   PDF extraction quality and chunk boundaries can affect retrieval.
-   Version comparison can include noisy text-level differences caused
    by formatting or extraction artifacts.
-   The prototype should not be used as the sole authority for
    high-stakes employment, legal, medical, financial, or compliance
    decisions.

## Roadmap

1.  Improve the evaluation set with manually verified answer and
    evidence labels.
2.  Add evaluation for evidence support and correct handling of
    insufficient evidence.
3.  Measure retrieval and generation latency separately.
4.  Improve retrieval for difficult questions and validate citations
    against their actual evidence.
5.  Add deployment configuration and test the hosted application end to
    end.
6.  Document reproducible setup steps and record benchmark
    hardware/model details.

## Contributing

Contributions, bug reports, and suggestions are welcome. For changes to
retrieval, version selection, answer generation, or evaluation, include
tests or reproducible examples where possible.

## License

No license has been specified yet. Add a `LICENSE` file before
presenting the repository as open source. Until then, do not assume
others have permission to reuse or redistribute the code.
