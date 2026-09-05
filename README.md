# LedgerGuard AI

### Agentic Financial Reconciliation & Exception Investigation

LedgerGuard AI is an agentic finance-operations system that reconciles multi-source financial transaction records and investigates unresolved exceptions using a Gemini-powered, read-only AI agent.

The system is designed around a simple principle:

> **AI assists with investigation. Deterministic logic remains the source of financial truth.**

---

## Overview

Finance operations teams frequently reconcile transaction information across multiple systems such as orders, payment gateways, and settlement records.

A transaction may appear successful in one system while being missing, inconsistent, or delayed in another. Identifying these exceptions and investigating them can require significant manual effort.

LedgerGuard automates this workflow across a synthetic batch of **150 financial transaction records**.

The system:

1. Loads order, gateway, and settlement records.
2. Deterministically reconciles transactions across sources.
3. Calculates matching scores using reference, amount, currency, and date compatibility.
4. Classifies unresolved cases as exceptions or cases requiring review.
5. Reports measured reconciliation performance against ground truth.
6. Uses a Gemini-powered investigation agent to inspect unresolved cases.
7. Provides the agent with read-only tools for retrieving financial evidence.
8. Produces an evidence-backed finding and recommended operational action.
9. Records investigations in an audit log for later review.

---

## Architecture

```text
                 Synthetic Financial Records
                           |
            +--------------+--------------+
            |              |              |
         Orders         Gateway       Settlements
            |              |              |
            +--------------+--------------+
                           |
                           v
              Deterministic Reconciliation
                           |
              +------------+------------+
              |            |            |
            MATCH       EXCEPTION    AI REVIEW
                           |
                           v
                  Gemini Investigation
                           |
                  Read-Only Tool Layer
                           |
             +-------------+-------------+
             |             |             |
         get_order    get_gateway   search_settlements
             |             |             |
             +-------------+-------------+
                           |
                           v
               Evidence-Based Finding
                           |
             +-------------+-------------+
             |             |             |
          Finding      Recommendation   Trace
                           |
                           v
                     Audit Log
```

---

## Key Design Principle

LedgerGuard intentionally separates **financial decision-making** from **AI reasoning**.

The deterministic reconciliation engine is responsible for:

- Matching records
- Calculating compatibility scores
- Classifying reconciliation outcomes
- Identifying unresolved exceptions

The AI investigator is responsible for:

- Inspecting supplied evidence
- Retrieving additional records through read-only tools
- Explaining why an exception occurred
- Identifying uncertainty
- Recommending an operational next step

The AI agent cannot modify financial records or override the deterministic reconciliation result.

This separation makes the system more auditable and reduces the risk of allowing a language model to make unsupported financial decisions.

---

## Deterministic Reconciliation

LedgerGuard compares records using multiple signals.

### Gateway matching

Gateway candidates are scored using:

- Reference similarity
- Amount compatibility
- Currency compatibility
- Capture-date compatibility

Reference similarity is the strongest signal.

Financial amount matching is intentionally strict, with exact or near-exact amounts receiving the strongest compatibility score.

### Settlement matching

Settlement candidates are evaluated using:

- Gateway reference similarity
- Settlement amount compatibility
- Settlement timing

Settlement records are expected within a defined settlement window.

If a compatible settlement cannot be found, the transaction is classified as a missing-settlement exception.

---

## Agentic Investigation

Unresolved cases can be investigated through the LedgerGuard AI agent.

The agent has access to read-only investigation tools:

```text
get_order(order_id)
get_gateway(gateway_ref)
get_settlement(settlement_id)
search_settlements(gateway_ref)
```

The agent cannot directly modify the underlying financial data.

For example, when investigating a missing settlement, the agent can:

```text
1. Retrieve the order
2. Retrieve the gateway transaction
3. Search for settlements associated with the gateway reference
4. Compare the returned evidence
5. Explain the exception
6. Recommend an operational action
```

The investigation also exposes a tool trace showing which tools were called and what evidence they returned.

---

## Example Investigation

Example case:

```text
Order:       ORD-0006
Gateway:     GW-0000006
Amount:      4882.68 EUR
Gateway:     captured
Settlement:  not found
```

The deterministic engine identifies the case as:

```text
missing_settlement
```

The AI investigator then verifies:

```text
get_order("ORD-0006")
get_gateway("GW-0000006")
search_settlements("GW-0000006")
```

The settlement search returns no matching records.

The resulting investigation identifies the missing settlement, explains the supporting evidence, communicates remaining uncertainty, and recommends contacting the payment processor or finance operations team.

The AI output remains advisory. The deterministic reconciliation result remains the financial source of truth.

---

## Evaluation

LedgerGuard includes a separate ground-truth evaluation layer.

Ground truth is used **only to measure system performance**.

It is never provided to the reconciliation engine during matching.

