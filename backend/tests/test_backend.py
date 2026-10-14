import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app, startup_seed_demo_data
from app.services.learner.mastery_model import mastery_service
from app.services.retrieval.hybrid_retriever import hybrid_retriever
from app.services.tutor.grounded_tutor import grounded_tutor
from app.services.assessment.generator import assessment_service
from app.models.schema import TutorQueryRequest
from app.db.storage import storage
from app.core.config import settings
from app.core.gemini import GeminiQuotaExceededError, GeminiServiceUnavailableError

startup_seed_demo_data()
client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_gemini_embeddings_for_tests():
    """Ensure zero live Gemini API calls during unit tests as required by rule 8."""
    deterministic_vector = [0.01 * ((i % 10) + 1) for i in range(768)]
    with patch("app.core.gemini.gemini_service.get_embedding", return_value=deterministic_vector):
        yield

def _get_seeded_ml_course():
    """Helper to locate the demonstration CS229 course reliably regardless of sorting order."""
    courses = storage.list_courses()
    cs229_list = [c for c in courses if "CS229" in c["title"]]
    if cs229_list:
        return cs229_list[0]
    return courses[0] if courses else None

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "storage_mode" in data

def test_courses_list_and_seeded_data():
    response = client.get("/api/courses")
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) >= 1
    # Locate seeded course by title
    cs229_courses = [c for c in courses if "CS229" in c["title"]]
    assert len(cs229_courses) >= 1
    c = cs229_courses[0]
    assert "CS229" in c["title"]
    assert c["documents_count"] >= 3

def test_hybrid_retrieval_and_citation_formatting():
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    results = hybrid_retriever.retrieve(
        query="feature normalization z-score scaling",
        course_id=c_id,
        top_k=3
    )
    assert len(results) > 0
    top = results[0]
    assert "normalization" in top["content"].lower() or "scaling" in top["content"].lower()
    assert top["page_number"] is not None

    citations = hybrid_retriever.format_citations(results)
    assert len(citations) == len(results)
    assert citations[0].source_file is not None

def test_grounded_tutor_answers_supported_query():
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    req = TutorQueryRequest(
        course_id=c_id,
        query="Why do we use feature normalization before gradient descent?",
        top_k=3
    )
    mock_tutor_res = json.dumps({
        "answer": "Feature normalization prevents oscillations and speeds up gradient descent convergence.",
        "is_sufficiently_grounded": True,
        "cited_source_indices": [1],
        "insufficient_evidence_reason": None
    })
    with patch("app.core.gemini.gemini_service.generate_text", return_value=mock_tutor_res):
        res = grounded_tutor.answer_query(req)
        assert res.is_grounded is True
        assert len(res.citations) > 0
        # Citations must preserve source location
        cit = res.citations[0]
        assert cit.page_number is not None or cit.slide_number is not None or cit.start_timestamp is not None

def test_grounded_tutor_rejects_unsupported_query():
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    req = TutorQueryRequest(
        course_id=c_id,
        query="What is the authentic recipe for baking French croissants with laminating butter?",
        top_k=3
    )
    with patch("app.services.retrieval.hybrid_retriever.gemini_service.get_embedding", return_value=[0.01] * 768):
        res = grounded_tutor.answer_query(req)
        # Must flag unsupported query and never hallucinate citations
        assert res.is_grounded is False
        assert len(res.citations) == 0
        assert "cannot find" in res.answer.lower() or "not contain" in res.answer.lower()

def test_bayesian_knowledge_tracing_deterministic_math():
    user = "test_bkt_user"
    topic = "Regression Testing"
    
    # 1. Update on correct observation
    m1 = mastery_service.update_mastery(user, topic, is_correct=True)
    assert 0.0 < m1 <= 1.0
    
    # 2. Second correct observation should monotonically increase mastery
    m2 = mastery_service.update_mastery(user, topic, is_correct=True)
    assert m2 > m1

    # 3. An incorrect observation should decrease mastery
    m3 = mastery_service.update_mastery(user, topic, is_correct=False)
    assert m3 < m2

def test_learner_profile_endpoint():
    res = client.get("/api/learner/profile?user_id=student_default")
    assert res.status_code == 200
    data = res.json()
    assert "overall_mastery" in data
    assert len(data["topics"]) > 0
    assert "recommended_activities" in data

