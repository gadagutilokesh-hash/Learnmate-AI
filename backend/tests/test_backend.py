import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
from fastapi.testclient import TestClient
from app.main import app, startup_seed_demo_data
from app.services.learner.mastery_model import mastery_service
from app.services.retrieval.hybrid_retriever import hybrid_retriever
from app.services.tutor.grounded_tutor import grounded_tutor
from app.models.schema import TutorQueryRequest
from app.db.storage import storage

startup_seed_demo_data()
client = TestClient(app)

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
    c = courses[0]
    assert "CS229" in c["title"]
    assert c["documents_count"] >= 3

def test_hybrid_retrieval_and_citation_formatting():
    courses = storage.list_courses()
    c_id = courses[0]["id"]
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
    courses = storage.list_courses()
    c_id = courses[0]["id"]
    req = TutorQueryRequest(
        course_id=c_id,
        query="Why do we use feature normalization before gradient descent?",
        top_k=3
    )
    res = grounded_tutor.answer_query(req)
    assert res.is_grounded is True
    assert len(res.citations) > 0
    # Citations must preserve source location
    cit = res.citations[0]
    assert cit.page_number is not None or cit.slide_number is not None or cit.start_timestamp is not None

def test_grounded_tutor_rejects_unsupported_query():
    courses = storage.list_courses()
    c_id = courses[0]["id"]
    req = TutorQueryRequest(
        course_id=c_id,
        query="What is the authentic recipe for baking French croissants with laminating butter?",
        top_k=3
    )
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
    courses = storage.list_courses()
    c_id = courses[0]["id"]
    gen_res = client.post("/api/assessments/generate", json={
        "course_id": c_id,
        "difficulty": "intermediate",
        "question_count": 3
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
    courses = storage.list_courses()
    c_id = courses[0]["id"]
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
