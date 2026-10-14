import pytest
import uuid
import json
from unittest.mock import MagicMock, patch
from app.models.schema import (
    AssessmentGenerateRequest, AssessmentQuestion, Citation,
    QuizSubmissionRequest, QuizSubmissionItem
)
from app.services.assessment.generator import (
    AssessmentService, normalize_text, compute_question_fingerprint
)
from app.db.storage import LocalStorageEngine
from app.services.learner.mastery_model import BayesianKnowledgeTracingService

# ==============================================================================
# Task B: MCQ Validation Tests
# ==============================================================================

def test_valid_mcq_validation():
    svc = AssessmentService()
    valid_q = {
        "prompt": "Which optimization algorithm uses negative gradients to update parameters?",
        "options": [
            "A) Gradient Descent",
            "B) Random Search",
            "C) Grid Search",
            "D) Simulated Annealing"
        ],
        "correct_answer": "A) Gradient Descent",
        "explanation": "Gradient descent computes the negative gradient to update parameters."
    }
    is_valid, err = svc.validate_mcq(valid_q)
    assert is_valid is True
    assert err is None

def test_invalid_mcq_rejection():
    svc = AssessmentService()

    # 1. Fewer than 2 options
    bad_opts = {
        "prompt": "What is overfitting?",
        "options": ["A) High variance"],
        "correct_answer": "A) High variance"
    }
    is_valid, err = svc.validate_mcq(bad_opts)
    assert is_valid is False
    assert "at least 2 options" in err

    # 2. Duplicate options
    dup_opts = {
        "prompt": "What is overfitting?",
        "options": ["A) High variance", "B) High variance", "C) Low bias", "D) High bias"],
        "correct_answer": "A) High variance"
    }
    is_valid, err = svc.validate_mcq(dup_opts)
    assert is_valid is False
    assert "duplicate" in err.lower()

    # 3. Correct answer does not match any option
    no_match = {
        "prompt": "What is overfitting?",
        "options": ["A) Low variance", "B) High bias", "C) Constant", "D) Undefined"],
        "correct_answer": "High variance"
    }
    is_valid, err = svc.validate_mcq(no_match)
    assert is_valid is False
    assert "does not correspond" in err

    # 4. Correct answer ambiguously matches multiple options
    ambig = {
        "prompt": "What is overfitting?",
        "options": ["High variance", "Very High variance"],
        "correct_answer": "variance"
    }
    is_valid, err = svc.validate_mcq(ambig)
    assert is_valid is False

# ==============================================================================
# Task B: Numerical Answer Tolerance Tests
# ==============================================================================

def test_numerical_answer_tolerance():
    svc = AssessmentService()

    # Correct within absolute tolerance
    assert svc._evaluate_numerical("1.502", "1.500", tolerance=0.01) is True
    # Incorrect outside tolerance
    assert svc._evaluate_numerical("1.58", "1.500", tolerance=0.01) is False

    # Negative numbers and scientific notation
    assert svc._evaluate_numerical("-0.05", "-0.051", tolerance=0.01) is True
    assert svc._evaluate_numerical("1e-3", "0.001", tolerance=1e-4) is True

    # Relative tolerance on large numbers
    assert svc._evaluate_numerical("1020", "1000", tolerance=1.0) is True  # within 5% relative
    assert svc._evaluate_numerical("1150", "1000", tolerance=1.0) is False

    # Detailed evaluation feedback
    is_corr, diff, allowed = svc._evaluate_numerical_details("2.05", "2.00", tolerance=0.1)
    assert is_corr is True
    assert round(diff, 2) == 0.05

# ==============================================================================
# Task B: Short-Answer Grading & Arbitrary Substring Rejection
# ==============================================================================

def test_short_answer_grading():
    svc = AssessmentService()

    # Exact match (normalized)
    is_corr, score, method, _ = svc._evaluate_short_answer_robust(
        "Standardizing feature representations",
        "standardizing feature representations"
    )
    assert is_corr is True
    assert score == 1.0
    assert method == "exact"

    # Rubric key concepts coverage
    rubric = {"key_concepts": ["standardization", "zero mean", "variance"]}
    is_corr, score, method, _ = svc._evaluate_short_answer_robust(
        "Standardization of inputs to zero mean and unit variance",
        "Feature normalization rescales inputs to zero mean and unit variance",
        rubric=rubric
    )
    assert is_corr is True
    assert method in ("rubric", "semantic_lexical")

    # Strict rejection of arbitrary substring matching
    # (Student writing a common stopword or partial substring must NOT be graded correct)
    mock_llm_eval = json.dumps({"is_acceptable": False, "score": 0.0, "feedback": "Arbitrary substring rejected."})
    with patch("app.core.gemini.gemini_service.generate_text", return_value=mock_llm_eval):
        is_corr_sub, score_sub, _, _ = svc._evaluate_short_answer_robust(
            "the",
            "The gradient descent algorithm iteratively updates parameters"
        )
        assert is_corr_sub is False
        assert score_sub == 0.0

        is_corr_sub2, _, _, _ = svc._evaluate_short_answer_robust(
            "gradient",
            "The gradient descent algorithm iteratively updates parameters towards the minimum"
        )
        assert is_corr_sub2 is False

