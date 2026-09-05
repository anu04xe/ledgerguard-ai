import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.tools import LedgerTools
from app.core.audit import (
    log_investigation,
    get_audit_for_order,
    load_audit_log,
)
from app.core.evaluation import evaluate_results
from app.core.matcher import reconcile_all
from app.core.run_reconciliation import (
    load_data,
    load_ground_truth,
)


# -------------------------------------------------------------------
# Page configuration
# -------------------------------------------------------------------

st.set_page_config(
    page_title="LedgerGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -------------------------------------------------------------------
# Custom styling
# -------------------------------------------------------------------

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1500px;
        }

        .hero {
            padding: 1.5rem 2rem;
            border-radius: 14px;
            border: 1px solid rgba(128, 128, 128, 0.25);
            margin-bottom: 1.5rem;
        }

        .hero-title {
            font-size: 2.3rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .hero-subtitle {
            font-size: 1rem;
            opacity: 0.75;
        }

        .section-title {
            font-size: 1.35rem;
            font-weight: 650;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
        }

        .status-card {
            padding: 1rem;
            border-radius: 10px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            min-height: 90px;
        }

        .small-label {
            font-size: 0.78rem;
            opacity: 0.65;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        .small-value {
            font-size: 1.45rem;
            font-weight: 650;
        }

        div[data-testid="stMetric"] {
            padding: 0.6rem 0.2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# Header
# -------------------------------------------------------------------

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">🛡️ LedgerGuard AI</div>
        <div class="hero-subtitle">
            AI-assisted financial reconciliation, anomaly detection,
            and exception investigation.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# Load data
# -------------------------------------------------------------------

orders, gateways, settlements = load_data()

results = reconcile_all(
    orders,
    gateways,
    settlements,
)

ground_truth = load_ground_truth()

evaluation = evaluate_results(
    results,
    ground_truth,
)

ledger_tools = LedgerTools(
    orders,
    gateways,
    settlements,
)


# -------------------------------------------------------------------
# Calculate summary statistics once
# -------------------------------------------------------------------

total = len(results)

matched = sum(
    result.decision == "MATCH"
    for result in results
)

exceptions = sum(
    result.decision == "EXCEPTION"
    for result in results
)

ai_review = sum(
    result.decision == "NEEDS_AI_REVIEW"
    for result in results
)

unresolved = exceptions + ai_review

match_rate = (
    matched / total
    if total
    else 0.0
)


# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------

with st.sidebar:

    st.header("LedgerGuard")

    st.caption(
        "Deterministic reconciliation + AI investigation"
    )

    st.divider()

    st.subheader("System Status")

    st.success("Reconciliation engine online")
    st.success("Dataset loaded")
    st.success("Evaluation available")

    st.divider()

    st.subheader("Pipeline")

    st.write("1. Load transaction records")
    st.write("2. Deterministic reconciliation")
    st.write("3. Exception classification")
    st.write("4. AI investigation")
    st.write("5. Audit logging")

    st.divider()

    st.caption(
        "Financial decisions are made by the deterministic "
        "reconciliation engine. AI provides investigation and "
        "explanation only."
    )


# -------------------------------------------------------------------
# Executive summary
# -------------------------------------------------------------------

st.markdown(
    '<div class="section-title">Reconciliation Overview</div>',
    unsafe_allow_html=True,
)

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Transactions",
        total,
    )

with col2:
    st.metric(
        "Matched",
        matched,
    )

with col3:
    st.metric(
        "Match Rate",
        f"{match_rate:.1%}",
    )

with col4:
    st.metric(
        "Exceptions",
        exceptions,
    )

with col5:
    st.metric(
        "AI Review",
        ai_review,
    )
st.caption(
    "Deterministic reconciliation metrics"
)

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

kpi_col1.metric(
    "Auto-Match Rate",
    f"{match_rate:.1%}",
)

kpi_col2.metric(
    "Exception Rate",
    f"{exceptions / total:.1%}" if total else "0.0%",
)

kpi_col3.metric(
    "AI Review Queue",
    ai_review,
)

kpi_col4.metric(
    "Investigations Logged",
    len(__import__(
        "app.core.audit",
        fromlist=["load_audit_log"]
    ).load_audit_log()),
)

# -------------------------------------------------------------------
# Exception overview
# -------------------------------------------------------------------

st.divider()

st.markdown(
    '<div class="section-title">Exception Overview</div>',
    unsafe_allow_html=True,
)

breakdown = evaluation["exception_breakdown"]

if breakdown:

    exception_df = pd.DataFrame(
        [
            {
                "Exception Type": (
                    exception_type
                    .replace("_", " ")
                    .title()
                ),
                "Count": count,
                "Share": (
                    count / evaluation["total"]
                    if evaluation["total"]
                    else 0
                ),
            }
            for exception_type, count
            in sorted(
                breakdown.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]
    )

    exception_df["Share"] = exception_df["Share"].map(
        lambda value: f"{value:.1%}"
    )

    st.dataframe(
        exception_df,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.success("No exceptions detected.")


# -------------------------------------------------------------------
# System evaluation
# -------------------------------------------------------------------

st.divider()

st.markdown(
    '<div class="section-title">System Evaluation</div>',
    unsafe_allow_html=True,
)

eval_col1, eval_col2, eval_col3, eval_col4 = st.columns(4)

with eval_col1:
    st.metric(
        "Ground Truth Records",
        evaluation["total"],
    )

with eval_col2:
    st.metric(
        "Correct",
        evaluation["correct"],
    )

with eval_col3:
    st.metric(
        "Classification Accuracy",
        f"{evaluation['accuracy']:.1%}",
    )

with eval_col4:
    st.metric(
        "Incorrect",
        evaluation["incorrect"],
    )

st.caption(
    "Ground truth is used exclusively for evaluation and is never "
    "provided to the reconciliation engine."
)

# -------------------------------------------------------------------
# Transaction Explorer
# -------------------------------------------------------------------

st.divider()

st.subheader("Transaction Explorer")

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:

    decision_filter = st.selectbox(
        "Decision",
        [
            "ALL",
            "MATCH",
            "EXCEPTION",
            "NEEDS_AI_REVIEW",
        ],
    )

with filter_col2:

    exception_types = sorted(
        {
            r.exception_type
            for r in results
            if r.exception_type
        }
    )

    exception_filter = st.selectbox(
        "Exception Type",
        ["ALL"] + exception_types,
    )

with filter_col3:

    minimum_score = st.slider(
        "Minimum Match Score",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.05,
    )


filtered_results = results

if decision_filter != "ALL":

    filtered_results = [
        r
        for r in filtered_results
        if r.decision == decision_filter
    ]


if exception_filter != "ALL":

    filtered_results = [
        r
        for r in filtered_results
        if r.exception_type == exception_filter
    ]


filtered_results = [
    r
    for r in filtered_results
    if r.score >= minimum_score
]


st.caption(
    f"Showing {len(filtered_results)} of "
    f"{len(results)} transactions"
)


result_df = pd.DataFrame(
    [
        {
            "Order": r.order_id,
            "Decision": r.decision,
            "Gateway": r.gateway_id or "",
            "Settlement": r.settlement_id or "",
            "Score": round(r.score, 3),
            "Exception": (
                r.exception_type.replace("_", " ").title()
                if r.exception_type
                else ""
            ),
        }
        for r in filtered_results
    ]
)


st.dataframe(
    result_df,
    use_container_width=True,
    hide_index=True,
)


# -------------------------------------------------------------------
# Exception investigation
# -------------------------------------------------------------------

st.divider()

st.markdown(
    '<div class="section-title">Exception Investigation</div>',
    unsafe_allow_html=True,
)

exceptions_to_review = [
    result
    for result in results
    if result.decision != "MATCH"
]


if not exceptions_to_review:

    st.success(
        "All transactions reconciled successfully. "
        "No investigation is required."
    )

else:

    selected_id = st.selectbox(
        "Select a transaction to investigate",
        [
            result.order_id
            for result in exceptions_to_review
        ],
    )

    selected = next(
        result
        for result in exceptions_to_review
        if result.order_id == selected_id
    )

    # ---------------------------------------------------------------
    # Selected case summary
    # ---------------------------------------------------------------

    st.markdown(
        f"### Case `{selected.order_id}`"
    )

    case_col1, case_col2, case_col3, case_col4 = st.columns(4)

    with case_col1:
        st.write("**Decision**")
        st.write(selected.decision)

    with case_col2:
        st.write("**Exception**")
        st.write(
            selected.exception_type
            .replace("_", " ").title()
            if selected.exception_type
            else "None"
        )

    with case_col3:
        st.write("**Deterministic Score**")
        st.write(f"{selected.score:.1%}")

    with case_col4:
        st.write("**Gateway**")
        st.write(
            selected.gateway_id
            or "Not found"
        )

    # ---------------------------------------------------------------
    # Financial records
    # ---------------------------------------------------------------

    st.subheader("Transaction Evidence")

    record_col1, record_col2, record_col3 = st.columns(3)

    with record_col1:

        st.write("**Order**")

        st.write(
            f"ID: `{selected.order_id}`"
        )

        st.write(
            f"Amount: `{selected.order_amount}`"
        )

    with record_col2:

        st.write("**Gateway**")

        st.write(
            f"Reference: "
            f"`{selected.gateway_id or 'None'}`"
        )

        st.write(
            f"Amount: `{selected.gateway_amount}`"
        )

    with record_col3:

        st.write("**Settlement**")

        st.write(
            f"ID: "
            f"`{selected.settlement_id or 'None'}`"
        )

        st.write(
            f"Amount: `{selected.settlement_amount}`"
        )

    # ---------------------------------------------------------------
    # Deterministic evidence
    # ---------------------------------------------------------------

    st.subheader("Deterministic Evidence")

    evidence_df = pd.DataFrame(
        [
            {
                "Factor": evidence.factor.replace(
                    "_", " "
                ).title(),
                "Evidence": evidence.value,
                "Score": f"{evidence.score:.1%}",
            }
            for evidence in selected.evidence
        ]
    )

    if not evidence_df.empty:

        st.dataframe(
            evidence_df,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No deterministic evidence was recorded "
            "for this case."
        )

    # ---------------------------------------------------------------
    # AI investigation
    # ---------------------------------------------------------------

    st.subheader("AI Investigation")

    st.caption(
        "LedgerGuard AI can inspect the supplied records using "
        "read-only investigation tools. It cannot modify financial "
        "records or override deterministic reconciliation."
    )

    if st.button(
        "Investigate with LedgerGuard AI",
        type="primary",
        use_container_width=True,
    ):

        from app.agents.investigator import LedgerInvestigator

        case = {
            "order": {
                "order_id": selected.order_id,
                "amount": str(selected.order_amount),
            },
            "gateway": {
                "gateway_ref": selected.gateway_id,
                "amount": str(selected.gateway_amount),
            },
            "settlement": {
                "settlement_id": selected.settlement_id,
                "amount": str(
                    selected.settlement_amount
                ),
            },
            "exception": selected.exception_type,
            "deterministic_score": selected.score,
            "matching_factors": selected.matching_factors,
            "evidence": [
                {
                    "factor": evidence.factor,
                    "value": evidence.value,
                    "score": evidence.score,
                }
                for evidence in selected.evidence
            ],
        }

        with st.spinner(
            "LedgerGuard AI is investigating the evidence..."
        ):

            try:

                investigator = LedgerInvestigator(
                    ledger_tools
                )

                investigation = investigator.investigate(
                    case
                )

                # ---------------------------------------------------
                # Audit logging
                # ---------------------------------------------------

                log_investigation(
                    order_id=selected.order_id,
                    exception_type=selected.exception_type,
                    deterministic_score=selected.score,
                    investigation=investigation,
                )

                # ---------------------------------------------------
                # AI result
                # ---------------------------------------------------

                st.success(
                    "Investigation complete"
                )

                st.subheader("AI Finding")

                st.write(
                    investigation.get(
                        "finding",
                        "No finding returned.",
                    )
                )

                ai_col1, ai_col2 = st.columns(2)

                with ai_col1:

                    confidence = investigation.get(
                        "confidence",
                        0,
                    )

                    try:
                        confidence = float(
                            confidence
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        confidence = 0.0

                    confidence = max(
                        0.0,
                        min(
                            1.0,
                            confidence,
                        ),
                    )

                    st.metric(
                        "AI Confidence",
                        f"{confidence:.0%}",
                    )

                with ai_col2:

                    human_review = investigation.get(
                        "requires_human_review",
                        True,
                    )

                    st.metric(
                        "Human Review",
                        "Required"
                        if human_review
                        else "Not required",
                    )

                st.subheader("AI Reasoning")

                st.write(
                    investigation.get(
                        "reasoning",
                        "No reasoning returned.",
                    )
                )

                st.subheader(
                    "Recommended Action"
                )

                st.info(
                    investigation.get(
                        "recommended_action",
                        "Human investigation required.",
                    )
                )

                st.subheader(
                    "Evidence Used by AI"
                )

                evidence_used = investigation.get(
                    "evidence_used",
                    [],
                )

                if evidence_used:

                    for evidence in evidence_used:

                        st.write(
                            f"• {evidence}"
                        )

                else:

                    st.write(
                        "No additional evidence reported."
                    )

                # ---------------------------------------------------
                # Agent trace
                # ---------------------------------------------------

                tool_trace = investigation.get(
                    "_tool_trace",
                    [],
                )

                if tool_trace:

                    with st.expander(
                        "Agent Investigation Trace"
                    ):

                        st.caption(
                            "Read-only tool calls performed "
                            "during this investigation."
                        )

                        for index, trace in enumerate(
                            tool_trace,
                            start=1,
                        ):

                            st.markdown(
                                f"**Step {index}: "
                                f"`{trace.get('tool', 'unknown')}`**"
                            )

                            st.json(
                                {
                                    "arguments": trace.get(
                                        "arguments",
                                        {},
                                    ),
                                    "result": trace.get(
                                        "result",
                                        {},
                                    ),
                                }
                            )

                # ---------------------------------------------------
                # Architecture reminder
                # ---------------------------------------------------

                st.caption(
                    "AI output is advisory. The deterministic "
                    "reconciliation result remains the financial "
                    "source of truth."
                )

            except Exception as exc:

                st.error(
                    f"Investigation failed: {exc}"
                )
    # -------------------------------------------------------------------
# Investigation History
# -------------------------------------------------------------------
if exceptions_to_review:
    audit_records = get_audit_for_order(selected.order_id)

    st.divider()
    st.subheader("Investigation History")

    if not audit_records:
        st.info(
            "No previous AI investigations have been recorded "
            "for this transaction."
        )
    else:
        history_df = pd.DataFrame(
            [
                {
                    "Timestamp": record.get("timestamp", ""),
                    "Exception": (
                        record.get("exception_type", "") or ""
                    ).replace("_", " ").title(),
                    "AI Confidence": (
                        f"{float(record.get('ai_confidence', 0)):.0%}"
                    ),
                    "Human Review": (
                        "Required"
                        if record.get(
                            "requires_human_review",
                            True,
                        )
                        else "Not required"
                    ),
                    "Recommended Action": record.get(
                        "recommended_action",
                        "",
                    ),
                }
                for record in reversed(audit_records)
            ]
        )

        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
        )       