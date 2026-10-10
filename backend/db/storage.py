import os
import json
import sqlite3
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np
from app.core.config import settings

class LocalStorageEngine:
    """
    Lightweight, embedded SQLite + Numpy vector storage engine.
    Fully compatible with the Supabase schema, allowing zero-friction local execution.
    """
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(settings.DATA_DIR, "learnmate.db")
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                ingestion_status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                total_pages_or_slides INTEGER,
                duration_seconds REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                chunk_type TEXT NOT NULL DEFAULT 'text',
                source_type TEXT NOT NULL,
                page_number INTEGER,
                slide_number INTEGER,
                start_timestamp TEXT,
                end_timestamp TEXT,
                topic TEXT,
                concept TEXT,
                embedding TEXT, -- JSON serialized vector
                metadata TEXT,  -- JSON serialized dict
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_mastery (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                topic_name TEXT NOT NULL,
                mastery_score REAL DEFAULT 0.1,
                p_transit REAL DEFAULT 0.15,
                p_guess REAL DEFAULT 0.20,
                p_slip REAL DEFAULT 0.10,
                attempts_count INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                last_attempt_at TEXT NOT NULL,
                UNIQUE(user_id, topic_name)
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id TEXT PRIMARY KEY,
                course_id TEXT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                assessment_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                total_questions INTEGER NOT NULL,
                score REAL,
                status TEXT NOT NULL,
                questions_json TEXT NOT NULL,
                misconceptions_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                run_name TEXT NOT NULL,
                dataset_type TEXT NOT NULL,
                faithfulness REAL NOT NULL,
                answer_relevancy REAL NOT NULL,
                context_precision REAL NOT NULL,
                context_recall REAL NOT NULL,
                question_repetition_rate REAL NOT NULL,
                grounded_accuracy REAL NOT NULL,
                unsupported_rejection_rate REAL NOT NULL,
                citation_precision REAL NOT NULL,
                simulation_results_json TEXT NOT NULL,
                sample_evaluations_json TEXT NOT NULL
            );
            """)
            conn.commit()

    # ------------------ Courses ------------------
    def create_course(self, title: str, description: str = "") -> Dict[str, Any]:
        course_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO courses (id, title, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (course_id, title, description, now, now)
            )
            conn.commit()
        return {"id": course_id, "title": title, "description": description, "created_at": now}

    def list_courses(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM courses ORDER BY created_at DESC")
            rows = cursor.fetchall()
            courses = []
            for r in rows:
                c_id = r["id"]
                # Count docs
                c_docs = conn.execute("SELECT COUNT(*) FROM documents WHERE course_id = ?", (c_id,)).fetchone()[0]
                # Distinct topics
                c_topics = conn.execute("SELECT COUNT(DISTINCT topic) FROM document_chunks WHERE course_id = ? AND topic IS NOT NULL", (c_id,)).fetchone()[0]
                courses.append({
                    "id": c_id,
                    "title": r["title"],
                    "description": r["description"],
                    "documents_count": c_docs,
                    "topics_count": c_topics,
                    "created_at": r["created_at"]
                })
            return courses

    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
            row = cursor.fetchone()
            if not row:
                return None
            c_docs = conn.execute("SELECT COUNT(*) FROM documents WHERE course_id = ?", (course_id,)).fetchone()[0]
            c_topics = conn.execute("SELECT COUNT(DISTINCT topic) FROM document_chunks WHERE course_id = ? AND topic IS NOT NULL", (course_id,)).fetchone()[0]
            return {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "documents_count": c_docs,
                "topics_count": c_topics,
                "created_at": row["created_at"]
            }

    # ------------------ Documents ------------------
    def create_document(self, course_id: str, filename: str, file_type: str, file_path: str) -> Dict[str, Any]:
        doc_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO documents (id, course_id, filename, file_type, file_path, ingestion_status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (doc_id, course_id, filename, file_type, file_path, now, now)
            )
            conn.commit()
        return {
            "id": doc_id, "course_id": course_id, "filename": filename,
            "file_type": file_type, "ingestion_status": "pending", "created_at": now
        }

    def update_document(self, doc_id: str, status: str, total_pages_or_slides: Optional[int] = None,
                        duration_seconds: Optional[float] = None, error_message: Optional[str] = None):
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE documents SET ingestion_status = ?, total_pages_or_slides = ?, duration_seconds = ?,
                   error_message = ?, updated_at = ? WHERE id = ?""",
                (status, total_pages_or_slides, duration_seconds, error_message, now, doc_id)
            )
            conn.commit()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            if not row:
                return None
            c_count = conn.execute("SELECT COUNT(*) FROM document_chunks WHERE document_id = ?", (doc_id,)).fetchone()[0]
            return {
                "id": row["id"],
                "course_id": row["course_id"],
                "filename": row["filename"],
                "file_type": row["file_type"],
                "ingestion_status": row["ingestion_status"],
                "error_message": row["error_message"],
                "total_pages_or_slides": row["total_pages_or_slides"],
                "duration_seconds": row["duration_seconds"],
                "chunks_count": c_count,
                "created_at": row["created_at"]
            }

    def list_documents(self, course_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE course_id = ? ORDER BY created_at DESC", (course_id,))
            rows = cursor.fetchall()
            docs = []
            for r in rows:
                c_count = conn.execute("SELECT COUNT(*) FROM document_chunks WHERE document_id = ?", (r["id"],)).fetchone()[0]
                docs.append({
                    "id": r["id"],
                    "course_id": r["course_id"],
                    "filename": r["filename"],
                    "file_type": r["file_type"],
                    "ingestion_status": r["ingestion_status"],
                    "error_message": r["error_message"],
                    "total_pages_or_slides": r["total_pages_or_slides"],
                    "duration_seconds": r["duration_seconds"],
                    "chunks_count": c_count,
                    "created_at": r["created_at"]
                })
            return docs

    # ------------------ Chunks ------------------
    def save_chunks(self, chunks: List[Dict[str, Any]]):
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for c in chunks:
                chunk_id = c.get("id") or str(uuid.uuid4())
                emb_str = json.dumps(c.get("embedding")) if c.get("embedding") else None
                meta_str = json.dumps(c.get("metadata", {}))
                cursor.execute(
                    """INSERT INTO document_chunks (
                        id, document_id, course_id, chunk_index, content, chunk_type, source_type,
                        page_number, slide_number, start_timestamp, end_timestamp, topic, concept,
                        embedding, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chunk_id, c["document_id"], c["course_id"], c["chunk_index"],
                        c["content"], c.get("chunk_type", "text"), c["source_type"],
                        c.get("page_number"), c.get("slide_number"),
                        c.get("start_timestamp"), c.get("end_timestamp"),
                        c.get("topic"), c.get("concept"), emb_str, meta_str, now
                    )
                )
            conn.commit()

    def get_chunks_for_course(self, course_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, d.filename FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.course_id = ? ORDER BY c.chunk_index ASC
            """, (course_id,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "document_id": r["document_id"],
                    "course_id": r["course_id"],
                    "filename": r["filename"],
                    "chunk_index": r["chunk_index"],
                    "content": r["content"],
                    "chunk_type": r["chunk_type"],
                    "source_type": r["source_type"],
                    "page_number": r["page_number"],
                    "slide_number": r["slide_number"],
                    "start_timestamp": r["start_timestamp"],
                    "end_timestamp": r["end_timestamp"],
                    "topic": r["topic"],
                    "concept": r["concept"],
                    "embedding": json.loads(r["embedding"]) if r["embedding"] else None,
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {}
                })
            return results

    def get_all_topics(self, course_id: Optional[str] = None) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if course_id:
                cursor.execute("SELECT DISTINCT topic FROM document_chunks WHERE course_id = ? AND topic IS NOT NULL", (course_id,))
            else:
                cursor.execute("SELECT DISTINCT topic FROM document_chunks WHERE topic IS NOT NULL")
            rows = cursor.fetchall()
            return [r[0] for r in rows if r[0]]

    # ------------------ Topic Mastery (BKT) ------------------
    def get_topic_mastery(self, user_id: str, topic_name: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topic_mastery WHERE user_id = ? AND topic_name = ?", (user_id, topic_name))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def save_topic_mastery(self, user_id: str, topic_name: str, mastery_score: float,
                           p_transit: float = 0.15, p_guess: float = 0.20, p_slip: float = 0.10,
                           attempts_delta: int = 1, correct_delta: int = 0) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topic_mastery WHERE user_id = ? AND topic_name = ?", (user_id, topic_name))
            row = cursor.fetchone()
            if row:
                att = row["attempts_count"] + attempts_delta
                corr = row["correct_count"] + correct_delta
                cursor.execute(
                    """UPDATE topic_mastery SET mastery_score = ?, p_transit = ?, p_guess = ?, p_slip = ?,
                       attempts_count = ?, correct_count = ?, last_attempt_at = ? WHERE id = ?""",
                    (mastery_score, p_transit, p_guess, p_slip, att, corr, now, row["id"])
                )
            else:
                m_id = str(uuid.uuid4())
                cursor.execute(
                    """INSERT INTO topic_mastery (id, user_id, topic_name, mastery_score, p_transit, p_guess, p_slip, attempts_count, correct_count, last_attempt_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (m_id, user_id, topic_name, mastery_score, p_transit, p_guess, p_slip, attempts_delta, correct_delta, now)
                )
            conn.commit()
        return self.get_topic_mastery(user_id, topic_name)

    def list_topic_masteries(self, user_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topic_mastery WHERE user_id = ? ORDER BY mastery_score ASC", (user_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # ------------------ Assessments ------------------
    def save_assessment(self, assessment_data: Dict[str, Any]) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO assessments (
                    id, course_id, user_id, title, assessment_type, difficulty,
                    total_questions, score, status, questions_json, misconceptions_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    assessment_data["id"],
                    assessment_data.get("course_id"),
                    assessment_data["user_id"],
                    assessment_data["title"],
                    assessment_data["assessment_type"],
                    assessment_data["difficulty"],
                    assessment_data["total_questions"],
                    assessment_data.get("score"),
                    assessment_data["status"],
                    json.dumps(assessment_data.get("questions", [])),
                    json.dumps(assessment_data.get("misconceptions", [])),
                    assessment_data.get("created_at", datetime.utcnow().isoformat())
                )
            )
            conn.commit()
        return assessment_data["id"]

    def get_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "course_id": row["course_id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "assessment_type": row["assessment_type"],
                "difficulty": row["difficulty"],
                "total_questions": row["total_questions"],
                "score": row["score"],
                "status": row["status"],
                "questions": json.loads(row["questions_json"]),
                "misconceptions": json.loads(row["misconceptions_json"]),
                "created_at": row["created_at"]
            }

    def update_assessment(self, assessment_id: str, score: float, status: str, questions: List[Dict[str, Any]], misconceptions: List[Dict[str, Any]]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE assessments SET score = ?, status = ?, questions_json = ?, misconceptions_json = ? WHERE id = ?""",
                (score, status, json.dumps(questions), json.dumps(misconceptions), assessment_id)
            )
            conn.commit()

    def list_assessments(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "course_id": r["course_id"],
                    "user_id": r["user_id"],
                    "title": r["title"],
                    "assessment_type": r["assessment_type"],
                    "difficulty": r["difficulty"],
                    "total_questions": r["total_questions"],
                    "score": r["score"],
                    "status": r["status"],
                    "questions": json.loads(r["questions_json"]),
                    "misconceptions": json.loads(r["misconceptions_json"]),
                    "created_at": r["created_at"]
                })
            return results

    # ------------------ Evaluation Runs ------------------
    def save_evaluation_run(self, eval_run: Dict[str, Any]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO evaluation_runs (
                    id, timestamp, run_name, dataset_type, faithfulness, answer_relevancy,
                    context_precision, context_recall, question_repetition_rate,
                    grounded_accuracy, unsupported_rejection_rate, citation_precision,
                    simulation_results_json, sample_evaluations_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    eval_run["id"],
                    eval_run["timestamp"],
                    eval_run["run_name"],
                    eval_run["dataset_type"],
                    eval_run["metrics"]["faithfulness"],
                    eval_run["metrics"]["answer_relevancy"],
                    eval_run["metrics"]["context_precision"],
                    eval_run["metrics"]["context_recall"],
                    eval_run["metrics"]["question_repetition_rate"],
                    eval_run["metrics"]["grounded_accuracy"],
                    eval_run["metrics"]["unsupported_rejection_rate"],
                    eval_run["metrics"]["citation_precision"],
                    json.dumps(eval_run.get("simulation_results", {})),
                    json.dumps(eval_run.get("sample_evaluations", []))
                )
            )
            conn.commit()

    def list_evaluation_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evaluation_runs ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "run_name": r["run_name"],
                    "dataset_type": r["dataset_type"],
                    "metrics": {
                        "faithfulness": r["faithfulness"],
                        "answer_relevancy": r["answer_relevancy"],
                        "context_precision": r["context_precision"],
                        "context_recall": r["context_recall"],
                        "question_repetition_rate": r["question_repetition_rate"],
                        "grounded_accuracy": r["grounded_accuracy"],
                        "unsupported_rejection_rate": r["unsupported_rejection_rate"],
                        "citation_precision": r["citation_precision"]
                    },
                    "simulation_results": json.loads(r["simulation_results_json"]),
                    "sample_evaluations": json.loads(r["sample_evaluations_json"])
                })
            return results

# Singleton instance
storage = LocalStorageEngine()
