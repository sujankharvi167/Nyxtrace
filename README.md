# NyxTrace
## ML-Powered Money Laundering Detection & Intelligence

NyxTrace is an intelligent financial investigation platform designed to identify potentially suspicious financial activities and map how funds move across interconnected transaction networks.

> **Important Disclaimer**: NyxTrace is a research and portfolio project. ML model outputs represent statistical suspicion only and must not be used as the sole basis for any legal or regulatory decision. All flagged transactions require qualified human review.

---

## Project Status

| Stage | Name | Status |
|-------|------|--------|
| 1 | Project Foundation | ✅ Complete |
| 2 | Dataset Processing | 🔲 Planned |
| 3 | Machine Learning | 🔲 Planned |
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
| ML | Scikit-learn, XGBoost, SHAP |
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
│   │   │   └── reports.py      # Reports listing
│   │   ├── core/               # Configuration and logging
│   │   │   ├── config.py       # Pydantic settings
│   │   │   └── logging.py      # Structured logging
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   │   ├── common.py       # Shared response models
│   │   │   └── analysis.py     # Analysis-specific models
│   │   └── main.py             # FastAPI application entry point
│   ├── requirements.txt
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
| GET | `/api/reports` | List investigation reports | ✅ (stub) |
| GET | `/api/docs` | Swagger UI | ✅ |
| POST | `/api/analysis/upload` | Upload dataset CSV | 🔲 Stage 2 |
| POST | `/api/analysis/run` | Execute analysis pipeline | 🔲 Stage 2 |
| GET | `/api/graph/network` | Transaction network data | 🔲 Stage 4 |
| GET | `/api/risk/scores` | Risk scores | 🔲 Stage 3 |

---

## Application Sections

| Section | Path | Description | Stage |
|---------|------|-------------|-------|
| Dashboard | `/` | Platform overview and investigation workflow | ✅ Stage 1 |
| Transaction Analysis | `/analysis` | Dataset upload and preprocessing workspace | 🔲 Stage 2 |
| Money Flow Intelligence | `/money-flow` | Transaction network analysis and route tracing | 🔲 Stage 4 |
| Risk Intelligence | `/risk` | Suspicious activity detection and risk insights | 🔲 Stage 3–5 |
| Investigation Reports | `/reports` | Analysis summaries and downloadable reports | 🔲 Stage 5 |
| About NyxTrace | `/about` | Platform overview, tech stack, and roadmap | ✅ Stage 1 |

---

## Datasets

### Elliptic++ (Primary)
Bitcoin transaction graph dataset with labeled transaction nodes.
- `txs_features.csv` — Transaction feature vectors (166 features)
- `txs_classes.csv` — Transaction labels: `1` (illicit), `2` (licit), `unknown`
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
