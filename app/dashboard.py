import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.audit import log_investigation
from app.core.matcher import reconcile_all
from app.core.run_reconciliation import load_data


st.set_page_config(
    page_title="LedgerGuard AI",
    page_icon="🛡️",
    layout="wide",
)

st.title("LedgerGuard AI")
st.caption(
    "AI-assisted financial reconciliation and exception investigation"
)


# -------------------------------------------------------------------
# Load and reconcile data
# -------------------------------------------------------------------

orders, gateways, settlements = load_data()

results = reconcile_all(
    orders,
    gateways,
    settlements,
)


# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------


matched_count = sum(
    r.decision == "MATCH"
    for r in results
)

exception_count = sum(
    r.decision == "EXCEPTION"
    for r in results
)

review_count = sum(
    r.decision == "NEEDS_AI_REVIEW"
    for r in results
)


st.subheader("Reconciliation Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Orders Processed",
    len(results),
)

col2.metric(
    "Matched",
    matched_count,
)

col3.metric(
    "Exceptions",
    exception_count,
)

col4.metric(
    "AI Review",
    review_count,
)


# -------------------------------------------------------------------
# Results table
# -------------------------------------------------------------------

st.divider()

st.subheader("Transaction Results")


result_df = pd.DataFrame(
    [
        {
            "Order": r.order_id,
            "Decision": r.decision,
            "Gateway": r.gateway_id or "",
            "Settlement": r.settlement_id or "",
            "Score": round(r.score, 3),
            "Exception": r.exception_type or "",
        }
        for r in results
    ]
)


st.dataframe(
    result_df,
    use_container_width=True,
    hide_index=True,
)


# -------------------------------------------------------------------
# Investigation
# -------------------------------------------------------------------

st.divider()

st.subheader("Exception Investigation")


exceptions = [
    r
    for r in results
    if r.decision != "MATCH"
]


if not exceptions:

    st.success("No exceptions detected.")

else:

    selected_id = st.selectbox(
        "Select a transaction to investigate",
        [r.order_id for r in exceptions],
    )

    selected = next(
        r
        for r in exceptions
        if r.order_id == selected_id
    )


    st.write(f"### {selected.order_id}")


    info1, info2, info3 = st.columns(3)


    with info1:
        st.write("**Decision**")
        st.write(selected.decision)


    with info2:
        st.write("**Exception**")
        st.write(selected.exception_type or "None")


    with info3:
        st.write("**Deterministic Score**")
        st.write(f"{selected.score:.1%}")


    st.subheader("Deterministic Evidence")


    for evidence in selected.evidence:

        st.write(
            f"- **{evidence.factor}:** "
            f"{evidence.value}"
        )


    # ---------------------------------------------------------------
    # Gemini investigation
    # ---------------------------------------------------------------

    if st.button(
        "Investigate with LedgerGuard AI",
        type="primary",
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
                "amount": str(selected.settlement_amount),
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

                investigator = LedgerInvestigator()

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
                # Display AI result
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


            except Exception as exc:

                st.error(
                    f"Investigation failed: {exc}"
                )