def test_assessment_generation_and_grading():
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    q_idx = 0
    def _mock_q(prompt, system_instruction=None, json_schema=None, **kwargs):
        nonlocal q_idx
        q_idx += 1
        return json.dumps({
            "prompt": f"Objective question {q_idx}: What is the role of gradient descent in machine learning?",
            "question_type": "mcq",
            "options": [
                "A) Minimize the loss function iteratively",
                "B) Maximize parameter variance",
                "C) Double dataset size",
                "D) Calculate exact matrix inverse"
            ],
            "correct_answer": "A) Minimize the loss function iteratively",
            "explanation": "Gradient descent minimizes empirical loss along the negative gradient direction.",
            "concept": "Gradient Descent",
            "difficulty": "medium",
            "numerical_tolerance": None,
            "numerical_unit": None,
            "rubric_concepts": []
        })

    with patch("app.core.gemini.gemini_service.generate_text", side_effect=_mock_q):
        gen_res = client.post("/api/assessments/generate", json={
            "course_id": c_id,
            "difficulty": "intermediate",
            "question_count": 3,
            "allow_revision": True
        })
        assert gen_res.status_code == 200
        assessment = gen_res.json()
        assert len(assessment["questions"]) == 3
        q0 = assessment["questions"][0]
        assert "citation" in q0
        assert q0["citation"]["source_file"] is not None

        # Submit answers
        sub_res = client.post("/api/assessments/submit", json={
            "assessment_id": assessment["id"],
            "user_id": "student_default",
            "answers": [
                {"question_id": q0["id"], "student_answer": q0["correct_answer"]}
            ]
        })
        assert sub_res.status_code == 200
        sub_data = sub_res.json()
        assert "score" in sub_data
        assert "mastery_updates" in sub_data

def test_evaluation_run():
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    mock_question_bank = [
        ("Explain the concept of learning rate in stochastic gradient optimization.", "mcq", ["A) Controls the step size along gradient descent", "B) Doubles dataset rows", "C) Removes outlier features", "D) Halts loss calculations"], "A) Controls the step size along gradient descent", "Controls the step size along the negative gradient vector."),
        ("Calculate the ratio of feature scale after standard z-score normalization.", "numerical", None, "1.5", "Directly computed from the sample variance."),
        ("Define how convex objective functions guarantee global convergence properties.", "short_answer", None, "Every local minimum of a convex function is a global minimum", "Fundamental theorem of convex optimization."),
        ("Describe the mechanism of early stopping during model regularization cycles.", "mcq", ["A) Halts training when validation loss stops improving", "B) Deletes random weights", "C) Increases model layers", "D) Resets momentum"], "A) Halts training when validation loss stops improving", "Monitors generalization performance."),
        ("Compute the Frobenius norm for an identity matrix of dimension two.", "numerical", None, "1.41", "Square root of the sum of squared diagonal elements."),
        ("What is the effect of batch normalization on internal covariate shift?", "short_answer", None, "Stabilizes layer input distributions across mini batches", "Maintains zero mean and unit variance."),
        ("Explain how dropout layers mitigate overfitting in deep artificial neural networks.", "mcq", ["A) Randomly deactivates activations during training passes", "B) Increases parameter counts", "C) Multiplies gradient rates", "D) Eliminates loss functions"], "A) Randomly deactivates activations during training passes", "Prevents complex co-adaptations of feature detectors."),
        ("Estimate the asymptotic memory complexity of storing an n-by-n covariance matrix.", "numerical", None, "4.0", "Proportional to n squared."),
        ("Why does coordinate descent update one parameter variable per cycle?", "short_answer", None, "Minimizes along single coordinate axes iteratively", "Solves one-dimensional optimization sub-problems.")
    ]
    eval_q_idx = 0
    def _mock_gen(prompt, system_instruction=None, json_schema=None, **kwargs):
        nonlocal eval_q_idx
        if json_schema and getattr(json_schema, "__name__", "") == "GeneratedQuestionLLMResponse":
            item = mock_question_bank[eval_q_idx % len(mock_question_bank)]
            eval_q_idx += 1
            p_text, q_type, opts, ans, expl = item
            return json.dumps({
                "prompt": p_text,
                "question_type": q_type,
                "options": opts,
                "correct_answer": ans,
                "explanation": expl,
                "concept": "Optimization",
                "difficulty": "medium",
                "numerical_tolerance": 0.05 if q_type == "numerical" else None,
                "numerical_unit": None,
                "rubric_concepts": ["minimization", "gradient", "iterative"] if q_type == "short_answer" else []
            })
        return json.dumps({
            "answer": "Based on the course excerpts, feature normalization standardizes scales and stabilizes training.",
            "is_sufficiently_grounded": True,
            "cited_source_indices": [1],
            "insufficient_evidence_reason": None
        })

    with patch("app.core.gemini.gemini_service.generate_text", side_effect=_mock_gen):
        eval_res = client.post("/api/evaluation/run", json={
            "course_id": c_id,
            "dataset_type": "grounded"
        })
        assert eval_res.status_code == 200
        data = eval_res.json()
        assert "metrics" in data
        m = data["metrics"]
        assert 0.0 <= m["faithfulness"] <= 1.0
        assert 0.0 <= m["answer_relevancy"] <= 1.0
        assert 0.0 <= m["unsupported_rejection_rate"] <= 1.0
        assert "simulation_results" in data
        assert "beginner" in data["simulation_results"]

