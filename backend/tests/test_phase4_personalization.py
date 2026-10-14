import pytest
import uuid
from datetime import datetime, timezone, timedelta
from app.db.storage import LocalStorageEngine
from app.services.learner.mastery_model import BayesianKnowledgeTracingService
from app.services.assessment.generator import AssessmentService
from app.models.schema import (
    QuizSubmissionRequest, QuizSubmissionItem, StudyPlanRequest
)

@pytest.fixture
def storage():
    return LocalStorageEngine()

@pytest.fixture
def bkt_service(storage):
    return BayesianKnowledgeTracingService(storage=storage)

# ==============================================================================
# Task A & B: BKT Correct / Incorrect Math & Monotonicity
# ==============================================================================

def test_bkt_updates_after_correct_answers(bkt_service):
    user_id = f"user_correct_{uuid.uuid4().hex[:6]}"
    topic = "Convex Optimization"

    # Step 1: Update on first correct answer
    m1 = bkt_service.update_mastery(user_id, topic, is_correct=True)
    assert 0.0 < m1 <= 1.0
    # Expected value from standard formula with prior=0.15, transit=0.15, guess=0.20, slip=0.10: ~0.526
    assert abs(m1 - 0.5262) < 0.02

    # Step 2: Second correct answer should strictly monotonically increase
    m2 = bkt_service.update_mastery(user_id, topic, is_correct=True)
    assert m2 > m1

    # Step 3: Third correct answer should further increase mastery
    m3 = bkt_service.update_mastery(user_id, topic, is_correct=True)
    assert m3 > m2
    assert m3 > 0.80

def test_bkt_updates_after_incorrect_answers(bkt_service):
    user_id = f"user_incorrect_{uuid.uuid4().hex[:6]}"
    topic = "Principal Component Analysis"

    # Seed with high mastery first
    bkt_service.update_mastery(user_id, topic, is_correct=True)
    m_high = bkt_service.update_mastery(user_id, topic, is_correct=True)
    assert m_high > 0.60

    # An incorrect answer must decrease mastery
    m_after_fail = bkt_service.update_mastery(user_id, topic, is_correct=False)
    assert m_after_fail < m_high

    # Second failure should decrease it further
    m_after_fail2 = bkt_service.update_mastery(user_id, topic, is_correct=False)
    assert m_after_fail2 < m_after_fail

def test_configurable_bkt_parameters(storage):
    custom_bkt = BayesianKnowledgeTracingService(
        storage=storage,
        prior=0.30,
        transit=0.20,
        guess=0.10,
        slip=0.05
    )
    user_id = f"user_custom_{uuid.uuid4().hex[:6]}"
    topic = "Support Vector Machines"

    m1 = custom_bkt.update_mastery(user_id, topic, is_correct=True)
    # With higher prior and lower guess, first correct answer gives much higher posterior
    assert m1 > 0.70

# ==============================================================================
# Task B: Repeated Submission Idempotency & Persistence Across Restarts
# ==============================================================================

def test_repeated_submission_idempotency(storage):
    assessment_service = AssessmentService(storage=storage)
    course_list = storage.list_courses()
    course_id = course_list[0]["id"] if course_list else "test_c"
    user_id = f"user_idempotent_{uuid.uuid4().hex[:6]}"

    # Generate assessment
    q_data = [{
        "id": "q1",
        "topic_name": "Gradient Descent",
        "question_type": "mcq",
        "prompt": "What does gradient descent minimize?",
        "options": ["A) Loss", "B) Data", "C) Layers", "D) Epochs"],
        "correct_answer": "A) Loss",
        "explanation": "Minimizes the empirical risk / loss function.",
        "citation": {"source_file": "test.pdf", "source_type": "pdf", "excerpt": "Gradient descent minimizes the loss function.", "page_number": 1}
    }]
    a_id = str(uuid.uuid4())
    storage.save_assessment({
        "id": a_id,
        "course_id": course_id,
        "user_id": user_id,
        "title": "Idempotency Test Assessment",
        "assessment_type": "adaptive_quiz",
        "difficulty": "intermediate",
        "total_questions": 1,
        "status": "generated",
        "questions": q_data
    })
    assessment_id = a_id

    sub_req = QuizSubmissionRequest(
        assessment_id=assessment_id,
        user_id=user_id,
        answers=[QuizSubmissionItem(question_id="q1", student_answer="A) Loss")]
    )

    # First submission
    res1 = assessment_service.grade_and_diagnose(sub_req)
    assert res1.score == 1.0

    # Retrieve history count for this user
    history1 = storage.list_mastery_history(user_id=user_id)
    history_count_1 = len(history1)
    assert history_count_1 >= 1

    # Second submission with the exact same assessment_id (repeated submission)
    res2 = assessment_service.grade_and_diagnose(sub_req)
    assert res2.score == 1.0

    # Check history count: must be unchanged (idempotent, no double counting)
    history2 = storage.list_mastery_history(user_id=user_id)
    assert len(history2) == history_count_1

