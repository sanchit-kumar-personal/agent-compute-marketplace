# 🧠 Agent Compute Marketplace (AgentCloud)

An AI-powered sandbox where autonomous agents negotiate cloud compute (GPUs, CPUs) and settle transactions using real-world payment rails (Stripe, PayPal, crypto). The project demonstrates agent-to-agent markets, AI-driven negotiation, secure payments, and audit-grade logging—ideal proof-of-work for infra / AI / fintech recruiters.

---

## ⚙️ Key Features

| Feature                                 | Why it matters                                                                            |
| --------------------------------------- | ----------------------------------------------------------------------------------------- |
| 🤝 **Autonomous Buyer & Seller Agents** | Simulate real-time supply–demand negotiation without human input.                         |
| 🧠 **GPT-Powered Negotiation Engine**   | Uses LangChain / AutoGen + GPT-4 to generate dynamic counter-offers and acceptance logic. |
| 💳 **Payment Integrations**             | Stripe (test mode), PayPal sandbox, optional ERC-20—showcases executable commerce flows.  |
| 📈 **Real-Time UI & Replay**            | Streamlit/React dashboard visualizes deal progress and lets recruiters replay sessions.   |
| 🧾 **Audit Logging & Policy Controls**  | Enterprise-grade traceability; every agent action and payment webhook is persisted.       |

---

## 🏗️ Tech Stack

| Layer         | Tools                                               |
| ------------- | --------------------------------------------------- |
| Agent Logic   | Python 3.11, GPT-4 (LangChain / AutoGen)            |
| Backend       | FastAPI                                             |
| Payments      | Stripe SDK, PayPal SDK, Web3.py (ERC-20)            |
| Database      | Development: SQLite                                 |
|               | Production: PostgreSQL + TimescaleDB                |
| Observability | OpenTelemetry, structured JSON logs                 |
| Frontend      | Streamlit _(fast)_ or React + Tailwind _(polished)_ |

---

## 📂 Project Structure

```text
agent-compute-marketplace/
├── agents/                # Buyer & seller agent classes
│   ├── buyer.py
│   └── seller.py
├── negotiation/           # FSM & GPT logic
│   ├── engine.py
│   └── prompts/
├── payments/              # Payment adapters
│   ├── stripe.py
│   ├── paypal.py
│   └── crypto.py
├── db/                    # SQLAlchemy models & migrations
│   ├── models.py
│   └── seed.py
├── api/                   # FastAPI routes & schemas
│   ├── routes.py
│   └── schemas.py
├── tests/                 # Pytest suites
│   └── test_negotiation.py
├── main.py                # App entry-point
├── .env.example
├── requirements.txt
├── pyproject.toml
├── setup.md               # Quick-start guide
├── .gitignore
└── README.md
```

## Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/agent-compute-marketplace.git
cd agent-compute-marketplace
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize the database:

```bash
alembic upgrade head
```

5. Run the development server:

```bash
uvicorn main:app --reload
```

## Development

- Run tests: `pytest`
- Format code: `black .`
- Lint code: `ruff .`
- Create database migration: `alembic revision --autogenerate -m "description"`

## Environment Variables

Required environment variables in `.env`:

- `DATABASE_URL`: Database connection string
- `STRIPE_KEY`: Stripe API key
- `PAYPAL_CLIENT_ID`: PayPal client ID
- `PAYPAL_SECRET`: PayPal secret key
- `OPENAI_API_KEY`: OpenAI API key

## API Documentation

Once running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