# ==============================================================================
# Phase 1 Regression Tests: Grading, Validation & Multi-Course Stability
# ==============================================================================

def test_regression_incorrect_short_answer_substring_rejection():
    """Ensure arbitrary short substrings (e.g. 'the', 'in') are strictly rejected."""
    correct = "Standardizing input representations"

    mock_llm_eval = json.dumps({"is_acceptable": False, "score": 0.0, "feedback": "Incorrect answer."})
    with patch("app.core.gemini.gemini_service.generate_text", return_value=mock_llm_eval):
        # Trivial substrings that previously passed due to bidirectional substring matching
        assert assessment_service.is_answer_correct("the", correct, "short_answer") is False
        assert assessment_service.is_answer_correct("in", correct, "short_answer") is False
        assert assessment_service.is_answer_correct("a", correct, "short_answer") is False
        assert assessment_service.is_answer_correct("input", correct, "short_answer") is False
        assert assessment_service.is_answer_correct("representations", correct, "short_answer") is False

        # Blank answers explicitly handled
        assert assessment_service.is_answer_correct("", correct, "short_answer") is False
        assert assessment_service.is_answer_correct("   ", correct, "short_answer") is False
        assert assessment_service.is_answer_correct(None, correct, "short_answer") is False

def test_regression_correct_short_answer_normalization():
    """Ensure exact and normalized short answers are accepted without punctuation sensitivity."""
    correct = "Standardizing input representations"

    # Exact match
    assert assessment_service.is_answer_correct("Standardizing input representations", correct, "short_answer") is True
    # Case & whitespace normalization
    assert assessment_service.is_answer_correct("  standardizing   input   representations  ", correct, "short_answer") is True
    # Trailing punctuation
    assert assessment_service.is_answer_correct("Standardizing input representations.", correct, "short_answer") is True
    # Minor morphological variation / typo (SequenceMatcher ratio >= 0.85)
    assert assessment_service.is_answer_correct("Standardizing input representation", correct, "short_answer") is True

def test_regression_numerical_tolerance():
    """Ensure numerical evaluation uses configurable numerical tolerance and rejects non-numbers."""
    target = "1.5"

    # Exact string match
    assert assessment_service.is_answer_correct("1.5", target, "numerical") is True
    # Within 1e-3 default tolerance
    assert assessment_service.is_answer_correct("1.5004", target, "numerical", tolerance=1e-3) is True
    assert assessment_service.is_answer_correct("1.4996", target, "numerical", tolerance=1e-3) is True
    # Outside tolerance
    assert assessment_service.is_answer_correct("1.6", target, "numerical", tolerance=1e-3) is False
    assert assessment_service.is_answer_correct("1.4", target, "numerical", tolerance=1e-3) is False
    # Non-numeric garbage
    assert assessment_service.is_answer_correct("formula", target, "numerical") is False
    assert assessment_service.is_answer_correct("", target, "numerical") is False

