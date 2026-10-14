#!/usr/bin/env python3
"""
LearnMate AI - Semantic Embeddings Re-indexing Tool
Usage:
    python backend/reindex_embeddings.py [--course-id <id>] [--batch-size 10] [--force]
"""
import sys
import os
import argparse
import logging

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ReindexerCLI")

def main():
    parser = argparse.ArgumentParser(
        description="Re-index LearnMate AI document chunks with genuine Gemini semantic embeddings."
    )
    parser.add_argument(
        "--course-id",
        type=str,
        default=None,
        help="Specific course ID to re-index (default: all courses)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for embedding API calls (default: 10)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay in seconds between batches to respect rate limits (default: 0.2)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-indexing of all chunks, even those already marked genuine"
    )

    args = parser.parse_args()

    from app.core.gemini import gemini_service
    from app.services.retrieval.reindexer import reindexer_service

    print("=" * 65)
    print("  LearnMate AI - Dense Semantic Embedding Re-indexer")
    print("=" * 65)

    if not gemini_service.is_configured():
        print("\n[ERROR] Gemini API is not configured!")
        print("Please ensure GEMINI_API_KEY is configured in backend/.env before running re-indexing.")
        sys.exit(1)

    print(f"Target Embedding Model : {gemini_service.embedding_model_name}")
    print(f"Target Dimension       : {gemini_service.embedding_dimension}")
    print(f"Batch Size             : {args.batch_size}")
    print(f"Filter Course ID       : {args.course_id or 'All Courses'}")
    print(f"Force Re-index         : {args.force}")
    print("-" * 65)

    try:
        report = reindexer_service.reindex(
            course_id=args.course_id,
            batch_size=args.batch_size,
            force=args.force,
            delay_between_batches=args.delay
        )
        print("\n" + "=" * 65)
        print("  Re-indexing Summary")
        print("=" * 65)
        print(f"  Total Chunks Evaluated : {report['total_chunks']}")
        print(f"  Successfully Re-indexed : {report['reindexed']}")
        print(f"  Already Genuine / Kept  : {report['already_indexed']}")
        print(f"  Failed Chunks           : {report['failed']}")
        print(f"  Final Status            : {report['status']}")
        print("=" * 65)

        if report['failed'] > 0:
            sys.exit(2)
        sys.exit(0)

    except Exception as e:
        print(f"\n[FATAL ERROR] Re-indexing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
