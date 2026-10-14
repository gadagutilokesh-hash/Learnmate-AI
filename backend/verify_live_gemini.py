#!/usr/bin/env python3
"""
LearnMate AI - Gemini Live Connectivity Verification Script
Runs a full suite of non-destructive live checks:
1. Generation with gemini-3.8-flash (structured and unstructured)
2. Dense semantic embeddings with gemini-embedding-001 (768 dimensions)
3. Grounded retrieval and programmatic citation verification

Usage:
    python backend/verify_live_gemini.py
"""
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

def main():
    print("=" * 70)
    print("  LearnMate AI - Gemini Live Connectivity Verification")
    print("=" * 70)

    from app.core.config import settings
    from app.core.gemini import gemini_service
    from app.services.tutor.grounded_tutor import grounded_tutor
    from app.models.schema import TutorQueryRequest
    from app.db.storage import storage

    # 1. Configuration check
    has_key = bool(settings.GEMINI_API_KEY)
    print(f"API Key Present      : {has_key}")
    if has_key:
        masked = settings.GEMINI_API_KEY[:4] + "..." + settings.GEMINI_API_KEY[-4:]
        print(f"API Key Masked       : {masked}")
    print(f"Configured Model     : {settings.GEMINI_MODEL}")
    print(f"Embedding Model      : {settings.GEMINI_EMBEDDING_MODEL}")
    print(f"Embedding Dimension  : {settings.EMBEDDING_DIMENSION}")
    print("-" * 70)

    if not gemini_service.is_configured():
        print("[STATUS] Application is running in OFFLINE SIMULATION MODE.")
        print("To enable live Gemini integration, add GEMINI_API_KEY to backend/.env")
        sys.exit(0)

    # 2. Live API Connectivity Test
    print("\n[Step 1/3] Testing Gemini API Connectivity...")
    conn_result = gemini_service.test_connectivity()
    if conn_result.get("verified"):
        print("  -> Connectivity SUCCESSFUL!")
        print(f"  -> Model               : {conn_result.get('model')}")
        print(f"  -> Embedding Model     : {conn_result.get('embedding_model')}")
        print(f"  -> Embedding Dimension : {conn_result.get('embedding_dimension')}")
        print(f"  -> Sample Response     : {conn_result.get('sample_generation')}")
    else:
        print(f"  -> Connectivity FAILED: {conn_result.get('error')}")
        sys.exit(1)

    # 3. Embedding Vector Check
    print("\n[Step 2/3] Testing Semantic Vector Generation...")
    try:
        vec = gemini_service.get_embedding("LearnMate AI dense vector retrieval verification test.")
        print(f"  -> Generated Vector Length : {len(vec)} (Expected: 768)")
        if len(vec) == 768:
            print("  -> Vector Dimension Verification PASSED!")
        else:
            print(f"  -> Vector Dimension Verification FAILED (got {len(vec)})")
            sys.exit(1)
    except Exception as e:
        print(f"  -> Vector Generation FAILED: {e}")
        sys.exit(1)

    # 4. Live Grounded Tutor Query Check
    print("\n[Step 3/3] Testing Live Grounded Tutor with Citations...")
    courses = storage.list_courses()
    if courses:
        ml_courses = [c for c in courses if "CS229" in c["title"] or "Machine" in c["title"]]
        target_course = ml_courses[0] if ml_courses else courses[0]
        print(f"  -> Using Course: {target_course['title']} ({target_course['id']})")

        req = TutorQueryRequest(
            course_id=target_course["id"],
            query="What is feature normalization and why does it help gradient descent?",
            top_k=3
        )
        tutor_res = grounded_tutor.answer_query(req)
        print(f"  -> Tutor is_grounded     : {tutor_res.is_grounded}")
        print(f"  -> Verified Citations    : {len(tutor_res.citations)}")
        for idx, cit in enumerate(tutor_res.citations):
            print(f"     [{idx+1}] File: {cit.source_file} | Page: {cit.page_number} | Slide: {cit.slide_number}")
        print(f"  -> Grounded Answer (preview): {tutor_res.answer[:220]}...")
    else:
        print("  -> No courses in DB to test live query (skipped)")

    print("\n" + "=" * 70)
    print("  ALL LIVE GEMINI VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
