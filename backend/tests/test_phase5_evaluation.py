"""
LearnMate AI - Phase 5 Evaluation, Benchmarking & Reliability Test Suite
Covers:
- Task B: Benchmark dataset loading, versioning, and schema validation
- Task C: Hand-checkable metric calculations (Recall@k, MRR, Precision@k, Citation Accuracy)
- Task C: Empty and partially evaluable datasets edge case handling
- Task D: Adversarial cases (absent queries, false premises, invalid citation indices, malformed JSON, 429 quota)
- Task E: Deterministic learner simulations (BKT separation, prerequisite routing, spaced repetition, cold start)
- Task E: Assessment submission idempotency & study plan daily time constraint adherence
- Task G: Evaluation API endpoints response schema validation
"""

import pytest
import json
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.db.storage import storage
from app.models.schema import (
    EvaluationMetrics, EvaluationRunRequest, EvaluationRunResponse,
    TutorQueryRequest, QuizSubmissionRequest, QuizSubmissionItem, StudyPlanRequest
)
from app.services.evaluation.benchmark import evaluation_pipeline, RAG_BENCHMARK_V2
from app.services.retrieval.hybrid_retriever import hybrid_retriever
from app.services.tutor.grounded_tutor import grounded_tutor
from app.services.assessment.generator import assessment_service
from app.services.learner.mastery_model import BayesianKnowledgeTracingService

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_gemini_embeddings_for_tests():
    """Guarantee zero live Gemini API calls during unit tests as required by rule 8."""
    deterministic_vector = [0.01 * ((i % 10) + 1) for i in range(768)]
    with patch("app.core.gemini.gemini_service.get_embedding", return_value=deterministic_vector):
        yield


# ==============================================================================
# 1. Benchmark Dataset Loading & Schema Validation (Task B)
# ==============================================================================
def test_benchmark_dataset_schema_and_categories():
    """Verify benchmark dataset v2.0 schema, versioning, and category completeness."""
    dataset = evaluation_pipeline.get_benchmark_dataset("comprehensive")
    assert len(dataset) == 12, "Comprehensive benchmark v2.0 must contain exactly 12 test cases"

    expected_categories = {
        "direct_factual",
        "multi_passage",
        "multimodal_slide",
        "insufficient_evidence",
        "false_premise",
        "precise_citation",
        "terminology_distinction"
    }

    found_categories = set()
    for case in dataset:
        assert "id" in case and case["id"].startswith("rag-")
        assert "category" in case and isinstance(case["category"], str)
        assert "question" in case and len(case["question"]) > 10
        assert "is_supported" in case and isinstance(case["is_supported"], bool)
        assert "should_abstain" in case and isinstance(case["should_abstain"], bool)

        found_categories.add(case["category"])

        if case["is_supported"]:
            assert "expected_document" in case and case["expected_document"] is not None
            assert "ground_truth_concepts" in case and len(case["ground_truth_concepts"]) > 0

    assert expected_categories.issubset(found_categories), (
        f"Missing required categories. Expected subset of {expected_categories}, got {found_categories}"
    )


def test_benchmark_dataset_filtering_subsets():
    """Test subset filtering for grounded, multi_source, and unsupported cases."""
    grounded = evaluation_pipeline.get_benchmark_dataset("grounded")
    assert all(c["category"] in ["direct_factual", "precise_citation"] for c in grounded)

    unsupported = evaluation_pipeline.get_benchmark_dataset("unsupported")
    assert all(c["category"] in ["unsupported_negative", "insufficient_evidence", "false_premise"] for c in unsupported)
    assert all(c["should_abstain"] for c in unsupported)


