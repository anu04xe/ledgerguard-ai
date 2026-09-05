from collections import Counter
from typing import Dict, List

from app.core.models import ReconciliationResult


def evaluate_results(
    results: List[ReconciliationResult],
    ground_truth,
) -> Dict:
    """
    Evaluate deterministic reconciliation results against ground truth.

    IMPORTANT:
    Ground truth is used ONLY for evaluation.
    It is never consumed by the reconciliation engine.
    """

    truth_by_order = {
        record.order_id: record
        for record in ground_truth
    }

    total = 0
    correct = 0
    incorrect = 0

    false_positives = 0
    false_negatives = 0

    exception_breakdown = Counter()
    errors = []

    for result in results:
        truth = truth_by_order.get(result.order_id)

        if truth is None:
            continue

        total += 1

        expected_exception = truth.exception_type or ""

        # Ground truth considers anything with no exception a MATCH.
        expected_decision = (
            "MATCH"
            if truth.expected_outcome == "success"
            else "EXCEPTION"
        )

        actual_decision = result.decision

        # NEEDS_AI_REVIEW is treated as unresolved rather than MATCH.
        if actual_decision == expected_decision:
            correct += 1
        else:
            incorrect += 1

            if actual_decision == "MATCH":
                false_negatives += 1
            else:
                false_positives += 1

            errors.append(
                {
                    "order_id": result.order_id,
                    "expected": expected_decision,
                    "actual": actual_decision,
                    "exception_type": expected_exception,
                }
            )

        if expected_exception:
            exception_breakdown[expected_exception] += 1

    accuracy = correct / total if total else 0.0

    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": accuracy,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "exception_breakdown": dict(exception_breakdown),
        "errors": errors,
    }