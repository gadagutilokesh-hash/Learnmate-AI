import math
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core.gemini import gemini_service
from app.db.storage import storage
from app.models.schema import Citation

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    State-of-the-art hybrid retriever combining BM25 keyword matching with
    dense semantic vector cosine similarity using Reciprocal Rank Fusion (RRF).
    """
    def __init__(self, alpha: float = 0.5, rrf_k: int = 60):
        self.alpha = alpha  # Weight between keyword and dense vector
        self.rrf_k = rrf_k  # Constant for RRF smoothing

    def retrieve(
        self,
        query: str,
        course_id: Optional[str] = None,
        top_k: int = 5,
        min_relevance: float = 0.30
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top_k chunks for query using hybrid fusion, filtered by relevance.
        """
        # Fetch candidate chunks for course
        all_chunks = storage.get_chunks_for_course(course_id) if course_id else []
        if not all_chunks:
            # Try fetching all chunks across all courses if course_id is None
            courses = storage.list_courses()
            for c in courses:
                all_chunks.extend(storage.get_chunks_for_course(c["id"]))

        if not all_chunks:
            return []

        # 1. BM25 Keyword Retrieval
        bm25_scores, max_bm25 = self._score_bm25(query, all_chunks)

        # 2. Dense Semantic Vector Retrieval
        vector_scores = self._score_vector(query, all_chunks)

        # 3. Reciprocal Rank Fusion & Strict Grounding Filtering
        scored_chunks = []
        for idx, chunk in enumerate(all_chunks):
            b_score = bm25_scores[idx]
            v_score = vector_scores[idx]

            # If there is ZERO keyword overlap in the entire corpus, demand very high vector confidence
            if max_bm25 <= 0.0 and v_score < 0.75:
                continue

            hybrid_score = (self.alpha * b_score) + ((1.0 - self.alpha) * v_score)

            # Strict relevance requirement
            if hybrid_score >= min_relevance and (b_score > 0.0 or v_score >= 0.70):
                chunk_copy = dict(chunk)
                chunk_copy["hybrid_score"] = float(hybrid_score)
                chunk_copy["bm25_score"] = float(b_score)
                chunk_copy["vector_score"] = float(v_score)
                scored_chunks.append(chunk_copy)

        # Sort descending by hybrid_score
        scored_chunks.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return scored_chunks[:top_k]

    STOP_WORDS = {
        "a", "an", "the", "is", "are", "was", "were", "what", "how", "why", "where",
        "when", "which", "who", "whom", "this", "that", "these", "those", "for", "with",
        "in", "on", "at", "to", "from", "by", "about", "as", "of", "and", "or", "but",
        "so", "if", "then", "else", "not", "no", "can", "could", "would", "should", "do",
        "does", "did", "have", "has", "had", "be", "been", "being"
    }

    def _score_bm25(self, query: str, chunks: List[Dict[str, Any]]):
        # Tokenize corpus without punctuation
        tokenized_corpus = [
            [w.strip(".,!?:;\"'()[]") for w in chunk["content"].lower().split() if w.strip(".,!?:;\"'()[]") not in self.STOP_WORDS]
            for chunk in chunks
        ]
        bm25 = BM25Okapi(tokenized_corpus)
        query_tokens = [
            w.strip(".,!?:;\"'()[]") for w in query.lower().split()
            if w.strip(".,!?:;\"'()[]") not in self.STOP_WORDS and len(w.strip(".,!?:;\"'()[]")) > 2
        ]
        if not query_tokens:
            return [0.0] * len(chunks), 0.0

        raw_scores = bm25.get_scores(query_tokens)
        max_score = float(max(raw_scores)) if len(raw_scores) > 0 else 0.0
        if max_score <= 0.0:
            return [0.0] * len(chunks), 0.0

        normalized = [float(s / max_score) for s in raw_scores]
        return normalized, max_score

    def _score_vector(self, query: str, chunks: List[Dict[str, Any]]) -> List[float]:
        query_emb = np.array(gemini_service.get_embedding(query), dtype=np.float32)
        q_norm = np.linalg.norm(query_emb)
        if q_norm > 0:
            query_emb = query_emb / q_norm

        scores = []
        for chunk in chunks:
            chunk_emb_raw = chunk.get("embedding")
            if not chunk_emb_raw:
                # Generate embedding lazily if not stored
                chunk_emb_raw = gemini_service.get_embedding(chunk["content"])
                chunk["embedding"] = chunk_emb_raw

            c_emb = np.array(chunk_emb_raw, dtype=np.float32)
            c_norm = np.linalg.norm(c_emb)
            if c_norm > 0:
                c_emb = c_emb / c_norm

            sim = float(np.dot(query_emb, c_emb))
            # Clip cosine similarity to [0, 1]
            sim_normalized = max(0.0, min(1.0, sim))
            scores.append(sim_normalized)

        return scores

    def format_citations(self, chunks: List[Dict[str, Any]]) -> List[Citation]:
        citations = []
        for c in chunks:
            citations.append(Citation(
                source_file=c.get("filename", "Course Document"),
                source_type=c.get("source_type", "pdf"),
                page_number=c.get("page_number"),
                slide_number=c.get("slide_number"),
                start_timestamp=c.get("start_timestamp"),
                end_timestamp=c.get("end_timestamp"),
                excerpt=c.get("content", "")[:280] + "..." if len(c.get("content", "")) > 280 else c.get("content", ""),
                relevance_score=c.get("hybrid_score"),
                topic=c.get("topic"),
                concept=c.get("concept")
            ))
        return citations

hybrid_retriever = HybridRetriever()
