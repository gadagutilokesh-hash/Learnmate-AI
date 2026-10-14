import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db.storage import storage
from app.core.auth import hash_password, create_access_token

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_test_users_and_courses():
    """
    Creates two isolated test users (User A, User B) and one Admin user.
    Creates private courses and documents for each.
    """
    # 1. Register User A
    user_a_email = f"user_a_{uuid.uuid4().hex[:6]}@learnmate.test"
    res_a = client.post("/api/auth/register", json={
        "email": user_a_email,
        "password": "PasswordUserA123!",
        "full_name": "Alice Learner"
    })
    assert res_a.status_code == 201
    user_a = res_a.json()["user"]
    token_a = res_a.json()["access_token"]

    # 2. Register User B
    user_b_email = f"user_b_{uuid.uuid4().hex[:6]}@learnmate.test"
    res_b = client.post("/api/auth/register", json={
        "email": user_b_email,
        "password": "PasswordUserB123!",
        "full_name": "Bob Researcher"
    })
    assert res_b.status_code == 201
    user_b = res_b.json()["user"]
    token_b = res_b.json()["access_token"]

    # 3. Create Admin user
    admin_email = f"admin_{uuid.uuid4().hex[:6]}@learnmate.test"
    admin_user = storage.create_user(
        email=admin_email,
        password_hash=hash_password("AdminSecurePassword123!"),
        full_name="Admin User",
        role="admin"
    )
    token_admin = create_access_token(user_id=admin_user["id"], email=admin_email, role="admin")

    # 4. Create Private Course for User A
    res_course_a = client.post(
        "/api/courses",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Alice Private AI Course", "description": "Confidential AI materials for Alice"}
    )
    assert res_course_a.status_code == 200
    course_a = res_course_a.json()

    # 5. Create Private Course for User B
    res_course_b = client.post(
        "/api/courses",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Bob Private Robotics Course", "description": "Proprietary robotics notes for Bob"}
    )
    assert res_course_b.status_code == 200
    course_b = res_course_b.json()

    # 6. Seed chunk for Alice's course
    chunk_a = {
        "id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "course_id": course_a["id"],
        "chunk_index": 0,
        "content": "Secret Algorithm Alpha: Alice's proprietary quantum gradient optimization procedure.",
        "chunk_type": "text",
        "source_type": "pdf",
        "page_number": 1,
        "topic": "Quantum Optimization",
        "concept": "Algorithm Alpha",
        "metadata": {"confidential": True}
    }
    # 7. Seed chunk for Bob's course
    chunk_b = {
        "id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "course_id": course_b["id"],
        "chunk_index": 0,
        "content": "Secret Kinematics Beta: Bob's confidential robotic inverse dynamics formula.",
        "chunk_type": "text",
        "source_type": "pdf",
        "page_number": 1,
        "topic": "Robotics Kinematics",
        "concept": "Kinematics Beta",
        "metadata": {"confidential": True}
    }
    storage.save_chunks([chunk_a, chunk_b])

    return {
        "user_a": user_a,
        "token_a": token_a,
        "course_a": course_a,
        "chunk_a": chunk_a,
        "user_b": user_b,
        "token_b": token_b,
        "course_b": course_b,
        "chunk_b": chunk_b,
        "admin_user": admin_user,
        "token_admin": token_admin
    }


# ==============================================================================
# Security Assertion 1: Unauthenticated visitor access strictly limited to demo
# ==============================================================================
def test_visitor_can_access_only_shared_demo():
    res = client.get("/api/courses")
    assert res.status_code == 200
    courses = res.json()
    assert len(courses) > 0
    # Every course listed for a visitor must be a shared demo
    for c in courses:
        assert c["visibility"] == "shared_demo" or c["is_demo"] is True


