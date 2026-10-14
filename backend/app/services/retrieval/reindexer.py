import time
import re
import logging
from typing import Dict, Any, List, Optional
from app.db.storage import storage
from app.core.gemini import gemini_service
from app.core.config import settings

logger = logging.getLogger(__name__)

class ReindexerService:
    """
    Safe, repeatable batch re-indexing service.
    Replaces pseudo-embeddings with genuine Gemini embeddings (768 dimensions),
    preserves original content and all source metadata, handles API rate limits,
    and safely resumes if interrupted.
    """
    def reindex(
        self,
        course_id: Optional[str] = None,
        batch_size: int = 15,
        force: bool = False,
        delay_between_batches: float = 0.5,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        if not gemini_service.is_gemini_configured():
            raise RuntimeError(
                "Cannot perform live re-indexing: GEMINI_API_KEY is not configured or invalid. "
                "Configure a valid key in backend/.env before re-indexing."
            )

        all_chunks = storage.get_all_chunks(course_id=course_id)
        target_model = gemini_service.embedding_model_name
        target_dim = gemini_service.embedding_dimension

        # Identify chunks requiring genuine embeddings
        chunks_to_process = []
        already_indexed = 0

        for chunk in all_chunks:
            meta = chunk.get("metadata", {}) or {}
            is_pseudo = meta.get("is_pseudo", True) if "is_pseudo" in meta else (meta.get("embedding_model") != target_model)
            emb = chunk.get("embedding")
            wrong_dim = (not emb) or (len(emb) != target_dim)
            wrong_model = meta.get("embedding_model") != target_model

            if force or is_pseudo or wrong_dim or wrong_model:
                chunks_to_process.append(chunk)
            else:
                already_indexed += 1

        total_chunks = len(all_chunks)
        pending_count = len(chunks_to_process)

        if pending_count == 0:
            logger.info("All chunks already have genuine embeddings up-to-date. Nothing to re-index.")
            return {
                "total_chunks": total_chunks,
                "reindexed": 0,
                "already_indexed": already_indexed,
                "failed": 0,
                "model": target_model,
                "dimension": target_dim,
                "status": "up_to_date"
            }

        logger.info(
            f"Starting re-indexing for {pending_count} / {total_chunks} chunks "
            f"(batch_size={batch_size}, target_model={target_model}). Already genuine: {already_indexed}."
        )

        succeeded = 0
        failed = 0

        for i in range(0, pending_count, batch_size):
            batch = chunks_to_process[i:i + batch_size]
            texts = [c["content"] for c in batch]

            batch_succeeded = False
            for attempt in range(max_retries):
                try:
                    vectors = gemini_service.get_embeddings_batch(texts)
                    updates = []
                    for c, vec in zip(batch, vectors):
                        updated_meta = dict(c.get("metadata", {}) or {})
                        # Preserve all original metadata fields (e.g. chapter, formula, etc.)
                        updated_meta["is_pseudo"] = False
                        updated_meta["embedding_model"] = target_model
                        updated_meta["embedding_version"] = "v1"

                        updates.append({
                            "id": c["id"],
                            "embedding": vec,
                            "metadata": updated_meta
                        })

                    storage.batch_update_chunk_embeddings(updates)
                    succeeded += len(updates)
                    batch_succeeded = True
                    logger.info(f"Re-indexed batch {i // batch_size + 1}: {succeeded}/{pending_count} chunks completed.")
                    break

                except Exception as batch_err:
                    err_str = str(batch_err)
                    is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

                    if is_rate_limit and attempt < max_retries - 1:
                        # Extract suggested retry delay or use exponential backoff
                        delay_match = re.search(r'retryDelay[\'":\s]+(\d+)', err_str) or re.search(r'retry in\s+([\d\.]+)', err_str)
                        wait_seconds = min(60.0, float(delay_match.group(1)) + 1.0) if delay_match else (10.0 * (2 ** attempt))
                        logger.warning(f"Rate limit encountered. Waiting {wait_seconds:.1f}s before retry attempt {attempt + 2}/{max_retries}...")
                        time.sleep(wait_seconds)
                    else:
                        logger.error(f"Batch embedding failed on attempt {attempt + 1}: {batch_err}")
                        if not is_rate_limit or attempt == max_retries - 1:
                            break

            if not batch_succeeded:
                failed += len(batch)

            if delay_between_batches > 0:
                time.sleep(delay_between_batches)

        logger.info(f"Re-indexing complete: {succeeded} succeeded, {failed} failed. Previously genuine: {already_indexed}.")
        return {
            "total_chunks": total_chunks,
            "reindexed": succeeded,
            "already_indexed": already_indexed,
            "failed": failed,
            "model": target_model,
            "dimension": target_dim,
            "status": "completed" if failed == 0 else "partial_failure"
        }

reindexer_service = ReindexerService()