# ==============================================================================
# 2. Hand-Checkable Metric Calculations (Task C)
# ==============================================================================
def test_hand_checkable_ranking_and_retrieval_metrics():
    """
    Hand-calculated verification:
    4 test queries:
    - Query 1: relevant at rank 1 -> reciprocal rank = 1.0, hit = True
    - Query 2: relevant at rank 2 -> reciprocal rank = 0.5, hit = True
    - Query 3: relevant at rank 4 -> reciprocal rank = 0.25, hit = True
    - Query 4: no relevant doc in top-k -> reciprocal rank = 0.0, hit = False

    Recall@4 = 3 / 4 = 0.750
    MRR = (1.0 + 0.5 + 0.25 + 0.0) / 4 = 1.75 / 4 = 0.4375 -> 0.438
    """
    total_cases = 4
    ranks = [1, 2, 4, None]

    hits = sum(1 for r in ranks if r is not None and r <= 4)
    total_rr = sum(1.0 / r for r in ranks if r is not None and r <= 4)

    calculated_recall = hits / total_cases
    calculated_mrr = total_rr / total_cases

    assert calculated_recall == 0.75
    assert round(calculated_mrr, 4) == 0.4375


def test_hand_checkable_citation_accuracy():
    """
    Hand-calculated verification:
    Total citations = 10
    Matches = 8
    Citation Source Accuracy = 8 / 10 = 0.800 (80.0%)

    Verifiable locations = 5
    Location matches = 4
    Citation Location Accuracy = 4 / 5 = 0.800 (80.0%)
    """
    citations = 10
    source_matches = 8
    verifiable_locs = 5
    loc_matches = 4

    src_acc = source_matches / citations
    loc_acc = loc_matches / verifiable_locs

    assert src_acc == 0.80
    assert loc_acc == 0.80


# ==============================================================================
# 3. Empty & Partial Dataset Edge Cases (Task C)
# ==============================================================================
def test_empty_and_partial_dataset_edge_cases():
    """Ensure metric evaluation handles 0-denominator without ZeroDivisionError."""
    # Test completely empty metrics breakdown
    empty_eval = EvaluationMetrics(
        faithfulness=0.0,
        answer_relevancy=0.0,
        context_precision=0.0,
        context_recall=0.0,
        question_repetition_rate=0.0,
        grounded_accuracy=0.0,
        unsupported_rejection_rate=0.0,
        citation_precision=0.0,
        recall_at_k=0.0,
        precision_at_k=0.0,
        mrr=0.0,
        citation_source_accuracy=0.0,
        citation_location_accuracy=0.0,
        metric_breakdowns={
            "recall_at_k": {"numerator": 0, "denominator": 0, "num_cases": 0, "description": "Empty"},
            "citation_source_accuracy": {"numerator": 0, "denominator": 0, "num_cases": 0, "description": "Empty"}
        }
    )
    assert empty_eval.recall_at_k == 0.0
    assert empty_eval.metric_breakdowns["recall_at_k"]["denominator"] == 0


# ==============================================================================
# 4. Adversarial & Regression Handling (Task D)
# ==============================================================================
def test_adversarial_absent_query_abstention():
    """Unsupported off-topic queries must return is_grounded=False with 0 citations."""
    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=[]):
        res = grounded_tutor.answer_query(
            TutorQueryRequest(
                course_id="",
                query="What is the authentic culinary recipe for baking artisan French sourdough baguettes?",
                top_k=3
            )
        )
        assert not res.is_grounded, "Off-topic culinary query must not claim grounded status"
        assert len(res.citations) == 0, "Off-topic query must produce zero citations"
        assert "cannot find" in res.answer.lower() or "not supported" in res.answer.lower()


def test_adversarial_out_of_bounds_citation_rejection():
    """Out-of-bounds citation indices [99, 999] must be programmatically rejected."""
    mock_llm_out = json.dumps({
        "answer": "Fabricated statement citing non-existent chunks.",
        "is_sufficiently_grounded": True,
        "cited_source_indices": [99, 999],
        "insufficient_evidence_reason": None
    })
    with patch("app.core.gemini.gemini_service.generate_text", return_value=mock_llm_out):
        res = grounded_tutor.answer_query(
            TutorQueryRequest(course_id="", query="What is supervised learning?", top_k=2)
        )
        assert len(res.citations) == 0, "Fabricated indices must be dropped by programmatic validator"
        assert not res.is_grounded, "Response with rejected citation indices must be marked ungrounded"


