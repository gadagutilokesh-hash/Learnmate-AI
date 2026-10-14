import json
import pytest
from unittest.mock import MagicMock, patch
from app.core.gemini import GeminiService, sanitize_error
from app.models.schema import TutorQueryRequest, TutorQueryResponse, Citation
from app.services.tutor.grounded_tutor import GroundedTutorService, GroundedTutorLLMResponse
from app.services.retrieval.hybrid_retriever import HybridRetriever
from app.services.retrieval.reindexer import ReindexerService
from app.db.storage import LocalStorageEngine

# ==============================================================================
# Task A & E: Missing & Invalid API Key Tests
# ==============================================================================

def test_missing_api_key_offline_mode():
    """
    When GEMINI_API_KEY is not configured:
    - Service reports is_configured() == False
    - Explicit offline mode is used without claiming live connection
    - Generates deterministic simulated responses
    """
    with patch.dict("os.environ", {}, clear=True):
        with patch("app.core.gemini.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = None
            mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
            mock_settings.GEMINI_MULTIMODAL_MODEL = "gemini-3.8-flash"
            mock_settings.GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
            mock_settings.EMBEDDING_DIMENSION = 768

            svc = GeminiService()
            assert not svc.is_configured()

            # Offline connectivity test
            conn = svc.test_connectivity()
            assert conn["configured"] is False
            assert conn["mode"] == "offline"

            # Offline text generation
            gen_text = svc.generate_text("Explain machine learning")
            assert isinstance(gen_text, str)
            assert len(gen_text) > 0

            # Offline pseudo embedding (768 dimensions)
            emb = svc.get_embedding("test text")
            assert len(emb) == 768

def test_invalid_api_key_raises_error():
    """
    Rule 7: When live mode is configured, API errors must NOT silently fall back
    to mock output. They must raise a sanitized exception.
    """
    with patch("app.core.gemini.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "invalid_secret_key_12345"
        mock_settings.GEMINI_MODEL = "gemini-3.8-flash"
        mock_settings.GEMINI_MULTIMODAL_MODEL = "gemini-3.8-flash"
        mock_settings.GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
        mock_settings.EMBEDDING_DIMENSION = 768

        svc = GeminiService()
        svc._client = MagicMock()
        # Mock client to raise an API error containing the key in the error string
        svc._client.models.generate_content.side_effect = Exception("403 Forbidden: API key invalid_secret_key_12345 invalid")
        svc._client.models.embed_content.side_effect = Exception("403 Forbidden: API key invalid_secret_key_12345 invalid")

        assert svc.is_configured()

        # Must raise RuntimeError, not return mock response!
        with pytest.raises(RuntimeError) as exc_info:
            svc.generate_text("test prompt")
        assert "Gemini live generation failed" in str(exc_info.value)
        # Verify secret was sanitized
        assert "invalid_secret_key_12345" not in str(exc_info.value)
        assert "[REDACTED_API_KEY]" in str(exc_info.value)

        # Embedding must also raise RuntimeError, not return pseudo embedding
        with pytest.raises(RuntimeError) as exc_emb:
            svc.get_embedding("test prompt")
        assert "Gemini live embedding failed" in str(exc_emb.value)
        assert "invalid_secret_key_12345" not in str(exc_emb.value)

def test_sanitize_error_helper():
    """Verify secrets are redacted from error messages."""
    with patch("app.core.gemini.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "my_super_secret_key"
        err = Exception("Request failed for key=my_super_secret_key with Bearer my_super_secret_key")
        sanitized = sanitize_error(err)
        assert "my_super_secret_key" not in sanitized
        assert "[REDACTED" in sanitized

# ==============================================================================
# Task B & E: Structured Tutor Output & Programmatic Citation Validation
# ==============================================================================

def test_mocked_successful_grounded_tutor_response():
    """
    Verify grounded tutor correctly processes structured LLM response,
    resolves 1-based source indices, and populates citations.
    """
    mock_retrieved = [
        {
            "id": "c1",
            "filename": "Lecture_01.pdf",
            "source_type": "pdf",
            "page_number": 5,
            "slide_number": None,
            "start_timestamp": None,
            "end_timestamp": None,
            "content": "Feature normalization standardizes inputs to unit variance.",
            "hybrid_score": 0.88,
            "topic": "Preprocessing",
            "concept": "Normalization"
        },
        {
            "id": "c2",
            "filename": "Lecture_02.pptx",
            "source_type": "pptx",
            "page_number": None,
            "slide_number": 8,
            "start_timestamp": None,
            "end_timestamp": None,
            "content": "Gradient descent converges faster on spherical contours.",
            "hybrid_score": 0.82,
            "topic": "Optimization",
            "concept": "Gradient Descent"
        }
    ]

    llm_payload = GroundedTutorLLMResponse(
        answer="Feature normalization standardizes inputs, which helps gradient descent converge faster.",
        is_sufficiently_grounded=True,
        cited_source_indices=[1, 2],
        insufficient_evidence_reason=None
    )

    tutor = GroundedTutorService()

    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=mock_retrieved):
        with patch("app.services.tutor.grounded_tutor.gemini_service.generate_text", return_value=llm_payload.model_dump_json()):
            with patch("app.services.tutor.grounded_tutor.gemini_service.is_configured", return_value=True):
                req = TutorQueryRequest(course_id="test_course", query="Why normalize features?", top_k=2)
                res = tutor.answer_query(req)

                assert res.is_grounded is True
                assert len(res.citations) == 2
                assert res.citations[0].source_file == "Lecture_01.pdf"
                assert res.citations[0].page_number == 5
                assert res.citations[1].source_file == "Lecture_02.pptx"
                assert res.citations[1].slide_number == 8

def test_rejection_of_fabricated_citation_identifiers():
    """
    CRITICAL: The model MUST NOT be allowed to invent or fabricate citation indices.
    If LLM returns [1, 99, -2, 0], only index 1 should be retained and 99, -2, 0 dropped.
    """
    mock_retrieved = [
        {
            "id": "c1",
            "filename": "Lecture_01.pdf",
            "source_type": "pdf",
            "page_number": 3,
            "slide_number": None,
            "start_timestamp": None,
            "end_timestamp": None,
            "content": "Supervised learning maps inputs to target outputs.",
            "hybrid_score": 0.90,
            "topic": "Fundamentals",
            "concept": "Supervised"
        }
    ]

    # Model fabricates indices 99 and -2
    llm_payload = GroundedTutorLLMResponse(
        answer="Supervised learning maps inputs to outputs.",
        is_sufficiently_grounded=True,
        cited_source_indices=[1, 99, -2, 0],
        insufficient_evidence_reason=None
    )

    tutor = GroundedTutorService()

    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=mock_retrieved):
        with patch("app.services.tutor.grounded_tutor.gemini_service.generate_text", return_value=llm_payload.model_dump_json()):
            with patch("app.services.tutor.grounded_tutor.gemini_service.is_configured", return_value=True):
                req = TutorQueryRequest(course_id="test_course", query="What is supervised learning?", top_k=1)
                res = tutor.answer_query(req)

                assert res.is_grounded is True
                # Only the 1 valid retrieved chunk was accepted; fabricated indices were rejected!
                assert len(res.citations) == 1
                assert res.citations[0].source_file == "Lecture_01.pdf"
                assert res.citations[0].page_number == 3

def test_unsupported_question_handling():
    """
    When retrieved excerpts do not substantiate the student query,
    the tutor must declare is_grounded=False with an explicit reason.
    """
    mock_retrieved = [
        {
            "id": "c1",
            "filename": "Economics_Notes.pdf",
            "source_type": "pdf",
            "page_number": 1,
            "slide_number": None,
            "start_timestamp": None,
            "end_timestamp": None,
            "content": "Opportunity cost is the loss of potential gain when one alternative is chosen.",
            "hybrid_score": 0.40,
            "topic": "Economics",
            "concept": "Cost"
        }
    ]

    # Model declares insufficient evidence
    llm_payload = GroundedTutorLLMResponse(
        answer="I cannot find information about quantum teleportation in your uploaded course materials.",
        is_sufficiently_grounded=False,
        cited_source_indices=[],
        insufficient_evidence_reason="Course materials cover basic economics, not quantum physics."
    )

    tutor = GroundedTutorService()

    with patch("app.services.tutor.grounded_tutor.hybrid_retriever.retrieve", return_value=mock_retrieved):
        with patch("app.services.tutor.grounded_tutor.gemini_service.generate_text", return_value=llm_payload.model_dump_json()):
            with patch("app.services.tutor.grounded_tutor.gemini_service.is_configured", return_value=True):
                req = TutorQueryRequest(course_id="test_course", query="How does quantum teleportation work?", top_k=1)
                res = tutor.answer_query(req)

                assert res.is_grounded is False
                assert len(res.citations) == 0
                assert res.unsupported_reason is not None
                assert "economics" in res.unsupported_reason.lower()

# ==============================================================================
# Task C & E: Embedding Dimensions & Isolation
# ==============================================================================

def test_genuine_embedding_dimension_validation():
    """Verify that genuine Gemini embeddings are strictly validated for 768 dimensions."""
    svc = GeminiService()
    svc._client = MagicMock()

    # Mock embed_content returning 768 dimensions
    mock_emb_obj = MagicMock()
    mock_emb_obj.values = [0.01] * 768
    svc._client.models.embed_content.return_value = MagicMock(embeddings=[mock_emb_obj])

    with patch("app.core.gemini.settings.GEMINI_API_KEY", "mock_key"):
        svc.api_key = "mock_key"
        emb = svc.get_embedding("test text")
        assert len(emb) == 768

    # If API returns wrong dimension (e.g. 512), must raise ValueError / RuntimeError
    mock_bad_dim = MagicMock()
    mock_bad_dim.values = [0.01] * 512
    svc._client.models.embed_content.return_value = MagicMock(embeddings=[mock_bad_dim])

    with patch("app.core.gemini.settings.GEMINI_API_KEY", "mock_key"):
        with pytest.raises(RuntimeError) as exc:
            svc.get_embedding("test text")
        assert "dimension" in str(exc.value).lower()

def test_no_mixing_pseudo_and_genuine_embeddings():
    """
    CRITICAL: In similarity search, genuine query vectors must NEVER be compared against
    pseudo-embeddings. Such chunks must receive a 0.0 vector score.
    """
    retriever = HybridRetriever()

    # 1 genuine chunk and 1 pseudo chunk
    test_chunks = [
        {
            "id": "c1",
            "content": "Supervised learning with regression and classification.",
            "embedding": [0.1] * 768,
            "metadata": {"is_pseudo": False, "embedding_model": "gemini-embedding-001"}
        },
        {
            "id": "c2",
            "content": "Deep convolutional neural networks and feature hierarchies.",
            "embedding": [0.1] * 768,
            "metadata": {"is_pseudo": True, "embedding_model": "pseudo"}
        }
    ]

    # Live query scenario
    with patch("app.services.retrieval.hybrid_retriever.gemini_service.is_configured", return_value=True):
        with patch("app.services.retrieval.hybrid_retriever.gemini_service.get_embedding", return_value=[0.1] * 768):
            with patch("app.services.retrieval.hybrid_retriever.gemini_service.embedding_model_name", "gemini-embedding-001"):
                with patch("app.services.retrieval.hybrid_retriever.gemini_service.embedding_dimension", 768):
                    scores = retriever._score_vector("Supervised learning", test_chunks)
                    # Genuine chunk c1 gets positive similarity score
                    assert scores[0] > 0.0
                    # Pseudo chunk c2 receives exactly 0.0 because it cannot be mixed with genuine vector!
                    assert scores[1] == 0.0

# ==============================================================================
# Task D & E: Re-indexing Idempotency & Data Preservation
# ==============================================================================

def test_reindexer_idempotency_and_metadata_preservation(tmp_path):
    """
    Verify that re-indexing:
    1. Replaces pseudo embeddings with genuine embeddings.
    2. Preserves all existing course, document, and chunk metadata (e.g. chapter, page).
    3. Running a second time is idempotent (0 pending chunks).
    """
    db_file = str(tmp_path / "test_reindex.db")
    test_storage = LocalStorageEngine(db_path=db_file)

    # Create course, document, and 2 chunks with custom metadata
    c = test_storage.create_course(title="Intro ML")
    d = test_storage.create_document(course_id=c["id"], filename="lecture.pdf", file_type="pdf", file_path="fake.pdf")

    test_storage.save_chunks([
        {
            "id": "chunk_01",
            "document_id": d["id"],
            "course_id": c["id"],
            "chunk_index": 0,
            "content": "Chunk one content about linear regression.",
            "source_type": "pdf",
            "page_number": 4,
            "slide_number": None,
            "start_timestamp": None,
            "end_timestamp": None,
            "topic": "Regression",
            "embedding": [0.0] * 768,
            "metadata": {"chapter": "Chapter 1", "author": "Professor X", "is_pseudo": True}
        },
        {
            "id": "chunk_02",
            "document_id": d["id"],
            "course_id": c["id"],
            "chunk_index": 1,
            "content": "Chunk two content about logistic regression.",
            "source_type": "pdf",
            "page_number": 7,
            "slide_number": None,
            "start_timestamp": None,
            "end_timestamp": None,
            "topic": "Classification",
            "embedding": [0.0] * 768,
            "metadata": {"chapter": "Chapter 2", "formula": "sigmoid(z)", "is_pseudo": True}
        }
    ])

    reindexer = ReindexerService()

    # Mock Gemini batch embedding
    mock_vectors = [[0.05] * 768, [0.08] * 768]

    with patch("app.services.retrieval.reindexer.storage", test_storage):
        with patch("app.services.retrieval.reindexer.gemini_service.is_configured", return_value=True):
            with patch("app.services.retrieval.reindexer.gemini_service.embedding_model_name", "gemini-embedding-001"):
                with patch("app.services.retrieval.reindexer.gemini_service.embedding_dimension", 768):
                    with patch("app.services.retrieval.reindexer.gemini_service.get_embeddings_batch", return_value=mock_vectors):
                        # First run: should re-index both chunks
                        rep1 = reindexer.reindex(batch_size=2)
                        assert rep1["total_chunks"] == 2
                        assert rep1["reindexed"] == 2
                        assert rep1["failed"] == 0

                        # Check that database records preserved all custom metadata
                        chunks_after = test_storage.get_all_chunks()
                        assert len(chunks_after) == 2
                        # Verify chunk 1
                        c1 = next(x for x in chunks_after if x["id"] == "chunk_01")
                        assert c1["page_number"] == 4
                        assert c1["metadata"]["chapter"] == "Chapter 1"
                        assert c1["metadata"]["author"] == "Professor X"
                        assert c1["metadata"]["is_pseudo"] is False
                        assert c1["metadata"]["embedding_model"] == "gemini-embedding-001"
                        assert c1["embedding"] == [0.05] * 768

                        # Verify chunk 2
                        c2 = next(x for x in chunks_after if x["id"] == "chunk_02")
                        assert c2["page_number"] == 7
                        assert c2["metadata"]["formula"] == "sigmoid(z)"
                        assert c2["metadata"]["is_pseudo"] is False
                        assert c2["embedding"] == [0.08] * 768

                        # Second run: Idempotency check -> nothing should be reindexed
                        rep2 = reindexer.reindex(batch_size=2)
                        assert rep2["total_chunks"] == 2
                        assert rep2["reindexed"] == 0
                        assert rep2["already_indexed"] == 2
                        assert rep2["status"] == "up_to_date"
