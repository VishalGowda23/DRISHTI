# 🛡️ RiskLens AI

### Real-Time Portfolio Risk & Concentration Alert System

> *"See the risk before it sees you."*

**RiskLens AI** monitors live portfolio positions and flags concentration and risk-limit breaches in real time — with Claude-generated rationale behind every alert.

[![Built with FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)](https://reactjs.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat&logo=mongodb&logoColor=white)](https://mongodb.com)
[![Claude AI](https://img.shields.io/badge/Claude_AI-Anthropic-purple?style=flat)](https://anthropic.com)

---

## 🎯 What It Does

| Feature | Description |
|---------|-------------|
| **Portfolio Ingestion** | Upload holdings via CSV/JSON. Supports equities, bonds, derivatives, cash across multiple funds. |
| **Real-Time Price Updates** | Yahoo Finance integration updates positions every 60 seconds via Kafka streaming. |
| **AI-Powered Analysis** | Claude analyzes concentration limits (issuer, sector, geography, asset class) and correlation clusters. |
| **Severity Scoring** | Every assessment produces a LOW/MEDIUM/HIGH/CRITICAL verdict with a confidence score. |
| **Automated Escalation** | Email alerts, Jira ticket creation, and WebSocket dashboard push based on severity. |
| **Complete Audit Trail** | Every analysis, alert, and action is logged immutably for compliance. |

---

## 🏗️ Architecture

```
Yahoo Finance → Kafka → FastAPI Backend → Rule Engine → Claude AI → MongoDB
                                                              ↓
                                              Alerts → Email / Jira / WebSocket → React Dashboard
```

**Tech Stack**: FastAPI · React · MongoDB · Apache Kafka · LangChain · Claude AI · LangSmith · Yahoo Finance API

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Node.js 18+
- Anthropic Claude API key

### 1. Clone & Configure
```bash
git clone https://github.com/your-team/risklens-ai.git
cd risklens-ai
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Start All Services
```bash
# Using Docker Compose (recommended)
docker-compose -f docker/docker-compose.yml up --build -d

# Or using Makefile
make up
```

### 3. Seed Sample Data
```bash
cd backend
python scripts/seed_database.py
```

### 4. Access the Application
| Service | URL |
|---------|-----|
| React Dashboard | http://localhost:3000 |
| FastAPI Docs (Swagger) | http://localhost:8000/docs |
| MongoDB Admin | http://localhost:8081 |
| Kafka UI | http://localhost:8082 |

---

## 📡 API Quick Reference

```bash
# Upload a portfolio
curl -X POST http://localhost:8000/api/v1/portfolios/upload \
  -F "file=@sample-data/portfolio_alpha_growth.json" \
  -F "fund_name=Alpha Growth Fund"

# Trigger risk analysis
curl -X POST http://localhost:8000/api/v1/risk/analyze/{portfolio_id}

# View alerts
curl http://localhost:8000/api/v1/alerts?severity=HIGH,CRITICAL

# View audit logs
curl http://localhost:8000/api/v1/audit/logs?portfolio_id={id}
```

Full API documentation: http://localhost:8000/docs

---

## 📁 Project Structure

```
risklens-ai/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── api/      # REST endpoint controllers
│   │   ├── services/ # Business logic orchestration
│   │   ├── domain/   # Models + rule engine
│   │   └── infrastructure/ # External I/O (DB, AI, Kafka)
│   └── scripts/      # Utility scripts
├── frontend/         # React dashboard
├── sample-data/      # Demo portfolio data
├── prompts/          # Claude prompt templates
├── docker/           # Docker Compose + configs
└── docs/             # Documentation
```

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## 👥 Team

| Role | Responsibilities |
|------|-----------------|
| Backend Lead | FastAPI APIs, services, domain models |
| AI/ML Engineer | Claude integration, prompts, risk rules |
| Frontend Engineer | React dashboard, WebSocket, visualizations |
| Infra Lead | Docker, Kafka, MongoDB, notifications, docs |

---

## 📄 License

MIT License — Built for Wissen Technology Hackathon 2026