# ==============================================================================
# Security Assertion 2: Shared BEFA demo is read-only for ordinary users
# ==============================================================================
def test_shared_demo_is_read_only_for_ordinary_users(setup_test_users_and_courses):
    data = setup_test_users_and_courses
    token_a = data["token_a"]

    # Locate BEFA course
    res = client.get("/api/courses")
    demo_courses = [c for c in res.json() if c["is_demo"] or c["visibility"] == "shared_demo"]
    assert len(demo_courses) > 0
    befa_id = demo_courses[0]["id"]

    # 1. Unauthenticated upload rejected with 401
    anon_client = TestClient(app)
    fake_file = ("notes.pdf", b"%PDF-1.4 test dummy content", "application/pdf")
    res_upload_anon = anon_client.post(
        f"/api/courses/{befa_id}/upload",
        files={"file": fake_file}
    )
    assert res_upload_anon.status_code == 401

    # 2. Authenticated non-admin upload to demo course rejected with 403 Forbidden
    res_upload_user = client.post(
        f"/api/courses/{befa_id}/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": fake_file}
    )
    assert res_upload_user.status_code == 403
    assert "read-only" in res_upload_user.json()["detail"].lower()

    # 3. Authenticated non-admin delete of demo course rejected with 403 Forbidden
    res_delete_demo = client.delete(
        f"/api/courses/{befa_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_delete_demo.status_code == 403


# ==============================================================================
# Security Assertion 3: Authenticated users can create & manage private courses
# ==============================================================================
def test_authenticated_user_can_create_and_manage_private_course(setup_test_users_and_courses):
    data = setup_test_users_and_courses
    token_a = data["token_a"]
    user_a = data["user_a"]

    res = client.post(
        "/api/courses",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Alice Discrete Math", "description": "Graph theory"}
    )
    assert res.status_code == 200
    course = res.json()
    assert course["owner_id"] == user_a["id"]
    assert course["visibility"] == "private"
    assert course["is_demo"] is False

    # Alice can fetch her own course
    res_get = client.get(
        f"/api/courses/{course['id']}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_get.status_code == 200
    assert res_get.json()["title"] == "Alice Discrete Math"


# ==============================================================================
# Security Assertion 4 & 9: User A cannot retrieve User B's private course (IDOR)
# ==============================================================================
def test_user_a_cannot_retrieve_user_b_private_course(setup_test_users_and_courses):
    data = setup_test_users_and_courses
    token_a = data["token_a"]
    course_b_id = data["course_b"]["id"]

    # User A tries to get Course B by changing course ID -> MUST BE 404
    res = client.get(
        f"/api/courses/{course_b_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Course not found"

    # Anonymous visitor tries to get Course B -> MUST BE 404
    anon_client = TestClient(app)
    res_anon = anon_client.get(f"/api/courses/{course_b_id}")
    assert res_anon.status_code == 404

    # User A listing courses does NOT contain Course B
    res_list = client.get(
        "/api/courses",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_list.status_code == 200
    user_a_course_ids = [c["id"] for c in res_list.json()]
    assert course_b_id not in user_a_course_ids


# ==============================================================================
# Security Assertion 5: User A cannot download or list User B's documents
# ==============================================================================
def test_user_a_cannot_access_user_b_documents(setup_test_users_and_courses):
    data = setup_test_users_and_courses
    token_a = data["token_a"]
    course_b_id = data["course_b"]["id"]

    # User A requests document list for Course B -> 404
    res = client.get(
        f"/api/courses/{course_b_id}/documents",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res.status_code == 404


# ==============================================================================
# Security Assertion 6: User A cannot read User B's learner history or study plan
# ==============================================================================
def test_user_a_cannot_access_user_b_learner_records(setup_test_users_and_courses):
    data = setup_test_users_and_courses
    token_a = data["token_a"]
    user_b_id = data["user_b"]["id"]
    course_b_id = data["course_b"]["id"]

    # 1. User A tries to pass user_b_id in profile request
    # Backend strictly binds profile to authenticated user_a session
    res_prof = client.get(
        f"/api/learner/profile?user_id={user_b_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_prof.status_code == 200
    # Must return user_a's profile, NOT user_b's
    assert res_prof.json()["user_id"] == data["user_a"]["id"]

    # 2. User A tries to request profile targeting Course B -> 404
    res_prof_course = client.get(
        f"/api/learner/profile?course_id={course_b_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_prof_course.status_code == 404

    # 3. User A tries to request study plan targeting Course B -> 404
    res_plan = client.get(
        f"/api/learner/study-plan?course_id={course_b_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_plan.status_code == 404


# ==============================================================================
# Security Assertion 7: User A cannot access User B's assessment attempts
# ==============================================================================
def test_user_a_cannot_access_user_b_assessment_attempts(setup_test_users_and_courses):
    data = setup_test_users_and_courses
    token_a = data["token_a"]
    token_b = data["token_b"]
    course_b_id = data["course_b"]["id"]

    # User B creates an assessment in their private course
    assessment_id = str(uuid.uuid4())
    storage._get_connection().execute(
        """INSERT INTO assessments (id, course_id, user_id, title, assessment_type, difficulty, total_questions, status, questions_json, misconceptions_json, created_at)
           VALUES (?, ?, ?, 'Bob Quiz', 'adaptive_quiz', 'medium', 1, 'ready', '[]', '[]', '2026-10-14T08:00:00Z')""",
        (assessment_id, course_b_id, data["user_b"]["id"])
    )

    # User A tries to get Bob's assessment -> 404
    res_get = client.get(
        f"/api/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_get.status_code == 404

    # User A tries to submit answers to Bob's assessment -> 404
    res_sub = client.post(
        "/api/assessments/submit",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"assessment_id": assessment_id, "answers": []}
    )
    assert res_sub.status_code == 404


# ==============================================================================
# Security Assertion 8 & 10: Strict Retrieval Isolation in AI Tutor
# User A cannot retrieve User B's documents through AI tutor
# ==============================================================================
def test_retrieval_isolation_cross_user_tutor(setup_test_users_and_courses):
    data = setup_test_users_and_courses
    token_a = data["token_a"]
    course_b_id = data["course_b"]["id"]
    course_a_id = data["course_a"]["id"]

    # 1. User A queries the tutor targeting User B's private course ID -> MUST BE 404
    res_idor = client.post(
        "/api/tutor/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"course_id": course_b_id, "query": "What is the robotic inverse dynamics formula?"}
    )
    assert res_idor.status_code == 404
    assert res_idor.json()["detail"] == "Course not found"

    # 2. User A queries the tutor on their OWN course about Bob's confidential content:
    # Retrieval is strictly confined to Course A chunks, so it will NOT retrieve Bob's chunks!
    from app.services.retrieval.hybrid_retriever import hybrid_retriever
    chunks = hybrid_retriever.retrieve(
        query="robotic inverse dynamics formula",
        course_id=course_a_id
    )
    for c in chunks:
        assert c["course_id"] == course_a_id
        assert "Bob" not in c["content"]
        assert "Kinematics Beta" not in c["content"]


# ==============================================================================
# Security Assertion 11: Demo course notes remain accessible after migration
# ==============================================================================
def test_befa_demo_notes_intact_and_accessible():
    res = client.get("/api/courses")
    assert res.status_code == 200
    courses = res.json()
    befa = next((c for c in courses if "befa" in c["title"].lower() or c["is_demo"]), None)
    assert befa is not None, "Designated BEFA demo course must be listed"
    assert befa["is_demo"] is True
    assert befa["visibility"] == "shared_demo"

    # Verify BEFA documents are accessible to anonymous visitors
    res_docs = client.get(f"/api/courses/{befa['id']}/documents")
    assert res_docs.status_code == 200
    docs = res_docs.json()
    assert len(docs) > 0
    assert any("BEFA" in d["filename"] for d in docs)
