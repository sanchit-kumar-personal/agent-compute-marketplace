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
| Database      | PostgreSQL + TimescaleDB                            |
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