def test_persistent_mastery_across_restarts(storage):
    user_id = f"user_persist_{uuid.uuid4().hex[:6]}"
    topic = "Eigenvalues and Eigenvectors"

    # Instance 1 records mastery
    service1 = BayesianKnowledgeTracingService(storage=storage)
    score1 = service1.update_mastery(user_id, topic, is_correct=True, assessment_id="assess_test_1", observed_score=1.0)

    # Instance 2 (simulating fresh server restart / new request)
    storage2 = LocalStorageEngine()
    service2 = BayesianKnowledgeTracingService(storage=storage2)
    profile = service2.get_learner_profile(user_id)

    matched_topic = next((t for t in profile.topics if t.topic_name == topic), None)
    assert matched_topic is not None
    assert abs(matched_topic.mastery_score - score1) < 1e-4

    # History audit trail also persists
    history = storage2.list_mastery_history(user_id=user_id, topic_name=topic)
    assert len(history) >= 1
    assert history[0]["mastery_score"] == score1
    assert history[0]["observed_score"] == 1.0

# ==============================================================================
# Task B & Task G: New Learner Cold-Start Initialization
# ==============================================================================

def test_new_learner_initialization(bkt_service):
    fresh_user = f"new_student_{uuid.uuid4().hex[:8]}"
    profile = bkt_service.get_learner_profile(fresh_user)

    assert profile.is_new_learner is True
    assert profile.overall_mastery == 0.0
    # Must not assume or fabricate pre-existing mastery
    assert len(profile.strong_topics) == 0
    # Must recommend diagnostic assessment
    assert len(profile.recommended_activities) > 0
    first_rec = profile.recommended_activities[0]
    assert "diagnostic" in first_rec.type.lower()
    assert "diagnostic" in first_rec.title.lower()

# ==============================================================================
# Task C: Personalized Recommendations & Verified Source Citations
# ==============================================================================

def test_recommendation_selection_for_weak_topics(bkt_service, storage):
    user_id = f"user_weak_rec_{uuid.uuid4().hex[:6]}"
    weak_topic = "Backpropagation Algorithm"

    # Record 2 consecutive failures
    bkt_service.update_mastery(user_id, weak_topic, is_correct=False)
    bkt_service.update_mastery(user_id, weak_topic, is_correct=False)

    profile = bkt_service.get_learner_profile(user_id)
    assert weak_topic in profile.weak_topics

    # Check recommendations prioritize weak topic
    recs = profile.recommended_activities
    weak_recs = [r for r in recs if r.topic == weak_topic]
    assert len(weak_recs) > 0
    assert weak_recs[0].priority == "high"
    assert weak_recs[0].reason is not None

def test_source_citation_validity_in_recommendations(bkt_service, storage):
    courses = storage.list_courses()
    course_id = courses[0]["id"] if courses else "test_course"
    topic = "Linear Regression"

    user_id = f"user_citation_{uuid.uuid4().hex[:6]}"
    bkt_service.update_mastery(user_id, topic, is_correct=False)

    profile = bkt_service.get_learner_profile(user_id, course_id=course_id)
    for act in profile.recommended_activities:
        cit = getattr(act, "source_citation", None) or getattr(act, "citation", None)
        if cit is not None:
            assert cit.source_file is not None
            assert len(cit.source_file) > 0
            assert cit.source_type is not None
            assert len(cit.excerpt) > 0

# ==============================================================================
# Task D: Spaced Repetition Scheduling
# ==============================================================================

def test_spaced_repetition_scheduling(bkt_service):
    # 1. Successful practice expands interval
    sched_success = bkt_service.calculate_spaced_repetition_schedule(
        current_interval=1.0,
        mastery_score=0.90,
        is_correct=True,
        consecutive_streak=2
    )
    assert sched_success.review_interval_days >= 2.5
    assert sched_success.consecutive_correct == 3
    # Next review date must be in future
    next_review = datetime.fromisoformat(sched_success.next_review_at)
    now = datetime.now(timezone.utc)
    assert next_review > now

    # 2. Failed practice resets interval and streak
    sched_fail = bkt_service.calculate_spaced_repetition_schedule(
        current_interval=5.0,
        mastery_score=0.40,
        is_correct=False,
        consecutive_streak=3
    )
    assert sched_fail.review_interval_days == 1.0
    assert sched_fail.consecutive_correct == 0