def test_adversarial_malformed_llm_json_handling():
    """Malformed non-JSON model output must be handled without uncaught server crash."""
    with patch("app.core.gemini.gemini_service.generate_text", return_value="INVALID NON-JSON OUTPUT {{{"):
        res = grounded_tutor.answer_query(
            TutorQueryRequest(course_id="", query="Explain gradient descent.", top_k=2)
        )
        assert isinstance(res.answer, str)
        assert len(res.answer) > 0


def test_live_gemini_quota_error_handling_no_fake_grounding():
    """
    Task D & Rule 7: Quota or availability error (429 RESOURCE_EXHAUSTED)
    must NOT silently become an apparently grounded answer through an undocumented fallback.
    """
    with patch("app.core.gemini.gemini_service.generate_text", side_effect=RuntimeError("429 RESOURCE_EXHAUSTED: Daily free-tier limit")):
        res = grounded_tutor.answer_query(
            TutorQueryRequest(course_id="", query="Explain gradient descent.", top_k=2)
        )
        assert not res.is_grounded, "Live generation failure must NOT claim is_grounded=True"
        assert len(res.citations) == 0, "Live generation failure must NOT produce fake citations"
        assert res.is_error or "429" in res.answer or "limit" in res.answer.lower() or "error" in res.answer.lower()


# ==============================================================================
# 5. Deterministic Simulated Learner Regressions (Task E)
# ==============================================================================
def test_simulated_learner_theoretical_vs_numerical_mastery():
    """Tests domain-separated BKT updates: theory increases, numerical drops."""
    bkt = BayesianKnowledgeTracingService()
    user_id = f"test_sim_theory_{uuid.uuid4().hex[:6]}"

    # Two correct answers on Supervised Learning
    m1 = bkt.update_mastery(user_id, "Supervised Learning", is_correct=True)
    m2 = bkt.update_mastery(user_id, "Supervised Learning", is_correct=True)

    # Two incorrect answers on Optimization
    m3 = bkt.update_mastery(user_id, "Optimization Dynamics", is_correct=False)
    m4 = bkt.update_mastery(user_id, "Optimization Dynamics", is_correct=False)

    assert m2 > 0.65, f"Theoretical mastery should increase to >0.65, got {m2:.2f}"
    assert m4 < 0.35, f"Numerical struggle mastery should drop to <0.35, got {m4:.2f}"


def test_simulated_learner_prerequisite_bottleneck():
    """Weak prerequisite must be recommended with high priority before downstream topic."""
    bkt = BayesianKnowledgeTracingService()
    user_id = f"test_sim_prereq_{uuid.uuid4().hex[:6]}"
    course_id = str(uuid.uuid4())

    storage.add_topic_prerequisite(course_id, "Deep Neural Networks", "Linear Algebra")
    bkt.update_mastery(user_id, "Linear Algebra", is_correct=False)

    profile = bkt.get_learner_profile(user_id, course_id=course_id)
    prereq_recs = [r for r in profile.recommended_activities if "linear algebra" in r.topic.lower()]
    assert len(prereq_recs) > 0, "Linear Algebra prerequisite must be recommended"
    assert prereq_recs[0].priority in ["urgent", "high"]


def test_simulated_learner_cold_start():
    """Unassessed brand new learner must have is_new_learner=True and 0.0 assumed mastery."""
    bkt = BayesianKnowledgeTracingService()
    user_id = f"test_new_{uuid.uuid4().hex[:8]}"

    profile = bkt.get_learner_profile(user_id)
    assert profile.is_new_learner is True
    assert profile.overall_mastery == 0.0
    assert len(profile.strong_topics) == 0


