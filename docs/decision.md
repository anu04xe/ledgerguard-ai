# Architecture Decisions

## 1. Deterministic financial validation

Financial arithmetic, record existence, amount comparison,
date windows and final validation are deterministic.

Reason:
LLMs are probabilistic and should not be the source of
financial truth.

## 2. AI only investigates ambiguity

The AI agent receives only cases that deterministic
matching cannot confidently resolve.
Reason:
reduces cost, latency and hallucination surface.

## 3. Ground truth is isolated

Ground truth is generated separately and is not available
to the reconciliation engine.

Reason:
allows objective evaluation.

## 4. Exceptions are first-class outputs

The system does not force reconciliation when evidence
is insufficient.

Reason:
false reconciliation is more dangerous than an
unresolved transaction.

## 5. Human review remains possible

Low-confidence and contradictory cases are escalated.

Reason:
financial automation should degrade safely.