import os
import json
import sqlite3
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
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
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS delivered_questions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                normalized_prompt TEXT NOT NULL,
                topic_name TEXT,
                delivered_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deliv_user ON delivered_questions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deliv_fingerprint ON delivered_questions(fingerprint);")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessment_answers (
                id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                submitted_answer TEXT,
                is_correct INTEGER NOT NULL,
                score REAL NOT NULL,
                grading_method TEXT,
                feedback TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(assessment_id, question_id)
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ans_user ON assessment_answers(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ans_assessment ON assessment_answers(assessment_id);")

            # Gracefully ensure started_at and completed_at columns exist in assessments table
            cursor.execute("PRAGMA table_info(assessments)")
            existing_cols = [r[1] for r in cursor.fetchall()]
            if "started_at" not in existing_cols:
                cursor.execute("ALTER TABLE assessments ADD COLUMN started_at TEXT")
            if "completed_at" not in existing_cols:
                cursor.execute("ALTER TABLE assessments ADD COLUMN completed_at TEXT")

            # Phase 4: Mastery History Audit Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mastery_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                topic_name TEXT NOT NULL,
                assessment_id TEXT,
                mastery_score REAL NOT NULL,
                previous_score REAL NOT NULL,
                is_correct INTEGER,
                score_delta REAL NOT NULL,
                observed_score REAL,
                p_transit REAL NOT NULL,
                p_guess REAL NOT NULL,
                p_slip REAL NOT NULL,
                recorded_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_user_topic ON mastery_history(user_id, topic_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_user_time ON mastery_history(user_id, recorded_at);")

            # Phase 4: Topic Prerequisites Knowledge Graph
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_prerequisites (
                id TEXT PRIMARY KEY,
                course_id TEXT,
                topic_name TEXT NOT NULL,
                prerequisite_topic TEXT NOT NULL,
                UNIQUE(course_id, topic_name, prerequisite_topic)
            );
            """)

            # Gracefully ensure spaced repetition columns exist in topic_mastery table
            cursor.execute("PRAGMA table_info(topic_mastery)")
            existing_tm_cols = [r[1] for r in cursor.fetchall()]
            if "next_review_at" not in existing_tm_cols:
                cursor.execute("ALTER TABLE topic_mastery ADD COLUMN next_review_at TEXT")
            if "review_interval_days" not in existing_tm_cols:
                cursor.execute("ALTER TABLE topic_mastery ADD COLUMN review_interval_days REAL DEFAULT 1.0")
            if "consecutive_correct" not in existing_tm_cols:
                cursor.execute("ALTER TABLE topic_mastery ADD COLUMN consecutive_correct INTEGER DEFAULT 0")
            if "repetition_count" not in existing_tm_cols:
                cursor.execute("ALTER TABLE topic_mastery ADD COLUMN repetition_count INTEGER DEFAULT 0")

            # Phase 3: User Accounts Schema
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")

            # Phase 2 & 4: Course Ownership and Visibility Schema Migration
            cursor.execute("PRAGMA table_info(courses)")
            existing_course_cols = [r[1] for r in cursor.fetchall()]
            if "owner_id" not in existing_course_cols:
                cursor.execute("ALTER TABLE courses ADD COLUMN owner_id TEXT")
            if "visibility" not in existing_course_cols:
                cursor.execute("ALTER TABLE courses ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'")
            if "is_demo" not in existing_course_cols:
                cursor.execute("ALTER TABLE courses ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_owner ON courses(owner_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_visibility ON courses(visibility);")

            # Designated shared demo courses:
            # Preserves all existing notes, embeddings, chunks, and citations!
            cursor.execute("""
                UPDATE courses 
                SET visibility = 'shared_demo', is_demo = 1, title = 'BEFA (Shared Demo)'
                WHERE id = '562df001-4a84-4593-86b5-8815cf2f5170' OR LOWER(title) = 'befa'
            """)
            cursor.execute("""
                UPDATE courses 
                SET visibility = 'shared_demo', is_demo = 1
                WHERE id = 'cd781c49-8d52-4a53-835f-a0e003bec7cf' OR LOWER(title) LIKE '%cs229%'
            """)

            # Seed default curriculum prerequisites
            canonical_prereqs = [
                (None, "Gradient Descent", "Supervised Learning"),
                (None, "Gradient Descent", "Linear Regression"),
                (None, "Optimization Dynamics", "Gradient Descent"),
                (None, "Optimization Algorithms", "Optimization Dynamics"),
                (None, "Neural Network Architectures", "Gradient Descent"),
                (None, "Neural Networks", "Gradient Descent"),
                (None, "Generalization & Regularization", "Supervised Learning"),
            ]
            for c_id, top, prereq in canonical_prereqs:
                p_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT OR IGNORE INTO topic_prerequisites (id, course_id, topic_name, prerequisite_topic) VALUES (?, ?, ?, ?)",
                    (p_id, c_id, top, prereq)
                )

            conn.commit()

    # ------------------ Users ------------------
    def create_user(self, email: str, password_hash: str, full_name: Optional[str] = None, role: str = "user") -> Dict[str, Any]:
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        clean_email = email.lower().strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (id, email, password_hash, full_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, clean_email, password_hash, full_name, role, now, now)
            )
            conn.commit()
        return {
            "id": user_id,
            "email": clean_email,
            "full_name": full_name,
            "role": role,
            "created_at": now,
            "updated_at": now
        }

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        clean_email = email.lower().strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (clean_email,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def count_users(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

    def bootstrap_admin_user(self, email: str, password_hash: str, full_name: str = "System Administrator") -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            if cursor.fetchone()[0] == 0:
                admin_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute(
                    "INSERT INTO users (id, email, password_hash, full_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, 'admin', ?, ?)",
                    (admin_id, email.lower().strip(), password_hash, full_name, now, now)
                )
                conn.commit()
                return admin_id
            return None

    # ------------------ Courses ------------------
    def create_course(
        self,
        title: str,
        description: str = "",
        owner_id: Optional[str] = None,
        visibility: str = "private",
        is_demo: int = 0
    ) -> Dict[str, Any]:
        course_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO courses (id, title, description, owner_id, visibility, is_demo, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (course_id, title, description, owner_id, visibility, is_demo, now, now)
            )
            conn.commit()
        return {
            "id": course_id,
            "title": title,
            "description": description,
            "owner_id": owner_id,
            "visibility": visibility,
            "is_demo": bool(is_demo),
            "created_at": now
        }

    def list_courses(self, user_id: Optional[str] = None, is_admin: bool = False) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if is_admin:
                cursor.execute("SELECT * FROM courses ORDER BY is_demo DESC, created_at DESC")
            elif user_id:
                cursor.execute(
                    "SELECT * FROM courses WHERE visibility = 'shared_demo' OR owner_id = ? ORDER BY is_demo DESC, created_at DESC",
                    (user_id,)
                )
            else:
                cursor.execute("SELECT * FROM courses WHERE visibility = 'shared_demo' ORDER BY is_demo DESC, created_at DESC")
            rows = cursor.fetchall()
            courses = []
            for r in rows:
                c_id = r["id"]
                c_docs = conn.execute("SELECT COUNT(*) FROM documents WHERE course_id = ?", (c_id,)).fetchone()[0]
                c_topics = conn.execute("SELECT COUNT(DISTINCT topic) FROM document_chunks WHERE course_id = ? AND topic IS NOT NULL", (c_id,)).fetchone()[0]
                courses.append({
                    "id": c_id,
                    "title": r["title"],
                    "description": r["description"],
                    "owner_id": r["owner_id"] if "owner_id" in r.keys() else None,
                    "visibility": r["visibility"] if "visibility" in r.keys() else "private",
                    "is_demo": bool(r["is_demo"]) if "is_demo" in r.keys() else False,
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
                # Allow resolving shared demo courses by title prefix or keyword (e.g. "CS229" or "befa")
                cursor.execute(
                    "SELECT * FROM courses WHERE (visibility = 'shared_demo' OR is_demo = 1) AND (LOWER(title) LIKE ? OR LOWER(id) = ?)",
                    (f"%{course_id.lower()}%", course_id.lower())
                )
                row = cursor.fetchone()
            if not row:
                return None
            real_id = row["id"]
            c_docs = conn.execute("SELECT COUNT(*) FROM documents WHERE course_id = ?", (real_id,)).fetchone()[0]
            c_topics = conn.execute("SELECT COUNT(DISTINCT topic) FROM document_chunks WHERE course_id = ? AND topic IS NOT NULL", (real_id,)).fetchone()[0]
            return {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "owner_id": row["owner_id"] if "owner_id" in row.keys() else None,
                "visibility": row["visibility"] if "visibility" in row.keys() else "private",
                "is_demo": bool(row["is_demo"]) if "is_demo" in row.keys() else False,
                "documents_count": c_docs,
                "topics_count": c_topics,
                "created_at": row["created_at"]
            }

    def is_course_accessible(self, course_id: str, user_id: Optional[str] = None, is_admin: bool = False) -> bool:
        course = self.get_course(course_id)
        if not course:
            return False
        if is_admin:
            return True
        if course.get("visibility") == "shared_demo" or course.get("is_demo"):
            return True
        if user_id and course.get("owner_id") == user_id:
            return True
        return False

    def is_course_modifiable(self, course_id: str, user_id: Optional[str] = None, is_admin: bool = False) -> bool:
        course = self.get_course(course_id)
        if not course:
            return False
        if is_admin:
            return True
        if course.get("is_demo") or course.get("visibility") == "shared_demo":
            return False
        if user_id and course.get("owner_id") == user_id:
            return True
        return False

    def delete_course(self, course_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            cursor.execute("DELETE FROM documents WHERE course_id = ?", (course_id,))
            cursor.execute("DELETE FROM document_chunks WHERE course_id = ?", (course_id,))
            cursor.execute("DELETE FROM topic_prerequisites WHERE course_id = ?", (course_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_document(self, doc_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            row = conn.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if row and row["file_path"] and os.path.exists(row["file_path"]):
                try:
                    os.remove(row["file_path"])
                except Exception:
                    pass
            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ------------------ Documents ------------------
    def create_document(self, course_id: str, filename: str, file_type: str, file_path: str) -> Dict[str, Any]:
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
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
    def delete_chunks_by_document(self, document_id: str) -> int:
        """Deletes all existing chunks for a document, preventing duplicates on resume/retry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted

    def save_chunks(self, chunks: List[Dict[str, Any]], replace_for_document: bool = False):
        if not chunks:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if replace_for_document:
                doc_ids = set(c["document_id"] for c in chunks if "document_id" in c)
                for d_id in doc_ids:
                    cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (d_id,))
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

    def get_all_chunks(self, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if course_id:
                cursor.execute("""
                    SELECT c.*, d.filename FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE c.course_id = ? ORDER BY c.course_id, c.chunk_index ASC
                """, (course_id,))
            else:
                cursor.execute("""
                    SELECT c.*, d.filename FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    ORDER BY c.course_id, c.chunk_index ASC
                """)
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

    def update_chunk_embedding(self, chunk_id: str, embedding: List[float], metadata: Dict[str, Any]):
        emb_str = json.dumps(embedding)
        meta_str = json.dumps(metadata)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE document_chunks SET embedding = ?, metadata = ? WHERE id = ?",
                (emb_str, meta_str, chunk_id)
            )
            conn.commit()

    def batch_update_chunk_embeddings(self, updates: List[Dict[str, Any]]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for u in updates:
                emb_str = json.dumps(u["embedding"])
                meta_str = json.dumps(u["metadata"])
                cursor.execute(
                    "UPDATE document_chunks SET embedding = ?, metadata = ? WHERE id = ?",
                    (emb_str, meta_str, u["id"])
                )
            conn.commit()


    def get_all_topics(self, course_id: Optional[str] = None) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if course_id:
                cursor.execute("SELECT DISTINCT topic FROM document_chunks WHERE course_id = ? AND topic IS NOT NULL", (course_id,))
            else:
                cursor.execute("SELECT DISTINCT topic FROM document_chunks WHERE topic IS NOT NULL")
            rows = cursor.fetchall()
            return [r[0] for r in rows if r[0]]

    # ------------------ Topic Mastery (BKT) & Personalization ------------------
    def get_topic_mastery(self, user_id: str, topic_name: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topic_mastery WHERE user_id = ? AND topic_name = ?", (user_id, topic_name))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def save_topic_mastery(
        self,
        user_id: str,
        topic_name: str,
        mastery_score: float,
        p_transit: float = 0.15,
        p_guess: float = 0.20,
        p_slip: float = 0.10,
        attempts_delta: int = 1,
        correct_delta: int = 0,
        assessment_id: Optional[str] = None,
        is_correct: Optional[bool] = None,
        observed_score: Optional[float] = None,
        next_review_at: Optional[str] = None,
        review_interval_days: Optional[float] = None,
        consecutive_correct: Optional[int] = None,
        repetition_count_delta: int = 0
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topic_mastery WHERE user_id = ? AND topic_name = ?", (user_id, topic_name))
            row = cursor.fetchone()

            row_dict = dict(row) if row else {}
            previous_score = row_dict.get("mastery_score", 0.15)
            score_delta = round(mastery_score - previous_score, 4)

            curr_interval = row_dict.get("review_interval_days") if row_dict.get("review_interval_days") is not None else 1.0
            curr_streak = row_dict.get("consecutive_correct") if row_dict.get("consecutive_correct") is not None else 0
            curr_reps = row_dict.get("repetition_count") if row_dict.get("repetition_count") is not None else 0

            final_interval = review_interval_days if review_interval_days is not None else curr_interval
            final_streak = consecutive_correct if consecutive_correct is not None else curr_streak
            final_reps = curr_reps + repetition_count_delta
            final_review_at = next_review_at if next_review_at is not None else row_dict.get("next_review_at")

            if row:
                att = row["attempts_count"] + attempts_delta
                corr = row["correct_count"] + correct_delta
                cursor.execute(
                    """UPDATE topic_mastery SET
                        mastery_score = ?, p_transit = ?, p_guess = ?, p_slip = ?,
                        attempts_count = ?, correct_count = ?, last_attempt_at = ?,
                        next_review_at = ?, review_interval_days = ?, consecutive_correct = ?, repetition_count = ?
                    WHERE id = ?""",
                    (mastery_score, p_transit, p_guess, p_slip, att, corr, now,
                     final_review_at, final_interval, final_streak, final_reps, row["id"])
                )
            else:
                m_id = str(uuid.uuid4())
                cursor.execute(
                    """INSERT INTO topic_mastery (
                        id, user_id, topic_name, mastery_score, p_transit, p_guess, p_slip,
                        attempts_count, correct_count, last_attempt_at,
                        next_review_at, review_interval_days, consecutive_correct, repetition_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (m_id, user_id, topic_name, mastery_score, p_transit, p_guess, p_slip,
                     attempts_delta, correct_delta, now,
                     final_review_at, final_interval, final_streak, final_reps)
                )

            # Record in historical audit log if this represents an attempt or explicit mastery change
            if attempts_delta > 0 or assessment_id is not None or is_correct is not None:
                h_id = str(uuid.uuid4())
                cursor.execute(
                    """INSERT INTO mastery_history (
                        id, user_id, topic_name, assessment_id, mastery_score, previous_score,
                        is_correct, score_delta, observed_score, p_transit, p_guess, p_slip, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        h_id,
                        user_id,
                        topic_name,
                        assessment_id,
                        mastery_score,
                        previous_score,
                        1 if is_correct is True else (0 if is_correct is False else None),
                        score_delta,
                        observed_score,
                        p_transit,
                        p_guess,
                        p_slip,
                        now
                    )
                )

            conn.commit()
        return self.get_topic_mastery(user_id, topic_name)

    def list_topic_masteries(self, user_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topic_mastery WHERE user_id = ? ORDER BY mastery_score ASC", (user_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def list_mastery_history(self, user_id: str, topic_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if topic_name:
                cursor.execute(
                    "SELECT * FROM mastery_history WHERE user_id = ? AND topic_name = ? ORDER BY recorded_at DESC LIMIT ?",
                    (user_id, topic_name, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM mastery_history WHERE user_id = ? ORDER BY recorded_at DESC LIMIT ?",
                    (user_id, limit)
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def add_topic_prerequisite(self, course_id_or_topic: Optional[str], topic_name: Optional[str] = None, prerequisite_topic: Optional[str] = None) -> None:
        if prerequisite_topic is None and topic_name is not None:
            c_id = None
            top = course_id_or_topic or ""
            prereq = topic_name
        else:
            c_id = course_id_or_topic
            top = topic_name or ""
            prereq = prerequisite_topic or ""
        p_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR IGNORE INTO topic_prerequisites (id, course_id, topic_name, prerequisite_topic)
                   VALUES (?, ?, ?, ?)""",
                (p_id, c_id, top, prereq)
            )
            conn.commit()

    def get_topic_prerequisites(self, course_id: Optional[str] = None, topic_name: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM topic_prerequisites WHERE 1=1"
            params = []
            if course_id:
                query += " AND (course_id = ? OR course_id IS NULL)"
                params.append(course_id)
            if topic_name:
                query += " AND topic_name = ?"
                params.append(topic_name)
            cursor.execute(query, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    # ------------------ Assessments ------------------
    def save_assessment(self, assessment_data: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO assessments (
                    id, course_id, user_id, title, assessment_type, difficulty,
                    total_questions, score, status, questions_json, misconceptions_json, created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    assessment_data.get("created_at", now),
                    assessment_data.get("started_at"),
                    assessment_data.get("completed_at")
                )
            )
            conn.commit()
        return assessment_data["id"]

    def start_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE assessments SET status = 'in_progress', started_at = COALESCE(started_at, ?) WHERE id = ?""",
                (now, assessment_id)
            )
            conn.commit()
        return self.get_assessment(assessment_id)

    def get_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,))
            row = cursor.fetchone()
            if not row:
                return None
            keys = row.keys()
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
                "created_at": row["created_at"],
                "started_at": row["started_at"] if "started_at" in keys else None,
                "completed_at": row["completed_at"] if "completed_at" in keys else None
            }

    def update_assessment(
        self,
        assessment_id: str,
        score: float,
        status: str,
        questions: List[Dict[str, Any]],
        misconceptions: List[Dict[str, Any]],
        completed_at: Optional[str] = None
    ):
        now = completed_at or datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE assessments SET score = ?, status = ?, questions_json = ?, misconceptions_json = ?, completed_at = ? WHERE id = ?""",
                (score, status, json.dumps(questions), json.dumps(misconceptions), now, assessment_id)
            )
            conn.commit()

    def list_assessments(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                keys = r.keys()
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
                    "created_at": r["created_at"],
                    "started_at": r["started_at"] if "started_at" in keys else None,
                    "completed_at": r["completed_at"] if "completed_at" in keys else None
                })
            return results

    def list_assessments_by_course(self, course_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assessments WHERE course_id = ? ORDER BY created_at DESC LIMIT ?", (course_id, limit))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                keys = r.keys()
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
                    "created_at": r["created_at"],
                    "started_at": r["started_at"] if "started_at" in keys else None,
                    "completed_at": r["completed_at"] if "completed_at" in keys else None
                })
            return results

    # ------------------ Delivered Questions & Duplicate Prevention ------------------
    def save_delivered_questions(self, records: List[Dict[str, Any]]):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for r in records:
                r_id = r.get("id") or str(uuid.uuid4())
                cursor.execute(
                    """INSERT OR IGNORE INTO delivered_questions (
                        id, user_id, assessment_id, question_id, fingerprint, normalized_prompt, topic_name, delivered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        r_id,
                        r["user_id"],
                        r["assessment_id"],
                        r["question_id"],
                        r["fingerprint"],
                        r["normalized_prompt"],
                        r.get("topic_name"),
                        r.get("delivered_at", now)
                    )
                )
            conn.commit()

    def get_delivered_fingerprints(self, user_id: str) -> set:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fingerprint FROM delivered_questions WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            return {r[0] for r in rows if r[0]}

    def get_delivered_prompts(self, user_id: str, limit: int = 200) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT normalized_prompt FROM delivered_questions WHERE user_id = ? ORDER BY delivered_at DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cursor.fetchall()
            return [r[0] for r in rows if r[0]]

    # ------------------ Student Assessment Answers Persistence ------------------
    def save_assessment_answers(self, records: List[Dict[str, Any]]):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for r in records:
                ans_id = r.get("id") or str(uuid.uuid4())
                cursor.execute(
                    """INSERT OR REPLACE INTO assessment_answers (
                        id, assessment_id, user_id, question_id, submitted_answer,
                        is_correct, score, grading_method, feedback, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ans_id,
                        r["assessment_id"],
                        r["user_id"],
                        r["question_id"],
                        r.get("submitted_answer", ""),
                        1 if r.get("is_correct") else 0,
                        float(r.get("score", 1.0 if r.get("is_correct") else 0.0)),
                        r.get("grading_method", "exact"),
                        r.get("feedback", ""),
                        r.get("created_at", now)
                    )
                )
            conn.commit()

    def get_assessment_answers(self, assessment_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM assessment_answers WHERE assessment_id = ? ORDER BY created_at ASC",
                (assessment_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

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