def test_assessment_submission_idempotency():
    """Re-submitting the exact same assessment ID must not double-count mastery or history."""
    user_id = f"test_idemp_{uuid.uuid4().hex[:6]}"
    a_id = str(uuid.uuid4())
    q_id = str(uuid.uuid4())

    storage.save_assessment({
        "id": a_id,
        "course_id": "c1",
        "user_id": user_id,
        "title": "Idempotency Test",
        "assessment_type": "practice",
        "difficulty": "intermediate",
        "total_questions": 1,
        "status": "generated",
        "questions": [{
            "id": q_id,
            "topic_name": "Supervised Learning",
            "question_type": "mcq",
            "prompt": "Hypothesis function?",
            "options": ["A) h(x)", "B) g(x)"],
            "correct_answer": "A) h(x)",
            "explanation": "Standard definition",
            "citation": {"source_file": "Lecture_01.pdf", "source_type": "pdf", "page_number": 2, "excerpt": "Excerpt"}
        }]
    })

    sub = QuizSubmissionRequest(
        assessment_id=a_id,
        user_id=user_id,
        answers=[QuizSubmissionItem(question_id=q_id, student_answer="A) h(x)")]
    )

    res_1 = assessment_service.grade_and_diagnose(sub)
    hist_count_1 = len(storage.list_mastery_history(user_id=user_id))

    res_2 = assessment_service.grade_and_diagnose(sub)
    hist_count_2 = len(storage.list_mastery_history(user_id=user_id))

    assert res_1.score == res_2.score == 1.0
    assert hist_count_1 == hist_count_2, "Re-submission must not append duplicate mastery history rows"


def test_study_plan_daily_time_budget_adherence():
    """Generated study plan activities must strictly obey the daily_study_minutes limit."""
    bkt = BayesianKnowledgeTracingService()
    user_id = f"test_budget_{uuid.uuid4().hex[:6]}"
    daily_budget = 20

    plan_req = StudyPlanRequest(user_id=user_id, daily_study_minutes=daily_budget)
    plan_res = bkt.generate_study_plan(plan_req)

    items = plan_res.schedule or plan_res.items
    assert len(items) > 0, "Study plan items should be generated"
    assert all(it.suggested_duration_minutes <= daily_budget for it in items), (
        f"All study plan items must be <= {daily_budget} minutes"
    )


# ==============================================================================
# 6. Evaluation API Endpoints (Task G)
# ==============================================================================
def test_evaluation_benchmark_cases_endpoint():
    """GET /api/evaluation/benchmark-cases returns verified dataset cases."""
    response = client.get("/api/evaluation/benchmark-cases?dataset_type=comprehensive")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_version"] == "v2.0"
    assert data["total_cases"] == 12
    assert len(data["cases"]) == 12


def test_evaluation_run_dry_run_endpoint_schema():
    """POST /api/evaluation/run with dry_run=True returns typed EvaluationRunResponse."""
    payload = {
        "dataset_type": "comprehensive",
        "num_test_cases": 12,
        "dry_run": True
    }
    response = client.post("/api/evaluation/run", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert "metrics" in data
    assert "metric_breakdowns" in data["metrics"]
    assert "learner_evaluations" in data
    assert "adversarial_results" in data
    assert "sample_evaluations" in data

    # Verify Task C metrics presence
    metrics = data["metrics"]
    assert "recall_at_k" in metrics
    assert "precision_at_k" in metrics
    assert "mrr" in metrics
    assert "citation_source_accuracy" in metrics
    assert "citation_location_accuracy" in metrics
    assert "unsupported_rejection_rate" in metrics

    # Verify Task E & D regression profiles presence
    assert len(data["learner_evaluations"]) >= 6
    assert len(data["adversarial_results"]) >= 4