# ==============================================================================
# Task A & B: Source Citation Validation
# ==============================================================================

def test_source_citation_validation(tmp_path):
    db_file = str(tmp_path / "test_citations.db")
    test_storage = LocalStorageEngine(db_path=db_file)
    c = test_storage.create_course(title="Calculus")
    d = test_storage.create_document(course_id=c["id"], filename="Calculus_Ch1.pdf", file_type="pdf", file_path="fake.pdf")
    test_storage.save_chunks([{
        "id": "c1",
        "document_id": d["id"],
        "course_id": c["id"],
        "chunk_index": 0,
        "content": "The derivative represents the instantaneous rate of change of a function.",
        "source_type": "pdf",
        "page_number": 14,
        "slide_number": None,
        "start_timestamp": None,
        "end_timestamp": None,
        "topic": "Derivatives",
        "concept": "Rate of Change",
        "embedding": [0.0] * 768,
        "metadata": {"chapter": "1"}
    }])

    svc = AssessmentService()
    with patch("app.services.assessment.generator.storage", test_storage):
        with patch("app.services.assessment.generator.gemini_service.is_configured", return_value=False):
            res = svc.generate_assessment(AssessmentGenerateRequest(
                course_id=c["id"],
                question_count=1,
                question_type="mcq"
            ))
            assert len(res.questions) == 1
            q = res.questions[0]
            # Citation must match real chunk from database
            assert q.citation.source_file == "Calculus_Ch1.pdf"
            assert q.citation.page_number == 14
            assert q.citation.topic == "Derivatives"

# ==============================================================================
# Task A: Unsupported Topic Rejection
# ==============================================================================

def test_unsupported_topic_rejection(tmp_path):
    db_file = str(tmp_path / "test_unsupported.db")
    test_storage = LocalStorageEngine(db_path=db_file)
    c = test_storage.create_course(title="Intro Biology")
    d = test_storage.create_document(course_id=c["id"], filename="Bio.pdf", file_type="pdf", file_path="fake.pdf")
    test_storage.save_chunks([{
        "id": "c1",
        "document_id": d["id"],
        "course_id": c["id"],
        "chunk_index": 0,
        "content": "Photosynthesis converts light energy into chemical energy.",
        "source_type": "pdf",
        "page_number": 2,
        "topic": "Photosynthesis",
        "embedding": [0.0] * 768,
        "metadata": {}
    }])

    svc = AssessmentService()
    with patch("app.services.assessment.generator.storage", test_storage):
        # Requesting a topic not present in the course
        with pytest.raises(ValueError) as exc:
            svc.generate_assessment(AssessmentGenerateRequest(
                course_id=c["id"],
                topics=["Quantum Computing"],
                question_count=2
            ))
        assert "insufficient supporting material" in str(exc.value).lower()

# ==============================================================================
# Task C: Duplicate Detection
# ==============================================================================

def test_duplicate_detection():
    svc = AssessmentService(duplicate_similarity_threshold=0.85)
    delivered = [
        "what is the primary role of gradient descent in optimization",
        "how does feature normalization prevent gradient explosion"
    ]

    # Exact duplicate
    assert svc.is_duplicate_prompt(
        "What is the primary role of gradient descent in optimization?",
        delivered
    ) is True

    # High similarity variant
    assert svc.is_duplicate_prompt(
        "What is the main role of gradient descent in optimization?",
        delivered
    ) is True

    # Novel question
    assert svc.is_duplicate_prompt(
        "Explain backpropagation through computational graphs.",
        delivered
    ) is False

    # Fingerprint stability
    fp1 = compute_question_fingerprint("What is gradient descent?", "Optimization")
    fp2 = compute_question_fingerprint("what is gradient descent", "optimization")
    assert fp1 == fp2

# ==============================================================================
# Task D: Student Answer Persistence & Repeated Submission Prevention
# ==============================================================================