def test_regression_invalid_mcq_answer_keys_rejected():
    """Verify that malformed or ambiguous MCQ questions are rejected."""
    # Less than two options
    q_single_opt = {
        "prompt": "What is gradient descent?",
        "options": ["A) An optimization algorithm"],
        "correct_answer": "A) An optimization algorithm"
    }
    assert assessment_service.is_valid_mcq(q_single_opt) is False

    # Correct answer not present in options
    q_missing_key = {
        "prompt": "What is gradient descent?",
        "options": ["A) Optimization algorithm", "B) Linear layer"],
        "correct_answer": "C) Loss function"
    }
    assert assessment_service.is_valid_mcq(q_missing_key) is False

    # Ambiguous duplicate options
    q_duplicate_opts = {
        "prompt": "What is gradient descent?",
        "options": ["A) Optimization", "B) Optimization"],
        "correct_answer": "Optimization"
    }
    assert assessment_service.is_valid_mcq(q_duplicate_opts) is False

    # Blank correct answer
    q_blank_key = {
        "prompt": "What is gradient descent?",
        "options": ["A) Optimization", "B) Linear layer"],
        "correct_answer": ""
    }
    assert assessment_service.is_valid_mcq(q_blank_key) is False

def test_regression_valid_mcq_answer_keys_accepted():
    """Verify that properly formed MCQs are validated and graded accurately."""
    options = [
        "A) Standardizing feature representations",
        "B) Discarding variance completely",
        "C) Increasing computational complexity",
        "D) Eliminating activations"
    ]
    q_valid = {
        "prompt": "What is the primary role of normalization?",
        "options": options,
        "correct_answer": "A) Standardizing feature representations"
    }
    assert assessment_service.is_valid_mcq(q_valid) is True

    # Student answers by letter identifier
    assert assessment_service.is_answer_correct("A", q_valid["correct_answer"], "mcq", options=options) is True
    assert assessment_service.is_answer_correct("a", q_valid["correct_answer"], "mcq", options=options) is True
    assert assessment_service.is_answer_correct("A)", q_valid["correct_answer"], "mcq", options=options) is True
    # Student answers by full option string
    assert assessment_service.is_answer_correct(options[0], q_valid["correct_answer"], "mcq", options=options) is True
    # Incorrect option choices
    assert assessment_service.is_answer_correct("B", q_valid["correct_answer"], "mcq", options=options) is False
    assert assessment_service.is_answer_correct("b", q_valid["correct_answer"], "mcq", options=options) is False
    assert assessment_service.is_answer_correct(options[1], q_valid["correct_answer"], "mcq", options=options) is False
    # Substring of option text must NOT award credit if student answers "the" or "in"
    assert assessment_service.is_answer_correct("the", q_valid["correct_answer"], "mcq", options=options) is False
    assert assessment_service.is_answer_correct("feature", q_valid["correct_answer"], "mcq", options=options) is False

def test_regression_course_selection_when_multiple_courses_exist():
    """Ensure courses are properly differentiated without cross-contamination."""
    courses = storage.list_courses()
    assert len(courses) >= 1
    
    # Query each course by specific ID via API
    for c in courses:
        res = client.get(f"/api/courses/{c['id']}")
        assert res.status_code == 200
        course_data = res.json()
        assert course_data["id"] == c["id"]
        assert course_data["title"] == c["title"]


# ==============================================================================
# Tasks 7A-7E: Retrieval Regression Tests
# ==============================================================================
def test_regression_7a_supported_question_retrieves_relevant_content():
    """
    Task 7A: A supported question must retrieve relevant content when the actual fixture contains it.
    Verifies that 'Explain the gradient descent parameter update rule' retrieves Slide 4 of Lecture 02.
    """
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    query = "Explain the gradient descent parameter update rule from my uploaded course materials."
    retrieved = hybrid_retriever.retrieve(
        query=query,
        course_id=c_id,
        top_k=5,
        min_relevance=settings.MIN_RELEVANCE_SCORE
    )
    assert len(retrieved) > 0, "Must retrieve matching chunks for supported question"
    top_chunk = retrieved[0]
    assert top_chunk["hybrid_score"] >= settings.MIN_RELEVANCE_SCORE
    assert "Lecture_02_Optimization_and_Gradient_Descent.pptx" in top_chunk["filename"]
    assert top_chunk.get("slide_number") == 4
    assert "theta := theta - alpha * grad(J(theta))" in top_chunk["content"]

    mock_llm = json.dumps({
        "answer": "According to Slide 4 of Lecture 02, the parameter theta is updated iteratively according to theta := theta - alpha * grad(J(theta)), where alpha represents the learning rate.",
        "is_sufficiently_grounded": True,
        "cited_source_indices": [1],
        "insufficient_evidence_reason": None
    })
    with patch("app.core.gemini.gemini_service.generate_text", return_value=mock_llm):
        res = grounded_tutor.answer_query(TutorQueryRequest(course_id=c_id, query=query, top_k=5))
        assert res.is_grounded is True
        assert len(res.citations) == 1
        assert res.citations[0].source_file == "Lecture_02_Optimization_and_Gradient_Descent.pptx"
        assert res.citations[0].slide_number == 4


