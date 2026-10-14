import fitz  # PyMuPDF
import httpx
import json
import time
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_URL = "http://localhost:8000/api"
FRONTEND_URL = "http://localhost:3000"

def create_sample_pdf(filepath: str):
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "Deployment Verification Guide\n\n"
        "LearnMate AI Production Readiness Protocol:\n"
        "1. Persistent SQLite database stores courses, documents, chunks, and learner mastery.\n"
        "2. Persistent volume must be mounted at backend/data for production deployments.\n"
        "3. Zero secret keys must ever be exposed in frontend bundles or API responses.\n"
        "4. Provider failover ensures seamless educational tutoring and assessment generation.\n"
    )
    page.insert_text((50, 72), text, fontsize=12)
    doc.save(filepath)
    doc.close()

def run_tests():
    test_pdf_path = "test_deployment_doc.pdf"
    create_sample_pdf(test_pdf_path)
    
    with httpx.Client(timeout=45.0) as client:
        print("=== 1. Testing Live Course Upload & Ingestion ===")
        # Get course ID
        courses_res = client.get(f"{BACKEND_URL}/courses")
        assert courses_res.status_code == 200
        courses = courses_res.json()
        cs229 = next((c for c in courses if "cs229" in c["title"].lower()), courses[0])
        course_id = cs229["id"]
        print(f"Uploading to course: {cs229['title']} ({course_id})")

        with open(test_pdf_path, "rb") as f:
            files = {"file": ("test_deployment_doc.pdf", f, "application/pdf")}
            data = {"topic": "Deployment Architecture"}
            upload_res = client.post(f"{BACKEND_URL}/courses/{course_id}/upload", files=files, data=data)
        
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.status_code} {upload_res.text}"
        doc_info = upload_res.json()
        doc_id = doc_info["id"]
        print(f"Document uploaded successfully! Doc ID: {doc_id}, initial status: {doc_info['ingestion_status']}")

        # Poll for completion
        status = doc_info["ingestion_status"]
        for attempt in range(15):
            time.sleep(1)
            poll_res = client.get(f"{BACKEND_URL}/documents/{doc_id}")
            if poll_res.status_code == 200:
                doc_record = poll_res.json()
                status = doc_record["ingestion_status"]
                print(f"Polling doc status ({attempt+1}s): {status} (chunks: {doc_record['chunks_count']})")
                if status in ("completed", "failed"):
                    break
        
        assert status == "completed", f"Document processing failed or timed out. Final status: {status}"
        print(f"Document {doc_id} processed successfully to 'completed' with {doc_record['chunks_count']} chunks.")

        # Query grounded tutor on this newly uploaded document!
        print("\n=== 2. Testing Tutor Query on Newly Ingested Document ===")
        tutor_req = {
            "course_id": course_id,
            "query": "What does the production readiness protocol say about persistent storage in LearnMate AI?",
            "top_k": 3
        }
        tutor_res = client.post(f"{BACKEND_URL}/tutor/query", json=tutor_req)
        assert tutor_res.status_code == 200
        tutor_data = tutor_res.json()
        print(f"Tutor grounded: {tutor_data['is_grounded']}")
        print(f"Citations count: {len(tutor_data['citations'])}")
        assert tutor_data["is_grounded"] is True, "Expected grounded response from new document"
        assert len(tutor_data["citations"]) > 0
        matched_source = any("test_deployment_doc.pdf" in c["source_file"] for c in tutor_data["citations"])
        print(f"Source matched newly uploaded PDF: {matched_source}")
        assert matched_source, "Citation did not reference newly uploaded test PDF"

        print("\n=== 3. Testing Provider Error Handling & Sanitization ===")
        # Test 1: Invalid request payload (validation error)
        bad_req = {"course_id": "nonexistent-id", "top_k": "invalid_integer_string"}
        bad_res = client.post(f"{BACKEND_URL}/tutor/query", json=bad_req)
        assert bad_res.status_code == 422, f"Expected 422 for invalid payload, got {bad_res.status_code}"
        print(f"Invalid payload handled gracefully with HTTP 422.")

        # Test 2: Verify error response bodies never leak secrets or tracebacks
        assert "api_key" not in bad_res.text.lower()
        assert "gsk_" not in bad_res.text
        assert "nvapi-" not in bad_res.text
        assert "aiza" not in bad_res.text.lower()
        print("Error response verified: zero secret keys or raw credentials in payload.")

        print("\n=== 4. Testing Privacy and Terms Navigation ===")
        privacy_res = client.get(f"{FRONTEND_URL}/privacy")
        assert privacy_res.status_code == 200
        assert "Privacy Policy" in privacy_res.text
        assert "LearnMate AI" in privacy_res.text
        print("Frontend /privacy: 200 OK with expected legal title and content.")

        terms_res = client.get(f"{FRONTEND_URL}/terms")
        assert terms_res.status_code == 200
        assert "Terms of Service" in terms_res.text
        assert "LearnMate AI" in terms_res.text
        print("Frontend /terms: 200 OK with expected legal title and content.")

    # Cleanup temp local test pdf
    if os.path.exists(test_pdf_path):
        os.remove(test_pdf_path)

    print("\n================ ALL ADVANCED LIVE TESTS PASSED ================")

if __name__ == "__main__":
    run_tests()