def test_answer_persistence_and_submission_idempotency(tmp_path):
    db_file = str(tmp_path / "test_attempts.db")
    test_storage = LocalStorageEngine(db_path=db_file)
    bkt = BayesianKnowledgeTracingService()

    # Seed assessment in test storage
    q_id = str(uuid.uuid4())
    cit = Citation(source_file="Notes.pdf", source_type="pdf", page_number=1, excerpt="Notes excerpt", topic="Neural Networks")
    q = AssessmentQuestion(
        id=q_id,
        topic_name="Neural Networks",
        question_type="mcq",
        prompt="What activation function introduces non-linearity?",
        options=["A) ReLU", "B) Identity", "C) Linear", "D) Constant"],
        correct_answer="A) ReLU",
        explanation="ReLU is non-linear.",
        citation=cit
    )

    assessment_id = str(uuid.uuid4())
    test_storage.save_assessment({
        "id": assessment_id,
        "course_id": "c1",
        "user_id": "test_student",
        "title": "Quiz 1",
        "assessment_type": "practice",
        "difficulty": "intermediate",
        "total_questions": 1,
        "score": None,
        "status": "generated",
        "questions": [q.model_dump()],
        "misconceptions": []
    })

    svc = AssessmentService()
    sub_req = QuizSubmissionRequest(
        assessment_id=assessment_id,
        user_id="test_student",
        answers=[QuizSubmissionItem(question_id=q_id, student_answer="A) ReLU")]
    )

    with patch("app.services.assessment.generator.storage", test_storage):
        with patch("app.services.learner.mastery_model.storage", test_storage):
            # First submission: grades and updates BKT mastery
            res1 = svc.grade_and_diagnose(sub_req)
            assert res1.score == 1.0
            assert res1.correct_count == 1
            m_first = test_storage.get_topic_mastery("test_student", "Neural Networks")["mastery_score"]
            assert m_first > 0.15

            # Answers persisted in assessment_answers table
            answers = test_storage.get_assessment_answers(assessment_id)
            assert len(answers) == 1
            assert answers[0]["is_correct"] == 1
            assert answers[0]["submitted_answer"] == "A) ReLU"

            # Second submission (Idempotency): Must NOT re-apply BKT mastery update
            res2 = svc.grade_and_diagnose(sub_req)
            m_second = test_storage.get_topic_mastery("test_student", "Neural Networks")["mastery_score"]
            # Mastery must be identical, not incremented a second time!
            assert m_second == m_first

# ==============================================================================
# Task E: Adaptive Topic Selection & Diagnostic Assessment
# ==============================================================================

def test_adaptive_topic_selection_prioritizes_weak_topics():
    svc = AssessmentService()
    chunks = [
        {"id": "c_strong", "topic": "Supervised Learning", "content": "Linear models"},
        {"id": "c_weak", "topic": "Backpropagation", "content": "Chain rule gradients"},
        {"id": "c_mid", "topic": "Regularization", "content": "L2 penalty weight decay"}
    ]

    req = AssessmentGenerateRequest(course_id="c1", user_id="student_1", difficulty="adaptive")

    mock_masteries = [
        {"topic_name": "Supervised Learning", "mastery_score": 0.90},
        {"topic_name": "Backpropagation", "mastery_score": 0.20},
        {"topic_name": "Regularization", "mastery_score": 0.60}
    ]

    with patch("app.services.assessment.generator.storage.list_topic_masteries", return_value=mock_masteries):
        prioritized = svc._prioritize_chunks_adaptively(chunks, req)
        # Weakest topic (Backpropagation with 0.20) must be prioritized first
        assert prioritized[0]["topic"] == "Backpropagation"
        # Strongest topic (Supervised Learning with 0.90) must be placed last
        assert prioritized[-1]["topic"] == "Supervised Learning"

def test_diagnostic_assessment_interleaves_topics():
    svc = AssessmentService()
    chunks = [
        {"id": "c1", "topic": "Topic A", "content": "A1"},
        {"id": "c2", "topic": "Topic A", "content": "A2"},
        {"id": "c3", "topic": "Topic B", "content": "B1"},
        {"id": "c4", "topic": "Topic C", "content": "C1"}
    ]
    req = AssessmentGenerateRequest(course_id="c1", assessment_type="diagnostic")
    interleaved = svc._prioritize_chunks_adaptively(chunks, req)
    # First 3 chunks must sample distinct topics
    topics_first_3 = [c["topic"] for c in interleaved[:3]]
    assert len(set(topics_first_3)) == 3