def test_regression_7b_7c_unsupported_question_rejected_without_fabricated_citations():
    """
    Task 7B & 7C:
    A genuinely unsupported question must be rejected, and a rejected answer must NOT
    contain fabricated citations.
    """
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    unsupported_query = "Explain a topic that is definitely absent from my uploaded course materials."
    mock_abstain = json.dumps({
        "answer": "I cannot find this topic or concept in your uploaded course materials.",
        "is_sufficiently_grounded": False,
        "cited_source_indices": [],
        "insufficient_evidence_reason": "Topic is completely absent from course materials."
    })
    with patch("app.core.gemini.gemini_service.generate_text", return_value=mock_abstain):
        res = grounded_tutor.answer_query(TutorQueryRequest(course_id=c_id, query=unsupported_query, top_k=5))
        assert res.is_grounded is False
        assert len(res.citations) == 0, "Rejected answer must never fabricate citations"
        assert res.is_error is False
        assert "cannot find" in res.answer.lower() or "not contain" in res.answer.lower() or res.unsupported_reason is not None


def test_regression_7d_citation_metadata_matches_actual_retrieved_source():
    """
    Task 7D:
    Citation document and location metadata must match the actual retrieved source.
    """
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    query = "Explain the gradient descent parameter update rule."
    chunks = hybrid_retriever.retrieve(query=query, course_id=c_id, top_k=3)
    assert len(chunks) > 0
    top = chunks[0]

    citations = hybrid_retriever.format_citations([top])
    assert len(citations) == 1
    cit = citations[0]
    assert cit.source_file == top["filename"]
    assert cit.slide_number == top.get("slide_number")
    assert cit.page_number == top.get("page_number")
    assert cit.relevance_score == top.get("hybrid_score")


def test_regression_7e_retrieval_and_gemini_failures_never_fabricated():
    """
    Task 7E:
    Retrieval failures and Gemini API failures must not be silently converted into fabricated grounded answers.
    """
    ml_course = _get_seeded_ml_course()
    assert ml_course is not None
    c_id = ml_course["id"]

    # 1. Retrieval failure
    with patch.object(hybrid_retriever, "retrieve", side_effect=RuntimeError("Storage connection failed")):
        res_ret = grounded_tutor.answer_query(TutorQueryRequest(course_id=c_id, query="What is gradient descent?"))
        assert res_ret.is_grounded is False
        assert len(res_ret.citations) == 0
        assert res_ret.is_error is True
        assert res_ret.error_type == "retrieval_error"

    # 2. Gemini Quota failure during tutor generation
    with patch("app.core.gemini.gemini_service.generate_text", side_effect=GeminiQuotaExceededError("Rate limit exceeded")):
        res_q = grounded_tutor.answer_query(TutorQueryRequest(course_id=c_id, query="What is gradient descent?"))
        assert res_q.is_grounded is False
        assert len(res_q.citations) == 0
        assert res_q.is_error is True
        assert res_q.error_type == "quota_exceeded"

    # 3. Gemini Service Unavailable failure
    with patch("app.core.gemini.gemini_service.generate_text", side_effect=GeminiServiceUnavailableError("Model overloaded")):
        res_s = grounded_tutor.answer_query(TutorQueryRequest(course_id=c_id, query="What is gradient descent?"))
        assert res_s.is_grounded is False
        assert len(res_s.citations) == 0
        assert res_s.is_error is True
        assert res_s.error_type == "service_unavailable"


def test_regression_bm25plus_small_corpus_non_negative_idf():
    """
    Verifies that BM25Plus does not yield negative IDF on small single-chunk corpora,
    preventing keyword-matching chunks from being zeroed out.
    """
    dummy_chunks = [{
        "id": "single-1",
        "content": "Gradient descent parameter update rule updates parameters iteratively with alpha.",
        "filename": "lecture.pdf"
    }]
    scores, max_score = hybrid_retriever._score_bm25(
        "gradient descent parameter update rule",
        dummy_chunks
    )
    assert max_score > 0.0, "BM25 score must be strictly positive on matching chunk"
    assert scores[0] == 1.0

