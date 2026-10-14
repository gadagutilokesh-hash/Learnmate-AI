import httpx
import json
import os
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_URL = "http://localhost:8000/api"
FRONTEND_URL = "http://localhost:3000"

results = {}

def run_tests():
    with httpx.Client(timeout=30.0) as client:
        # 1. Health & Config
        print("--- Testing Health & Config ---")
        res = client.get(f"{BACKEND_URL}/health")
        assert res.status_code == 200, f"Health check failed: {res.status_code}"
        health_data = res.json()
        print(f"Health status: {health_data['status']} | Active Provider: {health_data.get('active_provider')}")
        results["health"] = True

        # 2. Courses List & Finding CS229
        print("\n--- Testing Courses & Persistence ---")
        res = client.get(f"{BACKEND_URL}/courses")
        assert res.status_code == 200
        courses = res.json()
        assert len(courses) > 0, "No courses found"
        
        # Prefer CS229 for machine learning questions
        cs229_course = next((c for c in courses if "cs229" in c["title"].lower()), courses[0])
        course_id = cs229_course["id"]
        course_title = cs229_course["title"]
        print(f"Selected course for grounded tests: {course_title} ({course_id})")
        results["courses_list"] = True

        res = client.get(f"{BACKEND_URL}/courses/{course_id}/documents")
        assert res.status_code == 200
        docs = res.json()
        print(f"Found {len(docs)} documents in {course_title}.")
        results["docs_list"] = True

        # 3. Grounded Tutor Query
        print("\n--- Testing Grounded Tutor Query ---")
        tutor_req = {
            "course_id": course_id,
            "query": "Explain the gradient descent parameter update rule from my uploaded course materials.",
            "top_k": 3
        }
        res = client.post(f"{BACKEND_URL}/tutor/query", json=tutor_req)
        assert res.status_code == 200, f"Tutor query failed: {res.status_code}"
        tutor_data = res.json()
        print("Grounded:", tutor_data["is_grounded"])
        print("Citations count:", len(tutor_data["citations"]))
        assert tutor_data["is_grounded"] is True, "Expected grounded answer"
        assert len(tutor_data["citations"]) > 0, "Expected at least 1 citation"
        c0 = tutor_data["citations"][0]
        print(f"Verified Citation: {c0['source_file']}, slide {c0.get('slide_number') or c0.get('page_number')}")
        results["grounded_tutor"] = True

        # 4. Unsupported Question Rejection
        print("\n--- Testing Unsupported Question Rejection ---")
        unsupported_req = {
            "course_id": course_id,
            "query": "Explain quantum chromodynamics and gluon plasma in depth.",
            "top_k": 3
        }
        res = client.post(f"{BACKEND_URL}/tutor/query", json=unsupported_req)
        assert res.status_code == 200
        rej_data = res.json()
        print("Rejected is_grounded:", rej_data["is_grounded"])
        print("Rejection response received cleanly.")
        assert rej_data["is_grounded"] is False, "Expected ungrounded rejection"
        assert len(rej_data["citations"]) == 0, "Expected zero citations on rejection"
        results["unsupported_rejection"] = True

        # 5. Assessment Generation & Submission
        print("\n--- Testing Assessment Generation & Idempotent Submission ---")
        assess_req = {
            "course_id": course_id,
            "user_id": "test_deployment_student",
            "assessment_type": "adaptive_quiz",
            "difficulty": "intermediate",
            "question_count": 2,
            "question_type": "mcq"
        }
        res = client.post(f"{BACKEND_URL}/assessments/generate", json=assess_req)
        assert res.status_code == 200, f"Assessment generation failed: {res.status_code}"
        assessment = res.json()
        print(f"Generated assessment: {assessment['title']} ({assessment['id']})")
        print(f"Questions synthesized: {len(assessment['questions'])}")
        assert len(assessment["questions"]) > 0
        results["assessment_generation"] = True

        # Submit answers
        answers = []
        for q in assessment["questions"]:
            selected = q["options"][0] if q.get("options") else "test answer"
            answers.append({"question_id": q["id"], "student_answer": selected})

        submit_req = {
            "assessment_id": assessment["id"],
            "user_id": "test_deployment_student",
            "answers": answers
        }
        res = client.post(f"{BACKEND_URL}/assessments/submit", json=submit_req)
        assert res.status_code == 200, f"Assessment submit failed: {res.status_code}"
        sub_result = res.json()
        print(f"Graded score: {sub_result['score']*100:.0f}%")
        print(f"BKT Mastery updates: {list(sub_result['mastery_updates'].keys())}")
        results["assessment_submission"] = True

        # Idempotent re-submission check
        res2 = client.post(f"{BACKEND_URL}/assessments/submit", json=submit_req)
        assert res2.status_code == 200
        assert res2.json()["score"] == sub_result["score"], "Idempotent submission failed"
        print("Idempotent re-submission verified identical score.")
        results["assessment_idempotency"] = True

        # 6. Learner Progress & Study Plan
        print("\n--- Testing Learner Profile & Study Plan ---")
        res = client.get(f"{BACKEND_URL}/learner/profile?user_id=test_deployment_student")
        assert res.status_code == 200
        profile = res.json()
        print(f"Learner overall mastery: {profile['overall_mastery']*100:.1f}%")
        print(f"Topics tracked: {len(profile['topics'])}")
        results["learner_profile"] = True

        plan_req = {
            "user_id": "test_deployment_student",
            "course_id": course_id,
            "daily_study_minutes": 30
        }
        res = client.post(f"{BACKEND_URL}/learner/study-plan", json=plan_req)
        assert res.status_code == 200
        plan = res.json()
        print(f"Generated study plan activities: {len(plan['schedule'])}")
        results["study_plan"] = True

        # 7. Frontend Static & Legal Pages Connectivity
        print("\n--- Testing Frontend Routes & Legal Navigation ---")
        frontend_routes = ["/", "/courses", "/tutor", "/assessments", "/progress", "/evaluation", "/privacy", "/terms"]
        for route in frontend_routes:
            f_res = client.get(f"{FRONTEND_URL}{route}")
            assert f_res.status_code == 200, f"Route {route} returned {f_res.status_code}"
            print(f"Route {route}: 200 OK")
        results["frontend_routes"] = True

    print("\n================ ALL LIVE TESTS PASSED ================")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_tests()
