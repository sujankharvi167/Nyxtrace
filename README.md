# NyxTrace
## ML-Powered Money Laundering Detection & Intelligence

NyxTrace is an intelligent financial investigation platform designed to identify potentially suspicious financial activities and map how funds move across interconnected transaction networks.

> **Important Disclaimer**: NyxTrace is a research and portfolio project. ML model outputs represent statistical suspicion only and must not be used as the sole basis for any legal or regulatory decision. All flagged transactions require qualified human review.

---

## Project Status

| Stage | Name | Status |
|-------|------|--------|
| 1 | Project Foundation | ✅ Complete |
| 2 | Dataset Processing | ✅ Complete |
| 3 | Machine Learning | ✅ Complete |
| 4 | Graph Intelligence | 🔲 Planned |
| 5 | Investigation Intelligence | 🔲 Planned |
| 6 | Finalisation | 🔲 Planned |

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | React 18 + TypeScript, Vite, Tailwind CSS, React Router |
| Backend | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| Data | Pandas, NumPy |
| ML | Scikit-learn (Logistic Regression, Random Forest) |
| Graph | NetworkX |
| Visualisation | Recharts, React Flow |
| Deployment | Vercel (frontend), Render (backend) |

---

## Project Structure

```
NyxTrace/
├── frontend/                   # React + TypeScript frontend
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   │   └── ui/             # Core UI primitives
│   │   ├── pages/              # Application pages (6 sections)
│   │   ├── layouts/            # Page layout components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── services/           # API service layer
│   │   ├── types/              # TypeScript type definitions
│   │   └── utils/              # Utility functions
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
│
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── api/                # API route handlers
│   │   │   ├── health.py       # Health check endpoint
│   │   │   ├── analysis.py     # Analysis stats & status
│   │   │   ├── ml.py           # Stage 3 training and inference API
│   │   │   └── reports.py      # Reports listing
│   │   ├── services/
│   │   │   └── ml_engine.py    # Chunked dataset training and predictions
│   │   ├── core/               # Configuration and logging
│   │   │   ├── config.py       # Pydantic settings
│   │   │   └── logging.py      # Structured logging
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   │   ├── common.py       # Shared response models
│   │   │   └── analysis.py     # Analysis-specific models
│   │   └── main.py             # FastAPI application entry point
│   ├── requirements.txt
│   ├── tests/
│   ├── .env.example
│   └── .env                    # (not committed)
│
├── README.md
└── .gitignore
```

---

## Getting Started

### Prerequisites

- **Node.js** 18+ and **pnpm** (or npm)
- **Python** 3.11+
- Git

---

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (already pre-configured for local dev)
# Edit .env if you need to change ports or CORS origins

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

---

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
pnpm install
# or: npm install

# Start the development server
pnpm dev
# or: npm run dev
```

The frontend will be available at: **http://localhost:5173**

The Vite dev server proxies all `/api` requests to `http://localhost:8000`, so both services must be running simultaneously for full functionality.

---

## API Endpoints

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/` | Root — service info | ✅ |
| GET | `/api/health` | Health check | ✅ |
| GET | `/api/analysis/stats` | Platform statistics | ✅ (stub) |
| GET | `/api/analysis/status` | Analysis pipeline status | ✅ (stub) |
| POST | `/api/analysis/upload` | Upload and preprocess dataset CSVs | ✅ Stage 2 |
| GET | `/api/analysis/dataset` | Latest processed dataset summary | ✅ Stage 2 |
| GET | `/api/ml/readiness` | Check feature/class dataset readiness | ✅ Stage 3 |
| GET | `/api/ml/status` | Model and training status | ✅ Stage 3 |
| GET | `/api/ml/progress` | Background training progress | ✅ Stage 3 |
| POST | `/api/ml/train` | Compare, evaluate, and persist ML models | ✅ Stage 3 |
| GET | `/api/ml/evaluation` | Held-out model metrics | ✅ Stage 3 |
| GET | `/api/ml/models` | Model comparison results | ✅ Stage 3 |
| GET | `/api/ml/predictions` | Paginated transaction predictions | ✅ Stage 3 |
| GET | `/api/ml/suspicious` | Paginated predictions above illicit threshold | ✅ Stage 3 |
| GET | `/api/ml/feature-importance` | Selected-model global feature importance | ✅ Stage 3 |
| GET | `/api/ml/transactions/{id}/explanation` | Local feature-ablation explanation | ✅ Stage 3 |
| GET | `/api/reports` | List investigation reports | ✅ (stub) |
| GET | `/api/docs` | Swagger UI | ✅ |
| POST | `/api/analysis/run` | Execute analysis pipeline | 🔲 Stage 2 |
| GET | `/api/graph/network` | Transaction network data | 🔲 Stage 4 |
| GET | `/api/risk/scores` | Risk scores | 🔲 Later stage |

### Stage 3 Model Workflow

Open **Transaction Analysis**, upload the Elliptic++ feature and class CSVs, then select **Train & evaluate**. Training compares class-weighted Logistic Regression and Random Forest models. When a reliable time-step field is present, the holdout is chronological; otherwise a reproducible stratified split is used. Only licit and illicit labels are supervised targets; unknown labels are excluded from training/evaluation and retained as ground truth for transaction predictions.

Training runs in the background; the page polls its progress and then displays held-out metrics, model comparison, confusion matrix, global feature importance, paginated predictions, and local feature-ablation explanations. The explanation is a sensitivity estimate, not a causal account. The selected model, preprocessing medians, feature order, model configurations, evaluation results, and batched predictions are stored under `backend/data/ml/` (ignored by Git). The Risk Intelligence, graph, and investigation stages remain outside this implementation.

Run the backend tests from `backend/` with `python -m unittest discover -s tests -p "test_*.py"` and build the frontend from `frontend/` with `npm run build`.

---

## Application Sections

| Section | Path | Description | Stage |
|---------|------|-------------|-------|
| Dashboard | `/` | Platform overview and investigation workflow | ✅ Stage 1 |
| Transaction Analysis | `/analysis` | Dataset upload, preprocessing, and model workflow | ✅ Stages 2–3 |
| Money Flow Intelligence | `/money-flow` | Transaction network analysis and route tracing | 🔲 Stage 4 |
| Risk Intelligence | `/risk` | Later risk insights and investigation workflow | 🔲 Later stages |
| Investigation Reports | `/reports` | Analysis summaries and downloadable reports | 🔲 Stage 5 |
| About NyxTrace | `/about` | Platform overview, tech stack, and roadmap | ✅ Stage 1 |

---

## Datasets

### Elliptic++ (Primary)
Bitcoin transaction graph dataset with labeled transaction nodes.
- `txs_features.csv` — Transaction feature vectors with transaction ID and time-step fields; predictors are detected from the CSV schema
- `txs_classes.csv` — Transaction labels: `1` (illicit), `2` (licit), `3` (unknown)
- `txs_edgelist.csv` — Transaction graph edges

### IBM AMLSim (Planned)
Synthetic banking-style AML transaction data for realistic banking scenarios.

> **Note**: Elliptic++ contains **cryptocurrency** transaction data, not conventional bank records.
> Column schemas are inspected at preprocessing time — no hardcoded assumptions are made.

---

## Development Notes

- **Never commit `.env` files** — only `.env.example` is tracked.
- **Dataset CSV files** are excluded from version control (see `.gitignore`) due to their size.
- Backend and frontend are independently deployable services.
- CORS is configured for local development; update `ALLOWED_ORIGINS` in `.env` for production.
- Do not commit or push without explicit instruction.

---

## License

This project is developed for research and portfolio purposes.  
© 2024 All rights reserved.