def test_overdue_topics_detection(bkt_service, storage):
    user_id = f"user_overdue_{uuid.uuid4().hex[:6]}"
    topic = "Regularization Techniques"

    # Set review date in the past
    past_date = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    storage.save_topic_mastery(
        user_id=user_id,
        topic_name=topic,
        mastery_score=0.60,
        next_review_at=past_date,
        review_interval_days=1.0
    )

    profile = bkt_service.get_learner_profile(user_id)
    assert len(profile.upcoming_reviews) > 0
    matched = next((r for r in profile.upcoming_reviews if r.topic_name == topic), None)
    assert matched is not None
    assert matched.is_overdue is True
    assert matched.days_overdue >= 2.9

# ==============================================================================
# Task E: Adaptive Difficulty
# ==============================================================================

def test_adaptive_difficulty_progression(storage):
    generator = AssessmentService(storage=storage)
    user_id = f"user_diff_{uuid.uuid4().hex[:6]}"

    # New student without history receives beginner / diagnostic
    d_initial = generator._resolve_target_difficulty(user_id)
    assert d_initial in ["beginner", "diagnostic"]

    # Record 2 consecutive high-scoring assessments (> 0.85)
    storage.save_assessment({
        "id": str(uuid.uuid4()), "course_id": "c1", "user_id": user_id, "title": "Test 1", "assessment_type": "practice", "difficulty": "intermediate", "total_questions": 5, "status": "completed", "score": 0.90
    })
    storage.save_assessment({
        "id": str(uuid.uuid4()), "course_id": "c1", "user_id": user_id, "title": "Test 2", "assessment_type": "practice", "difficulty": "intermediate", "total_questions": 5, "status": "completed", "score": 0.95
    })

    d_advanced = generator._resolve_target_difficulty(user_id)
    assert d_advanced == "advanced"

    # Record 2 consecutive low-scoring assessments (< 0.50)
    user_struggle = f"user_struggle_{uuid.uuid4().hex[:6]}"
    storage.save_assessment({
        "id": str(uuid.uuid4()), "course_id": "c1", "user_id": user_struggle, "title": "Struggle 1", "assessment_type": "practice", "difficulty": "intermediate", "total_questions": 5, "status": "completed", "score": 0.30
    })
    storage.save_assessment({
        "id": str(uuid.uuid4()), "course_id": "c1", "user_id": user_struggle, "title": "Struggle 2", "assessment_type": "practice", "difficulty": "intermediate", "total_questions": 5, "status": "completed", "score": 0.20
    })
    d_struggle = generator._resolve_target_difficulty(user_struggle)
    assert d_struggle == "beginner"

# ==============================================================================
# Task F: Personalized Study Plan
# ==============================================================================

def test_study_plan_respects_time_and_exam_date(bkt_service):
    user_id = f"user_plan_{uuid.uuid4().hex[:6]}"
    daily_minutes = 25
    exam_date = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")

    req = StudyPlanRequest(
        user_id=user_id,
        daily_study_minutes=daily_minutes,
        target_exam_date=exam_date
    )
    plan = bkt_service.generate_study_plan(req)

    assert plan.user_id == user_id
    assert plan.daily_study_minutes == daily_minutes
    schedule_items = plan.schedule or plan.items
    assert len(schedule_items) > 0
    # Every activity duration must respect daily study minutes
    for item in schedule_items:
        assert item.suggested_duration_minutes <= daily_minutes
        assert item.reason is not None
        assert len(item.reason) > 0

def test_study_plan_handles_omitted_exam_date_as_provisional(bkt_service):
    user_id = f"user_provisional_{uuid.uuid4().hex[:6]}"
    req = StudyPlanRequest(
        user_id=user_id,
        daily_study_minutes=30,
        target_exam_date=None
    )
    plan = bkt_service.generate_study_plan(req)

    assert plan.is_provisional is True
    assert plan.provisional_notice is not None
    assert "provisional" in plan.provisional_notice.lower()
    schedule_items = plan.schedule or plan.items
    assert len(schedule_items) > 0

# ==============================================================================
# Topic Prerequisites
# ==============================================================================

def test_topic_prerequisites_awareness(bkt_service, storage):
    user_id = f"user_prereq_{uuid.uuid4().hex[:6]}"
    storage.add_topic_prerequisite(None, "Deep Neural Networks", "Linear Algebra")

    # Linear Algebra has poor mastery
    bkt_service.update_mastery(user_id, "Linear Algebra", is_correct=False)

    profile = bkt_service.get_learner_profile(user_id)
    recs = profile.recommended_activities

    # Should prioritize the prerequisite Linear Algebra
    algebra_recs = [r for r in recs if r.topic == "Linear Algebra"]
    assert len(algebra_recs) > 0
    assert "prerequisite" in algebra_recs[0].type.lower() or "prerequisite" in algebra_recs[0].reason.lower()
