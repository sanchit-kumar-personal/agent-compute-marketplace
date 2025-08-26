# 🧠 Agent Compute Marketplace

[![CI](https://github.com/sanchit-kumar-personal/agent-compute-marketplace/actions/workflows/ci.yml/badge.svg)](https://github.com/sanchit-kumar-personal/agent-compute-marketplace/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)
[![Version](https://img.shields.io/badge/version-v1.0.0-success.svg)](https://github.com/sanchit-kumar-personal/agent-compute-marketplace/releases)

> **🎬 Demo Ready!** AI-powered marketplace where autonomous agents negotiate cloud compute resources and settle payments using real-world payment rails (Stripe, PayPal). Complete with observability stack, audit trails, and ~89% test coverage.
>
> **🚀 v1.0.0 Production Ready** - Fully tested, documented, and ready for deployment.

## ✨ What This Demonstrates

- **AI Agent Negotiations** - GPT-powered buyer/seller agents that autonomously negotiate prices
- **Real Payment Processing** - Stripe and PayPal integration with webhooks and idempotency
- **Production Patterns** - OpenTelemetry tracing, Prometheus metrics, structured logging
- **Enterprise Audit** - Complete transaction trail with PostgreSQL persistence
- **Full Stack** - FastAPI backend, Streamlit dashboard, Docker orchestration

---

## 🚀 Quick Start

### One-Command Demo (Demo Mode)

```bash
git clone https://github.com/sanchit-kumar-personal/agent-compute-marketplace.git
cd agent-compute-marketplace
cp env.example .env
# Add your OpenAI/Stripe/PayPal keys to .env (see Environment Setup below)

DEMO_MODE=1 DISABLE_TRACING=1 docker compose up -d --build
```

**What happens automatically:**

- 🗄️ Database migrations run on first startup
- 🌱 Initial inventory seeded (100 GPU, 500 CPU, 50 TPU units)
- 🧪 Demo quotes created; one demo negotiation may run automatically
- 🚀 All services start with health checks

**Access Points:**

- **API Docs:** http://localhost:8000/docs
- **Dashboard:** http://localhost:8501
- **Grafana:** http://localhost:3000 (admin/admin)
- **Jaeger Traces:** http://localhost:16686
- **Prometheus:** http://localhost:9090

### Demo Flow (2 minutes)

```bash
# 🔍 Step 1: Check available compute resources (uses simulated inventory)
curl http://localhost:8000/api/v1/resources/availability

# 💰 Step 2: Create quote (AI pricing)
curl -X POST http://localhost:8000/api/v1/quotes/request \
  -H "Content-Type: application/json" \
  -d '{"buyer_id":"demo","resource_type":"GPU","duration_hours":4,"buyer_max_price":2.0}'

# 🤖 Step 3: Run AI negotiation (initial pricing)
QUOTE_ID=$(curl -s http://localhost:8000/api/v1/quotes/recent | jq -r '.[0].id')
curl -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/negotiate

# 🤝 Step 4: Multi-turn negotiation (optional)
curl -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/negotiate/multi-turn

# 💳 Step 5: Process payment
curl -X POST http://localhost:8000/api/v1/quotes/$QUOTE_ID/payments?provider=stripe \
  -H "Content-Type: application/json"

# 📊 Step 6: View audit trail
docker compose exec db psql -U agentcloud -d agentcloud \
  -c "SELECT action, payload FROM audit_logs ORDER BY id DESC LIMIT 3;"
```

## 🌐 Environment Setup

**1️⃣ Copy environment template:**

```bash
cp env.example .env
```

**2️⃣ Add your API keys:**

```bash
# Required for AI negotiations
OPENAI_API_KEY=sk-your-key-here

# Required for payments (use test keys)
STRIPE_API_KEY=sk_test_your-key-here
STRIPE_WEBHOOK_SECRET=whsec_your-secret-here

# Required for PayPal (sandbox)
PAYPAL_CLIENT_ID=your-sandbox-client-id
PAYPAL_SECRET=your-sandbox-secret
```

**3️⃣ Start services:**

```bash
docker compose up -d
```

## 📊 Real-Time Dashboard

![Agent Compute Marketplace Dashboard](docs/dashboard.png)

_Live negotiation tracking with metrics, audit trails, and payment status_

In Demo Mode, the dashboard sidebar includes a "Create demo quote" action. Set `API_BASE` in `.env` for local development if not using Docker (e.g., `http://localhost:8000`).

## 🧪 Demo Mode vs. Production

- **Demo Mode (recommended for screenshots/demos)**
  - `DEMO_MODE=1` redacts request bodies in audit logs and hides query params in API entry logs
  - `DISABLE_TRACING=1` disables OTEL exporters/instrumentation to keep logs clean
  - Demo data is seeded on startup; optional one-shot negotiation runs
- **Production**
  - Set `METRICS_ENABLED=true` and configure `METRICS_AUTH_TOKEN` to protect `/metrics`
  - Provide real Stripe/PayPal test keys; Stripe webhooks are recommended for real flows
  - Limit CORS origins; configure `ENVIRONMENT=production`

---

## 🏗️ Architecture

![System Architecture](docs/architecture.png)

_Comprehensive system showing AI agents, payment rails, and observability stack_

## 🛠️ Tech Stack

| Component          | Technology                  | Purpose                         |
| ------------------ | --------------------------- | ------------------------------- |
| **Backend**        | FastAPI + SQLAlchemy        | REST API with type safety       |
| **Agents**         | OpenAI GPT-4                | Autonomous price negotiation    |
| **Payments**       | Stripe + PayPal SDKs        | Real payment processing         |
| **Database**       | PostgreSQL                  | ACID transactions + audit logs  |
| **Observability**  | OTEL + Prometheus + Grafana | Production monitoring           |
| **Frontend**       | Streamlit                   | Real-time negotiation dashboard |
| **Infrastructure** | Docker Compose              | Full-stack orchestration        |

## 📊 Key Features

### AI-Powered Negotiations

- **Buyer Agent**: Analyzes market conditions, makes counter-offers
- **Seller Agent**: Dynamic pricing based on demand and inventory
- **Negotiation Engine**: Multi-turn conversations with state management
- **Market Intelligence**: Price history and trend analysis

### Payment Processing

- **Stripe Integration**: PaymentIntents with idempotency keys
- **PayPal Integration**: Sandbox invoicing with webhook handling
- **Transaction Tracking**: Complete audit trail for all payments
- **Error Handling**: Graceful degradation and retry logic

### Enterprise Observability

- **Distributed Tracing**: OpenTelemetry with Jaeger visualization
- **Custom Metrics**: Quote rates, negotiation latency, payment success
- **Structured Logging**: JSON logs with trace correlation
- **Grafana Dashboards**: Auto-provisioned monitoring panels

### Security & Compliance

- **Audit Logs**: Every action logged to `audit_logs` table
- **Secret Management**: Environment-based configuration
- **Input Validation**: Pydantic schemas with type checking
- **Error Boundaries**: Proper exception handling and rollbacks

---

## 📁 Project Structure

```
agent-compute-marketplace/
├── agents/                 # AI buyer/seller agent implementations
├── api/                   # FastAPI routes and schemas
├── core/                  # Settings, logging, metrics, tracing
├── db/                    # SQLAlchemy models and sessions
├── payments/              # Stripe/PayPal service implementations
├── dashboard/             # Streamlit real-time dashboard
├── tests/                 # 90%+ coverage test suite
├── alembic/               # Database migrations
├── docs/                  # Grafana configs and documentation
└── scripts/               # Deployment and utility scripts
```

## 🧪 Testing & Quality

- **~89% Test Coverage** - Comprehensive pytest suite
- **CI/CD Pipeline** - GitHub Actions with PostgreSQL
- **Code Quality** - Ruff linting + Black formatting
- **Type Safety** - Full mypy compliance
- **Docker Ready** - Multi-stage builds with health checks

## 📈 Monitoring & Observability

### Grafana Dashboards

- **Business Metrics**: Quote creation rates, negotiation success
- **System Metrics**: HTTP latency, error rates, database performance
- **Payment Metrics**: Transaction volume by provider

### Jaeger Tracing

- **End-to-End Visibility**: From API request to payment completion
- **Performance Analysis**: Identify bottlenecks in negotiation flow
- **Error Tracking**: Trace failed requests across service boundaries

### Audit Trail

```sql
-- Example audit query
SELECT action, payload->>'amount' as amount, created_at
FROM audit_logs
WHERE quote_id = 123
ORDER BY created_at;
```

## 🎯 Demo Scenarios

### Scenario 1: Successful Negotiation

🎯 **Step 1:** Create quote with buyer max price $2.00  
💡 **Step 2:** Seller prices at $1.80  
✅ **Step 3:** Buyer accepts immediately  
💳 **Step 4:** Payment processed via Stripe

### Scenario 2: Multi-Round Negotiation

🎯 **Step 1:** Create quote with buyer max price $1.50  
💰 **Step 2:** Seller starts at $2.20  
🔄 **Step 3:** 3 rounds of counter-offers  
🤝 **Step 4:** Final agreement at $1.75

### Scenario 3: Payment Failure Recovery

✅ **Step 1:** Complete negotiation successfully  
❌ **Step 2:** Simulate Stripe payment failure  
📝 **Step 3:** Audit logs capture failure details  
🔄 **Step 4:** Retry with PayPal successfully

---

## 🚀 Development Commands

### Docker Commands (Recommended)

```bash
make docker-up        # Start all services (auto-migrates & seeds)
make docker-down      # Stop all services
make docker-logs      # View logs from all services
make reset-demo       # Reset demo environment
```

### Local Development

```bash
make dev              # Start development server with auto-reload
make test             # Run pytest with coverage
make lint             # Run linting with ruff and black
make format           # Format code with black
make migrate          # Run database migrations
```

### Utility Commands

```bash
make install          # Install dependencies with Poetry
make clean            # Clean up temporary files
make dashboard        # Launch Streamlit dashboard locally
make help             # View all available commands
```

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Built to showcase:** AI agent development • Payment integration • Observability patterns • Enterprise software practices