The dashboard reports:

- Total transactions
- Matched transactions
- Match rate
- Exception count
- Ground-truth records
- Correct classifications
- Incorrect classifications
- Classification accuracy
- Exception breakdown

This separation prevents evaluation data from leaking into the reconciliation process.

---

## Auditability

Every AI investigation can be recorded in an audit log containing information such as:

- Timestamp
- Order ID
- Exception type
- Deterministic score
- AI finding
- AI confidence
- Recommended action
- Human-review requirement

The dashboard also provides an investigation history for previously investigated cases.

---

## Dashboard

The Streamlit dashboard provides:

### Reconciliation overview

```text
Transactions
Matched
Match Rate
Exceptions
```

### Exception analysis

The system displays a breakdown of unresolved exception types.

### Evaluation

Ground-truth performance is displayed separately from the operational reconciliation results.

### Transaction explorer

Users can filter transactions by:

- Decision
- Exception type
- Score

### AI investigation

Users can select an unresolved transaction and launch a read-only AI investigation.

The resulting interface displays:

- AI finding
- AI confidence
- Human-review status
- AI reasoning
- Recommended action
- Evidence used
- Agent investigation trace
- Investigation history

---

## Technology Stack

- **Python**
- **Streamlit**
- **Pydantic**
- **RapidFuzz**
- **Pandas**
- **Google Gemini API**
- **Google GenAI Python SDK**
- **Synthetic financial data**
- **JSONL audit logging**

---

## Project Structure

```text
ledgerguard-ai/
│
├── app/
│   ├── agents/
│   │   ├── investigator.py
│   │   └── tools.py
│   │
│   ├── core/
│   │   ├── audit.py
│   │   ├── evaluation.py
│   │   ├── matcher.py
│   │   ├── models.py
│   │   ├── normalizer.py
│   │   └── run_reconciliation.py
│   │
│   ├── data/
│   │   ├── generator.py
│   │   └── schemas.py
│   │
│   └── dashboard.py
│
├── data/
│   ├── orders.csv
│   ├── gateways.csv
│   ├── settlements.csv
│   └── ground_truth.csv
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd ledgerguard-ai
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Gemini

Set the Gemini API key as an environment variable:

```bash
export GEMINI_API_KEY="your_api_key_here"
```

Do not commit API keys to the repository.

### 5. Run the dashboard

```bash
streamlit run app/dashboard.py
```

The Streamlit interface should open locally.

---

## Safety and Reliability Considerations

LedgerGuard deliberately limits the role of the language model.

The AI investigator:

- Does not determine financial truth.
- Does not modify transactions.
- Does not invent missing records.
- Does not invent amounts, dates, or IDs.
- Does not treat missing evidence as proof that a transaction exists.
- Must distinguish confirmed evidence from uncertainty.
- Can recommend human review.

This architecture is intended to make AI useful for investigation without allowing generated text to silently become financial truth.

---

## Technical Challenges

Several implementation challenges were encountered during development:

### Gemini API compatibility

The initial Gemini model configuration became unavailable, requiring the integration to be updated to the currently supported model/API configuration.

### Tool-calling protocol

The Gemini tool-calling response format required careful handling of function-call and function-response messages. Incorrect role handling resulted in API errors, which were resolved by aligning the conversation structure with the GenAI SDK's expected format.

### Structured AI output

The investigator was required to return structured JSON rather than free-form text. The implementation includes JSON parsing and fallback handling when the model produces malformed structured output.

### Ground-truth evaluation

Ground-truth records contain empty exception fields, which can be interpreted as `NaN` by Pandas. These values had to be normalized before being passed into Pydantic models.

### Deterministic/AI separation

The system was designed so that the AI layer investigates exceptions without overriding the deterministic reconciliation engine. This required separating matching logic, evidence retrieval, AI reasoning, and evaluation.

---

## Limitations

This project uses synthetic financial data and is intended as a demonstration of an agentic finance-operations workflow.

It is not a production payment reconciliation system.

A production implementation would additionally require:

- Secure secrets management
- Authentication and authorization
- Persistent database storage
- Processor-specific settlement integrations
- Stronger financial controls
- Monitoring and alerting
- Rate limiting
- Comprehensive automated test coverage
- Production-grade observability
- Compliance and audit requirements

---

## Project Status

**Core implementation complete.**

The current system demonstrates:

- Multi-source reconciliation
- Deterministic matching
- Exception classification
- Measured evaluation
- Agentic investigation
- Read-only financial tools
- Evidence-backed AI reasoning
- Investigation traces
- Human-review signaling
- Audit logging
- Investigation history
- Streamlit dashboard

---

## Philosophy

LedgerGuard follows a simple rule:

> **Use deterministic systems to decide what happened. Use AI to investigate why it happened.**

That distinction is the foundation of the project.