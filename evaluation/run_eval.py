import argparse
import os
import sys
import tempfile
import time
from typing import Dict, List
from unittest.mock import patch

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.workflows.graph import run_workflow
from evaluation.dataset import SYNTHETIC_EVAL_DATASET


def simulate_llm_response(content: str) -> Dict[str, any]:
    """Deterministic mock provider for offline reproducibility."""
    lower = content.lower()
    if "admin override mode" in lower or "ignore all previous" in lower:
        return {"classification": "General_Correspondence", "confidence": 0.20}
    if "master software license" in lower:
        return {"classification": "Contract", "confidence": 0.95}
    if "invoice #inv-2026-902" in lower:
        return {"classification": "Invoice", "confidence": 0.92}
    if "invoice #inv-2026-901" in lower:
        return {"classification": "Invoice", "confidence": 0.96}
    if "subject: quick update" in lower:
        return {"classification": "General_Correspondence", "confidence": 0.35}
    return {"classification": "Unknown", "confidence": 0.0}


def simulate_extraction_response(content: str, doc_type: str) -> Dict[str, any]:
    """Deterministic extraction mock provider."""
    if "invoice #inv-2026-901" in content.lower():
        return {"subtotal": 5000.0, "tax": 500.0, "total_due": 5500.0, "vendor": "Apex Cloud"}
    if "invoice #inv-2026-902" in content.lower():
        return {"subtotal": 1200.0, "tax": 120.0, "total_due": 1500.0, "vendor": "Office Hub"}
    if "master software license" in content.lower():
        return {"parties": ["DataCore", "Global Analytics"], "term_months": 24}
    return {}


def run_evaluation(use_live_models: bool = False):
    print("=" * 70)
    print("AI Document Processing Agent - Synthetic Evaluation Harness")
    print(f"Mode: {'LIVE GROQ LLM' if use_live_models else 'REPRODUCIBLE MOCK PROVIDER'}")
    print(f"Dataset Size: {len(SYNTHETIC_EVAL_DATASET)} synthetic fixtures")
    print("=" * 70)

    results = []
    start_total = time.time()

    for item in SYNTHETIC_EVAL_DATASET:
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
            tf.write(item["content"])
            temp_path = tf.name

        t0 = time.time()
        if not use_live_models:
            with patch("app.workflows.nodes.run_classification_crew", side_effect=simulate_llm_response), \
                 patch("app.workflows.nodes.run_extraction_crew", side_effect=simulate_extraction_response):
                wf_res = run_workflow(item["id"], temp_path)
        else:
            wf_res = run_workflow(item["id"], temp_path)
        elapsed_ms = (time.time() - t0) * 1000.0

        classification = wf_res.get("classification")
        confidence = wf_res.get("confidence_score", 0.0)
        errors = wf_res.get("validation_errors", [])
        next_step = wf_res.get("next_step")

        is_correct_class = classification == item["expected_classification"]
        is_stp = (confidence >= 0.70) and (not errors) and (next_step != "manual_review")
        routed_to_review = next_step == "manual_review" or len(errors) > 0

        results.append({
            "id": item["id"],
            "name": item["name"],
            "classification": classification,
            "expected_class": item["expected_classification"],
            "confidence": confidence,
            "correct_classification": is_correct_class,
            "stp": is_stp,
            "expected_stp": item["expect_stp"],
            "has_validation_error": len(errors) > 0,
            "routed_to_review": routed_to_review,
            "elapsed_ms": elapsed_ms,
        })

    total_time_ms = (time.time() - start_total) * 1000.0

    # Summary metrics
    n = len(results)
    class_acc = sum(1 for r in results if r["correct_classification"]) / n * 100.0
    stp_count = sum(1 for r in results if r["stp"])
    stp_rate = stp_count / n * 100.0
    review_rate = sum(1 for r in results if r["routed_to_review"]) / n * 100.0
    val_err_rate = sum(1 for r in results if r["has_validation_error"]) / n * 100.0
    avg_latency = sum(r["elapsed_ms"] for r in results) / n

    print("\nDocument-Level Results:")
    print(f"{'ID':<15} {'Classification':<25} {'Conf':<6} {'STP':<6} {'Review':<8} {'Time (ms)':<10}")
    print("-" * 75)
    for r in results:
        stp_str = "YES" if r["stp"] else "NO"
        rev_str = "YES" if r["routed_to_review"] else "NO"
        print(f"{r['id']:<15} {r['classification']:<25} {r['confidence']:<6.2f} {stp_str:<6} {rev_str:<8} {r['elapsed_ms']:<10.1f}")

    print("\nAggregate Metrics:")
    print(f"- Total Documents: {n}")
    print(f"- Classification Accuracy: {class_acc:.1f}%")
    print(f"- Straight-Through Processing (STP) Rate: {stp_rate:.1f}% ({stp_count}/{n})")
    print(f"- Manual Review Routing Rate: {review_rate:.1f}%")
    print(f"- Validation Error Rate: {val_err_rate:.1f}%")
    print(f"- Mean Processing Duration: {avg_latency:.1f} ms")
    print(f"- Total Evaluation Wall Time: {total_time_ms:.1f} ms")
    print("\n" + "=" * 70)
    print("Methodology & Notes:")
    print("1. Synthetic dataset tests schema boundaries, arithmetic errors, and injection attempts.")
    print("2. Straight-Through Processing (STP) is strictly defined as: high confidence (>=0.70),")
    print("   zero validation errors, and completion without entering the manual review state.")
    print("3. Historical claims (such as 76% STP on 100 documents) require the original private dataset")
    print("   and are not reproduced by this minimal synthetic test set.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run synthetic document processing evaluation")
    parser.add_argument("--live", action="store_true", help="Use live Groq API instead of mock provider")
    args = parser.parse_args()
    run_evaluation(use_live_models=args.live)
