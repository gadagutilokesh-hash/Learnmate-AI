import json
import uuid
import logging
import re
import math
import hashlib
from difflib import SequenceMatcher
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field

from app.db.storage import storage
from app.core.gemini import (
    gemini_service, GeminiQuotaExceededError, is_gemini_quota_error,
    extract_gemini_retry_delay, get_friendly_quota_message, sanitize_error
)
from app.models.schema import (
    AssessmentGenerateRequest, AssessmentResponse, AssessmentQuestion,
    Citation, MisconceptionItem, QuizSubmissionRequest, QuizSubmissionResponse,
    QuizGradedQuestion, QuizSubmissionItem
)

logger = logging.getLogger(__name__)

class GeneratedQuestionLLMResponse(BaseModel):
    """
    Pydantic schema enforcing structured generation of individual assessment questions.
    Source metadata is never hallucinated by the model; it is strictly bound to the
    real database chunk by the backend generator.
    """
    prompt: str = Field(description="Clear, unambiguous question text testing comprehension of the course excerpt.")
    question_type: str = Field(description="'mcq', 'short_answer', or 'numerical'")
    options: Optional[List[str]] = Field(default=None, description="For MCQ: list of 4 distinct plausible options prefixed A), B), C), D). For others: null.")
    correct_answer: str = Field(description="Exact correct answer. For MCQ: matches one of the options. For numerical: numeric value. For short_answer: concise reference answer.")
    explanation: str = Field(description="Pedagogical explanation referencing the course excerpt.")
    concept: Optional[str] = Field(default=None, description="Specific concept tested.")
    difficulty: Optional[str] = Field(default="medium", description="'easy', 'medium', or 'hard'")
    numerical_tolerance: Optional[float] = Field(default=0.01, description="For numerical: acceptable tolerance.")
    numerical_unit: Optional[str] = Field(default=None, description="For numerical: unit of measure if applicable.")
    rubric_concepts: Optional[List[str]] = Field(default=None, description="For short_answer: list of key concepts or keywords expected in student response.")

class ShortAnswerEvaluationLLMResponse(BaseModel):
    """Structured semantic grading evaluation for short-answer questions."""
    is_acceptable: bool = Field(description="True if student answer correctly conveys the core concepts from the reference answer and rubric.")
    score: float = Field(description="Score between 0.0 and 1.0 reflecting concept coverage.")
    feedback: str = Field(description="Constructive explanation of what was accurate or missing in the response.")

ASSESSMENT_GEN_SYSTEM_PROMPT = """You are LearnMate AI's rigorous psychometric and educational assessment engine.
Generate assessment questions strictly grounded in the provided course passage.
Rules:
1. Every question must test comprehension or application of a specific fact or concept in the excerpt.
2. For 'mcq', provide 4 plausible options prefixed with A), B), C), D) and exactly ONE verifiably correct answer matching one of the options.
3. For 'numerical', provide the exact numeric value and appropriate tolerance/units.
4. For 'short_answer', provide a concise reference answer and rubric concepts.
5. NEVER invent facts outside the provided passage.
"""

def normalize_text(text: str) -> str:
    """Normalize text for consistent comparison, token overlap, and fingerprinting."""
    t = text.lower().strip()
    t = re.sub(r'[^\w\s]', ' ', t)
    return ' '.join(t.split())

def compute_question_fingerprint(prompt: str, topic: Optional[str] = None) -> str:
    """Compute stable deterministic SHA-256 fingerprint for question deduplication."""
    norm_prompt = normalize_text(prompt)
    norm_topic = normalize_text(topic or "")
    payload = f"{norm_prompt}|{norm_topic}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

class AssessmentService:
    def __init__(self, duplicate_similarity_threshold: float = 0.85, storage: Optional[Any] = None):
        self.duplicate_similarity_threshold = duplicate_similarity_threshold
        self.storage = storage

    # ==========================================================================
    # TASK A & E: Question Generation & Adaptive Selection
    # ==========================================================================
    def generate_assessment(self, req: AssessmentGenerateRequest) -> AssessmentResponse:
        # 1. Fetch chunks for course
        all_course_chunks = storage.get_chunks_for_course(req.course_id)
        if not all_course_chunks:
            raise ValueError(
                f"Course '{req.course_id}' has no uploaded or processed materials. "
                f"Please upload lecture slides, PDFs, or transcripts before generating an assessment."
            )

        # 2. Topic/concept filtering & Insufficient evidence check
        candidate_chunks = list(all_course_chunks)
        if req.topics:
            target_topics_lower = {t.lower().strip() for t in req.topics}
            candidate_chunks = [
                c for c in candidate_chunks
                if c.get("topic") and c.get("topic", "").lower().strip() in target_topics_lower
            ]
            if not candidate_chunks:
                raise ValueError(
                    f"Selected topic(s) ({', '.join(req.topics)}) have insufficient supporting material "
                    f"in the course database. Upload relevant materials covering these topics to generate questions."
                )

        if req.concepts:
            target_concepts_lower = {cp.lower().strip() for cp in req.concepts}
            filtered_by_concept = [
                c for c in candidate_chunks
                if c.get("concept") and c.get("concept", "").lower().strip() in target_concepts_lower
            ]
            if filtered_by_concept:
                candidate_chunks = filtered_by_concept

        # 3. Adaptive Question Selection & Difficulty Tuning
        target_difficulty = self._resolve_target_difficulty(req)
        prioritized_chunks = self._prioritize_chunks_adaptively(candidate_chunks, req)

        # 4. Duplicate Question Tracking
        delivered_fingerprints: Set[str] = set()
        delivered_prompts: List[str] = []
        if not req.allow_revision:
            delivered_fingerprints = storage.get_delivered_fingerprints(req.user_id)
            delivered_prompts = storage.get_delivered_prompts(req.user_id, limit=200)

        # 5. Synthesize Questions across chunks
        questions: List[AssessmentQuestion] = []
        delivered_records: List[Dict[str, Any]] = []
        seen_assessment_fingerprints: Set[str] = set()
        assessment_id = str(uuid.uuid4())

        chunk_pool = list(prioritized_chunks)
        pool_idx = 0

        target_count = max(1, min(20, req.question_count))
        attempts_budget = target_count * 3  # bounded retry loop

        while len(questions) < target_count and attempts_budget > 0 and chunk_pool:
            attempts_budget -= 1
            chunk = chunk_pool[pool_idx % len(chunk_pool)]
            pool_idx += 1

            # Determine question type
            q_type = self._determine_question_type(req.question_type, chunk, len(questions))

            # Bind actual database source provenance (never hallucinated!)
            chunk_citation = Citation(
                source_file=chunk.get("filename", "Course Document"),
                source_type=chunk.get("source_type", "pdf"),
                page_number=chunk.get("page_number"),
                slide_number=chunk.get("slide_number"),
                start_timestamp=chunk.get("start_timestamp"),
                end_timestamp=chunk.get("end_timestamp"),
                excerpt=chunk.get("content", "")[:280],
                topic=chunk.get("topic", "Core Concepts"),
                concept=chunk.get("concept")
            )

            # Generate question with bounded retries
            try:
                q_obj = self._generate_single_question_with_validation(
                    chunk=chunk,
                    citation=chunk_citation,
                    q_type=q_type,
                    difficulty=target_difficulty,
                    delivered_fingerprints=delivered_fingerprints,
                    delivered_prompts=delivered_prompts,
                    seen_in_this_assessment=seen_assessment_fingerprints,
                    allow_revision=req.allow_revision
                )
            except GeminiQuotaExceededError:
                # Requirement 9: Do not automatically retry quota-exhausted requests repeatedly
                raise

            if q_obj:
                fp = compute_question_fingerprint(q_obj.prompt, q_obj.topic_name)
                seen_assessment_fingerprints.add(fp)
                questions.append(q_obj)

                delivered_records.append({
                    "id": str(uuid.uuid4()),
                    "user_id": req.user_id,
                    "assessment_id": assessment_id,
                    "question_id": q_obj.id,
                    "fingerprint": fp,
                    "normalized_prompt": normalize_text(q_obj.prompt),
                    "topic_name": q_obj.topic_name
                })

        if not questions:
            raise ValueError(
                "Unable to generate valid assessment questions from the available course excerpts. "
                "Please verify that the course documents contain adequate conceptual content."
            )

        # 6. Save delivered question tracking
        if delivered_records:
            storage.save_delivered_questions(delivered_records)

        # 7. Persist assessment record in SQLite
        now_iso = datetime.now(timezone.utc).isoformat()
        title = f"{req.assessment_type.replace('_', ' ').title()} - {target_difficulty.capitalize()}"
        assessment_dict = {
            "id": assessment_id,
            "course_id": req.course_id,
            "user_id": req.user_id,
            "title": title,
            "assessment_type": req.assessment_type,
            "difficulty": target_difficulty,
            "total_questions": len(questions),
            "score": None,
            "status": "generated",
            "questions": [q.model_dump() for q in questions],
            "misconceptions": [],
            "created_at": now_iso,
            "started_at": None,
            "completed_at": None
        }
        storage.save_assessment(assessment_dict)

        return AssessmentResponse(
            id=assessment_id,
            course_id=req.course_id,
            user_id=req.user_id,
            title=title,
            assessment_type=req.assessment_type,
            difficulty=target_difficulty,
            total_questions=len(questions),
            score=None,
            status="generated",
            questions=questions,
            misconceptions=[],
            created_at=datetime.fromisoformat(now_iso),
            started_at=None,
            completed_at=None
        )

    def _resolve_target_difficulty(self, req_or_user_id: Any, course_id: Optional[str] = None) -> str:
        if isinstance(req_or_user_id, str):
            user_id = req_or_user_id
            diff_lower = "adaptive"
            c_id = course_id
        else:
            user_id = getattr(req_or_user_id, "user_id", "student_default")
            diff_lower = (getattr(req_or_user_id, "difficulty", "adaptive") or "adaptive").lower()
            c_id = getattr(req_or_user_id, "course_id", None) or course_id

        if diff_lower in ("easy", "beginner"):
            return "beginner"
        elif diff_lower in ("medium", "intermediate"):
            return "intermediate"
        elif diff_lower in ("hard", "advanced"):
            return "advanced"
        elif diff_lower == "mixed":
            return "mixed"

        # Adaptive difficulty resolution based on student mastery and practice history
        from app.services.learner.mastery_model import mastery_service
        try:
            store = getattr(self, "storage", None) or storage
            recent_assessments = store.list_assessments(user_id, limit=5)
            if recent_assessments:
                recent_scores = [a["score"] for a in recent_assessments if a.get("score") is not None]
                if len(recent_scores) >= 2 and all(s >= 0.85 for s in recent_scores[:2]):
                    return "advanced"
                elif len(recent_scores) >= 2 and all(s < 0.50 for s in recent_scores[:2]):
                    return "beginner"

            profile = mastery_service.get_learner_profile(user_id, course_id=c_id)
            # Brand new students receive diagnostic difficulty
            if profile.is_new_learner or not profile.topics:
                return "beginner"

            # Check recent consecutive streak from history audit trail
            history = store.list_mastery_history(user_id, limit=5)
            if history:
                recent_correct = [h["is_correct"] for h in history if h.get("is_correct") is not None]
                # Consecutive success increases difficulty gradually
                if len(recent_correct) >= 3 and all(r == 1 for r in recent_correct[:3]):
                    if profile.overall_mastery >= 0.70:
                        return "advanced"
                    return "intermediate"
                # Repeated mistakes trigger easier practice/revision
                elif len(recent_correct) >= 2 and all(r == 0 for r in recent_correct[:2]):
                    return "beginner"

            # Overall mastery thresholds
            if profile.overall_mastery < 0.45:
                return "beginner"
            elif profile.overall_mastery < 0.75:
                return "intermediate"
            else:
                return "advanced"
        except Exception as e:
            logger.warning(f"Failed to resolve adaptive difficulty for user {user_id}: {e}")
            return "intermediate"
        except Exception:
            return "intermediate"

    def _prioritize_chunks_adaptively(
        self,
        chunks: List[Dict[str, Any]],
        req: AssessmentGenerateRequest
    ) -> List[Dict[str, Any]]:
        # Diagnostic mode: sample evenly across all topics
        if req.assessment_type == "diagnostic":
            by_topic: Dict[str, List[Dict[str, Any]]] = {}
            for c in chunks:
                t = c.get("topic") or "General"
                by_topic.setdefault(t, []).append(c)

            interleaved = []
            max_len = max((len(lst) for lst in by_topic.values()), default=0)
            for i in range(max_len):
                for t_list in by_topic.values():
                    if i < len(t_list):
                        interleaved.append(t_list[i])
            return interleaved or chunks

        # Adaptive mastery prioritization: prioritize weak prerequisites and low-mastery topics
        try:
            masteries = storage.list_topic_masteries(req.user_id)
            mastery_map = {m["topic_name"]: m["mastery_score"] for m in masteries}
            prereqs = storage.get_topic_prerequisites(course_id=req.course_id)
            prereq_weak_set = set()
            for p in prereqs:
                p_topic = p["prerequisite_topic"]
                if mastery_map.get(p_topic, 0.20) < 0.50:
                    prereq_weak_set.add(p_topic)

            # Sort chunks so that weak prerequisites and weaker topics appear first
            def chunk_priority_key(chunk: Dict[str, Any]):
                t = chunk.get("topic") or ""
                base_score = mastery_map.get(t, 0.20)
                if t in prereq_weak_set:
                    return base_score - 0.25  # elevate weak prerequisite chunks
                return base_score

            return sorted(chunks, key=chunk_priority_key)
        except Exception:
            return chunks

    def _determine_question_type(self, requested_type: Optional[str], chunk: Dict[str, Any], current_index: int) -> str:
        req_type = (requested_type or "mixed").lower()
        if req_type in ("mcq", "short_answer", "numerical"):
            return req_type

        # Mixed mode distribution:
        # If chunk contains formula or mathematical calculations, offer numerical
        content_lower = chunk.get("content", "").lower()
        if any(kw in content_lower for kw in ["formula", "equation", "calculate", "z =", "loss =", "ratio", "rate"]):
            if current_index % 3 == 1:
                return "numerical"

        if current_index % 3 == 2:
            return "short_answer"
        return "mcq"

    def _generate_single_question_with_validation(
        self,
        chunk: Dict[str, Any],
        citation: Citation,
        q_type: str,
        difficulty: str,
        delivered_fingerprints: Set[str],
        delivered_prompts: List[str],
        seen_in_this_assessment: Set[str],
        allow_revision: bool,
        max_attempts: int = 2
    ) -> Optional[AssessmentQuestion]:
        topic = citation.topic or "Course Fundamentals"
        concept = citation.concept or "Core Concept"

        for attempt in range(max_attempts):
            if gemini_service.is_configured():
                prompt_input = (
                    f"Source Passage from {citation.source_file} (Page {citation.page_number or 'N/A'}, Slide {citation.slide_number or 'N/A'}):\n"
                    f"\"\"\"{chunk.get('content', '')}\"\"\"\n\n"
                    f"Requirements:\n"
                    f"- Topic: {topic}\n"
                    f"- Concept: {concept}\n"
                    f"- Question Type: {q_type}\n"
                    f"- Difficulty Level: {difficulty}\n"
                    f"- Formulate 1 rigorous {q_type} question testing the passage.\n"
                    f"- For MCQ, provide exactly 4 options: A), B), C), D) and specify the exact correct answer matching one option.\n"
                    f"- For numerical, state expected numerical value and tolerance.\n"
                    f"- For short_answer, provide concise expected answer and rubric points.\n"
                )
                try:
                    raw_res = gemini_service.generate_text(
                        prompt=prompt_input,
                        system_instruction=ASSESSMENT_GEN_SYSTEM_PROMPT,
                        json_schema=GeneratedQuestionLLMResponse
                    )
                    data = self._parse_and_validate_llm_question(raw_res, q_type)
                except GeminiQuotaExceededError:
                    raise
                except Exception as e:
                    if is_gemini_quota_error(e):
                        delay_sec, human = extract_gemini_retry_delay(e)
                        friendly = get_friendly_quota_message(e, retry_after_human=human)
                        raise GeminiQuotaExceededError(
                            message=friendly,
                            retry_delay_seconds=delay_sec,
                            retry_after_human=human,
                            original_error=e
                        )
                    sanitized_msg = sanitize_error(e)
                    logger.error(f"Live Gemini question generation error on attempt {attempt+1}: {sanitized_msg}")
                    # Rule 7: Do not silently fake simulated response in live mode!
                    raise RuntimeError(f"Live Gemini assessment question generation failed: {sanitized_msg}")
            else:
                # Explicit offline deterministic generator
                data = self._generate_offline_question(citation, q_type, attempt)

            if not data:
                continue

            # Server-Side Validation (Task B)
            is_valid, reason = self.validate_question(data, q_type)
            if not is_valid:
                logger.warning(f"Question validation failed ({q_type}): {reason}. Retrying...")
                continue

            # Duplicate Check (Task C)
            prompt_text = data["prompt"]
            fp = compute_question_fingerprint(prompt_text, topic)

            if not allow_revision:
                if fp in delivered_fingerprints or fp in seen_in_this_assessment:
                    logger.info(f"Duplicate fingerprint detected for user. Retrying...")
                    continue
                if self.is_duplicate_prompt(prompt_text, delivered_prompts):
                    logger.info(f"Semantic/lexical duplicate detected for user. Retrying...")
                    continue

            # Construct validated AssessmentQuestion
            q_id = str(uuid.uuid4())
            return AssessmentQuestion(
                id=q_id,
                topic_name=topic,
                concept=concept,
                question_type=q_type,
                prompt=prompt_text,
                options=data.get("options"),
                correct_answer=data["correct_answer"],
                explanation=data["explanation"],
                citation=citation,
                difficulty=data.get("difficulty", difficulty),
                numerical_tolerance=data.get("numerical_tolerance", 0.01 if q_type == "numerical" else None),
                numerical_unit=data.get("numerical_unit"),
                rubric=data.get("rubric"),
                fingerprint=fp
            )

        return None

    def _parse_and_validate_llm_question(self, raw_text: str, q_type: str) -> Optional[Dict[str, Any]]:
        cleaned = raw_text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            if isinstance(data, dict):
                data["question_type"] = q_type
                if "rubric_concepts" in data and "rubric" not in data:
                    data["rubric"] = {"key_concepts": data.get("rubric_concepts") or []}
                return data
        except Exception:
            pass
        return None

    def _generate_offline_question(self, citation: Citation, q_type: str, attempt: int) -> Dict[str, Any]:
        topic = citation.topic or "Course Fundamentals"
        suffix = f" (Variant {attempt+1})" if attempt > 0 else ""

        if q_type == "mcq":
            return {
                "prompt": f"Based on the course materials on {topic}, which of the following is correct{suffix}?",
                "options": [
                    f"A) The primary principle applies under baseline conditions outlined in {citation.source_file}",
                    "B) The relationship is inversely proportional to dataset variance",
                    "C) The method requires exponential computational overhead without benefit",
                    "D) The concept is not supported by empirical findings"
                ],
                "correct_answer": f"A) The primary principle applies under baseline conditions outlined in {citation.source_file}",
                "explanation": f"According to {citation.source_file}, baseline conditions govern the primary relationship.",
                "difficulty": "intermediate"
            }
        elif q_type == "numerical":
            return {
                "prompt": f"Given the parameters discussed in {topic}, compute the baseline ratio (rounded to 1 decimal place){suffix}.",
                "options": None,
                "correct_answer": "1.5",
                "explanation": f"Directly derived from the formulas in {citation.source_file}.",
                "difficulty": "intermediate",
                "numerical_tolerance": 0.05
            }
        else:
            return {
                "prompt": f"Briefly explain the primary function of the mechanism detailed in {citation.source_file}{suffix}.",
                "options": None,
                "correct_answer": "Standardizing feature representations to stabilize learning",
                "explanation": f"Section {citation.page_number or citation.slide_number or 1} specifies standardization as the core objective.",
                "difficulty": "intermediate",
                "rubric": {"key_concepts": ["standardizing", "stabilize", "representation"]}
            }

    # ==========================================================================
    # TASK B: Server-Side Question Validation
    # ==========================================================================
    def validate_question(self, q_data: Dict[str, Any], q_type: str) -> Tuple[bool, Optional[str]]:
        if not isinstance(q_data, dict):
            return False, "Question data must be a dictionary."

        prompt = q_data.get("prompt")
        if not prompt or not isinstance(prompt, str) or len(prompt.strip()) < 10:
            return False, "Prompt is missing, blank, or too brief."

        correct_ans = q_data.get("correct_answer")
        if correct_ans is None or not str(correct_ans).strip():
            return False, "Correct answer key is missing or blank."

        if q_type == "mcq":
            return self.validate_mcq(q_data)
        elif q_type == "numerical":
            return self.validate_numerical_question(q_data)
        elif q_type == "short_answer":
            return self.validate_short_answer_question(q_data)
        return True, None

    def validate_mcq(self, q_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Server-side validation for MCQs:
        - Must have at least 2 options.
        - Options must be non-empty strings.
        - No duplicate options.
        - Exactly one option matches the correct answer.
        """
        options = q_data.get("options")
        if not isinstance(options, list) or len(options) < 2:
            return False, f"MCQ must have at least 2 options; found {len(options) if isinstance(options, list) else 0}."

        cleaned_options = [str(opt).strip() for opt in options if opt is not None and str(opt).strip()]
        if len(cleaned_options) < 2:
            return False, "MCQ options contain fewer than 2 valid strings."

        lower_options = [opt.lower() for opt in cleaned_options]
        if len(set(lower_options)) != len(cleaned_options):
            return False, "MCQ contains duplicate options."

        stripped_options = [
            re.sub(r'^[a-zA-Z][\)\.\:\s]+\s*', '', opt).strip().lower()
            for opt in cleaned_options
        ]
        if len(set(stripped_options)) != len(cleaned_options):
            return False, "MCQ contains duplicate option content."

        correct_ans = str(q_data.get("correct_answer", "")).strip()
        c_lower = correct_ans.lower()

        # 1. Exact match with an option
        exact_matches = [i for i, opt in enumerate(lower_options) if opt == c_lower]
        if len(exact_matches) == 1:
            return True, None
        elif len(exact_matches) > 1:
            return False, "Correct answer matches multiple options ambiguously."

        # 2. Letter identifier match e.g. 'A' or 'A)'
        c_id_match = re.match(r'^([a-zA-Z])(?:[\)\.\:\s]|$)', correct_ans)
        if c_id_match:
            c_letter = c_id_match.group(1).lower()
            letter_matches = []
            for i, opt in enumerate(cleaned_options):
                opt_id_match = re.match(r'^([a-zA-Z])(?:[\)\.\:\s]|$)', opt)
                if opt_id_match and opt_id_match.group(1).lower() == c_letter:
                    letter_matches.append(i)
                elif not opt_id_match and i == (ord(c_letter) - ord('a')):
                    letter_matches.append(i)
            if len(letter_matches) == 1:
                return True, None
            elif len(letter_matches) > 1:
                return False, "Correct answer letter identifier matches multiple options."

        # 3. Content match after stripping letter prefixes
        body_matches = []
        stripped_c = re.sub(r'^[a-zA-Z][\)\.\:\s]+\s*', '', correct_ans).strip().lower()
        for i, opt in enumerate(cleaned_options):
            stripped_opt = re.sub(r'^[a-zA-Z][\)\.\:\s]+\s*', '', opt).strip().lower()
            if stripped_opt and stripped_c and stripped_opt == stripped_c:
                body_matches.append(i)
        if len(body_matches) == 1:
            return True, None
        elif len(body_matches) > 1:
            return False, "Correct answer content matches multiple options ambiguously."

        return False, "Correct answer does not correspond to any available option."

    def is_valid_mcq(self, q_data: Dict[str, Any]) -> bool:
        return self.validate_mcq(q_data)[0]

    def validate_numerical_question(self, q_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate that numerical question defines a valid parseable target number."""
        ans = str(q_data.get("correct_answer", "")).strip()
        match = re.search(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', ans)
        if not match:
            return False, f"Numerical problem has no parseable numeric answer in '{ans}'."
        try:
            val = float(match.group(0))
            if math.isnan(val) or math.isinf(val):
                return False, "Numerical answer is NaN or Inf."
            return True, None
        except ValueError:
            return False, "Could not convert numerical answer to float."

    def validate_short_answer_question(self, q_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate short-answer question prompt and reference answer."""
        ans = str(q_data.get("correct_answer", "")).strip()
        if len(ans) < 3:
            return False, "Short answer key is too brief."
        return True, None

    # ==========================================================================
    # TASK C: Duplicate Detection
    # ==========================================================================
    def is_duplicate_prompt(self, prompt: str, delivered_prompts: List[str]) -> bool:
        """
        Detect question repetition across assessments using:
        - Exact normalized comparison
        - SequenceMatcher ratio threshold
        - Token set overlap
        """
        if not delivered_prompts:
            return False

        norm_p = normalize_text(prompt)
        tokens_p = set(norm_p.split())

        for prev_p in delivered_prompts:
            norm_prev = normalize_text(prev_p)
            if norm_p == norm_prev:
                return True

            # Lexical similarity ratio
            ratio = SequenceMatcher(None, norm_p, norm_prev).ratio()
            if ratio >= self.duplicate_similarity_threshold:
                return True

            # Mutual token overlap check
            tokens_prev = set(norm_prev.split())
            if tokens_p and tokens_prev:
                intersection = tokens_p.intersection(tokens_prev)
                jaccard = len(intersection) / len(tokens_p.union(tokens_prev))
                if jaccard >= 0.80:
                    return True

        return False

    # ==========================================================================
    # TASK D: Assessment Attempts & Grading Workflow
    # ==========================================================================
    def grade_and_diagnose(self, req: QuizSubmissionRequest) -> QuizSubmissionResponse:
        assessment = storage.get_assessment(req.assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {req.assessment_id} not found")

        questions = assessment.get("questions", [])
        answers_map = {a.question_id: a.student_answer.strip() for a in req.answers}

        # Idempotency check (Task D):
        # Prevent duplicate submissions from updating mastery repeatedly
        is_already_completed = assessment.get("status") == "completed"

        correct_count = 0
        total_earned_score = 0.0
        graded_questions: List[QuizGradedQuestion] = []
        topic_results: Dict[str, List[bool]] = {}
        topic_counts: Dict[str, Dict[str, int]] = {}
        misconceptions: List[MisconceptionItem] = []
        answers_to_store: List[Dict[str, Any]] = []
        weak_concepts_set: Set[str] = set()

        for q in questions:
            q_id = q.get("id") or q.get("question_id", "")
            stud_ans = answers_map.get(q_id, "")
            corr_ans = str(q.get("correct_answer", "")).strip()
            q_type = q.get("question_type", "mcq")
            t_name = q.get("topic_name", "General")
            concept = q.get("concept")

            # Evaluate correctness with grading method attribution
            is_corr, score, method, feedback = self.evaluate_student_answer(
                student_ans=stud_ans,
                correct_ans=corr_ans,
                q_type=q_type,
                options=q.get("options"),
                tolerance=q.get("numerical_tolerance", 0.01),
                rubric=q.get("rubric")
            )

            if is_corr:
                correct_count += 1
            total_earned_score += score

            # Topic tracking
            topic_results.setdefault(t_name, []).append(is_corr)
            topic_counts.setdefault(t_name, {"correct": 0, "total": 0})
            topic_counts[t_name]["total"] += 1
            if is_corr:
                topic_counts[t_name]["correct"] += 1
            elif concept:
                weak_concepts_set.add(concept)

            cit = Citation(**q["citation"])
            graded_questions.append(QuizGradedQuestion(
                question_id=q_id,
                prompt=q["prompt"],
                student_answer=stud_ans,
                correct_answer=corr_ans,
                is_correct=is_corr,
                explanation=q["explanation"],
                citation=cit,
                partial_score=score,
                grading_method=method,
                feedback=feedback
            ))

            answers_to_store.append({
                "assessment_id": req.assessment_id,
                "user_id": req.user_id,
                "question_id": q_id,
                "submitted_answer": stud_ans,
                "is_correct": is_corr,
                "score": score,
                "grading_method": method,
                "feedback": feedback
            })

            # Task F: Distinguish directly observed mistakes from inferred misconceptions
            if not is_corr and stud_ans:
                diag = self._diagnose_misconception_item(q["prompt"], stud_ans, corr_ans, cit)
                misconceptions.append(diag)

        overall_score = float(total_earned_score / len(questions)) if questions else 0.0

        # Update Bayesian Knowledge Tracing (BKT) learner model
        from app.services.learner.mastery_model import mastery_service
        mastery_updates: Dict[str, float] = {}

        if not is_already_completed:
            # Deterministic BKT mastery update
            for topic_name, results in topic_results.items():
                for r in results:
                    new_m = mastery_service.update_mastery(
                        user_id=req.user_id,
                        topic_name=topic_name,
                        is_correct=r,
                        assessment_id=req.assessment_id,
                        observed_score=overall_score
                    )
                    mastery_updates[topic_name] = new_m

            # Persist answer records
            storage.save_assessment_answers(answers_to_store)

            # Update assessment record
            completed_now = datetime.now(timezone.utc).isoformat()
            storage.update_assessment(
                assessment_id=req.assessment_id,
                score=round(overall_score, 3),
                status="completed",
                questions=questions,
                misconceptions=[m.model_dump() for m in misconceptions],
                completed_at=completed_now
            )
        else:
            # Idempotent re-submission: fetch current masteries without re-applying updates
            for t_name in topic_results.keys():
                existing_m = storage.get_topic_mastery(req.user_id, t_name)
                mastery_updates[t_name] = existing_m["mastery_score"] if existing_m else 0.50

        # Topic Performance Breakdown (Task F)
        topic_perf: Dict[str, Dict[str, Any]] = {}
        for t_name, counts in topic_counts.items():
            topic_perf[t_name] = {
                "correct": counts["correct"],
                "total": counts["total"],
                "percentage": round(counts["correct"] / counts["total"], 2) if counts["total"] > 0 else 0.0,
                "current_mastery": mastery_updates.get(t_name, 0.5)
            }

        # Recommendations
        recommended_next_steps = []
        if overall_score < 0.6:
            recommended_next_steps.append("Schedule a diagnostic review session focusing on foundational topics.")
            for m in misconceptions[:2]:
                recommended_next_steps.append(f"Review {m.topic_name}: {m.remediation_advice}")
        else:
            recommended_next_steps.append("Demonstrated high conceptual mastery! Ready to advance to challenge sets.")
            recommended_next_steps.append("Try synthesizing multiple source texts in the Grounded AI Tutor.")

        return QuizSubmissionResponse(
            assessment_id=req.assessment_id,
            score=round(overall_score, 3),
            total_questions=len(questions),
            correct_count=correct_count,
            graded_questions=graded_questions,
            mastery_updates=mastery_updates,
            misconceptions=misconceptions,
            recommended_next_steps=recommended_next_steps,
            topic_performance=topic_perf,
            weak_concepts=list(weak_concepts_set),
            completed_at=datetime.now(timezone.utc)
        )

    # ==========================================================================
    # Answer Evaluation (MCQ, Numerical, Short Answer)
    # ==========================================================================
    def evaluate_student_answer(
        self,
        student_ans: Optional[str],
        correct_ans: Optional[str],
        q_type: str,
        options: Optional[List[str]] = None,
        tolerance: float = 0.01,
        rubric: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, float, str, str]:
        """
        Evaluates student answer returning (is_correct, score, grading_method, feedback).
        """
        if student_ans is None or not str(student_ans).strip():
            return False, 0.0, "blank", "No answer provided."
        if correct_ans is None or not str(correct_ans).strip():
            return False, 0.0, "error", "Missing correct answer key."

        s_clean = str(student_ans).strip()
        c_clean = str(correct_ans).strip()

        # Direct exact match check
        if s_clean.lower() == c_clean.lower():
            return True, 1.0, "exact", "Exact match with correct answer."

        if q_type == "mcq":
            is_corr = self._evaluate_mcq(s_clean, c_clean, options)
            feedback = "Correct option selected." if is_corr else f"Incorrect. Correct answer is '{c_clean}'."
            return is_corr, (1.0 if is_corr else 0.0), "exact", feedback

        elif q_type == "numerical":
            is_corr, diff, allowed = self._evaluate_numerical_details(s_clean, c_clean, tolerance)
            if is_corr:
                feedback = f"Numerically correct within tolerance (delta: {diff:.4f} <= ±{allowed:.4f})."
            else:
                feedback = f"Numerical deviation exceeds allowed tolerance (delta: {diff:.4f} > ±{allowed:.4f}). Expected: {c_clean}."
            return is_corr, (1.0 if is_corr else 0.0), "tolerance", feedback

        else:
            # Short answer evaluation (distinguishing exact vs semantic)
            is_corr, score, method, feedback = self._evaluate_short_answer_robust(s_clean, c_clean, rubric)
            return is_corr, score, method, feedback

    def is_answer_correct(
        self,
        student_ans: Optional[str],
        correct_ans: Optional[str],
        q_type: str,
        options: Optional[List[str]] = None,
        tolerance: float = 0.01
    ) -> bool:
        """Backward-compatible helper returning boolean correctness."""
        is_corr, _, _, _ = self.evaluate_student_answer(
            student_ans=student_ans,
            correct_ans=correct_ans,
            q_type=q_type,
            options=options,
            tolerance=tolerance
        )
        return is_corr

    def _evaluate_mcq(self, student_ans: str, correct_ans: str, options: Optional[List[str]] = None) -> bool:
        s_lower = student_ans.lower().strip()
        c_lower = correct_ans.lower().strip()

        if s_lower == c_lower:
            return True

        def get_identifier(text: str) -> Optional[str]:
            t = text.strip()
            if len(t) == 1 and t.isalpha():
                return t.lower()
            m = re.match(r'^([a-zA-Z])(?:[\)\.\:\s]|$)', t)
            if m:
                return m.group(1).lower()
            return None

        s_id = get_identifier(student_ans)
        c_id = get_identifier(correct_ans)

        # If both provide option letter identifiers (e.g. 'A' vs 'A)'), compare directly
        if s_id and c_id:
            return s_id == c_id

        # If options list provided, resolve student answer to option index
        if options:
            cleaned_options = [opt.strip() for opt in options if opt]
            s_idx = None
            c_idx = None

            for i, opt in enumerate(cleaned_options):
                opt_lower = opt.lower()
                opt_id = get_identifier(opt)

                if s_id and opt_id == s_id:
                    s_idx = i
                elif s_lower == opt_lower:
                    s_idx = i
                elif opt_id:
                    stripped_opt = re.sub(r'^[a-zA-Z][\)\.\:\s]+\s*', '', opt).strip().lower()
                    if s_lower == stripped_opt:
                        s_idx = i

                if c_id and opt_id == c_id:
                    c_idx = i
                elif c_lower == opt_lower:
                    c_idx = i
                elif opt_id:
                    stripped_opt = re.sub(r'^[a-zA-Z][\)\.\:\s]+\s*', '', opt).strip().lower()
                    if c_lower == stripped_opt:
                        c_idx = i

            if s_idx is not None and c_idx is not None:
                return s_idx == c_idx

        # Check content match with prefix stripped
        stripped_s = re.sub(r'^[a-zA-Z][\)\.\:\s]+\s*', '', student_ans).strip().lower()
        stripped_c = re.sub(r'^[a-zA-Z][\)\.\:\s]+\s*', '', correct_ans).strip().lower()
        if stripped_s and stripped_c and stripped_s == stripped_c:
            return True

        return False

    def _evaluate_numerical_details(
        self,
        student_ans: str,
        correct_ans: str,
        tolerance: float = 0.01
    ) -> Tuple[bool, float, float]:
        def extract_num(text: str) -> Optional[float]:
            match = re.search(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', text.strip())
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return None
            return None

        val_s = extract_num(student_ans)
        val_c = extract_num(correct_ans)
        if val_s is None or val_c is None:
            return False, float('inf'), tolerance

        abs_diff = abs(val_s - val_c)
        allowed_tol = max(tolerance, abs(val_c) * 0.05)  # allow max of absolute tolerance or 5% relative
        return abs_diff <= allowed_tol, abs_diff, allowed_tol

    def _evaluate_numerical(self, student_ans: str, correct_ans: str, tolerance: float = 0.01) -> bool:
        is_corr, _, _ = self._evaluate_numerical_details(student_ans, correct_ans, tolerance)
        return is_corr

    def _evaluate_short_answer_robust(
        self,
        student_ans: str,
        correct_ans: str,
        rubric: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, float, str, str]:
        """
        Evaluate short answer distinguishing exact matching from semantic grading.
        Rejects arbitrary substring matching.
        """
        s_norm = normalize_text(student_ans)
        c_norm = normalize_text(correct_ans)

        if not s_norm or not c_norm:
            return False, 0.0, "blank", "Response or answer key is blank."

        # 1. Exact match
        if s_norm == c_norm:
            return True, 1.0, "exact", "Exact match with reference answer."

        # 2. SequenceMatcher ratio for minor phrasing differences
        seq_ratio = SequenceMatcher(None, s_norm, c_norm).ratio()
        if seq_ratio >= 0.88:
            return True, 1.0, "semantic_lexical", f"High semantic similarity match ({seq_ratio*100:.1f}%)."

        # 3. Token set overlap (require mutual precision & recall >= 85%)
        s_tokens = set(s_norm.split())
        c_tokens = set(c_norm.split())
        if s_tokens and c_tokens:
            intersection = s_tokens.intersection(c_tokens)
            precision = len(intersection) / len(s_tokens)
            recall = len(intersection) / len(c_tokens)
            if precision >= 0.85 and recall >= 0.85:
                return True, 1.0, "semantic_lexical", "Response covers required key concepts."

        # 4. Rubric key concept coverage
        if rubric and "key_concepts" in rubric:
            required = [normalize_text(k) for k in rubric["key_concepts"]]
            matched = [k for k in required if k in s_norm]
            coverage = len(matched) / len(required) if required else 0.0
            if coverage >= 0.75:
                return True, round(coverage, 2), "rubric", f"Rubric concept coverage: {len(matched)}/{len(required)} key concepts verified."

        # 5. Live Gemini Semantic Grading (when available and not in quota cooldown)
        if gemini_service.is_configured() and not gemini_service.is_quota_exhausted():
            try:
                eval_prompt = (
                    f"Question Reference Answer: \"{correct_ans}\"\n"
                    f"Student Response: \"{student_ans}\"\n"
                    f"Rubric: {json.dumps(rubric or {})}\n\n"
                    f"Evaluate if the student response conveys the accurate educational concept. "
                    f"Grade strictly: do not award points for unrelated keywords."
                )
                raw_eval = gemini_service.generate_text(
                    prompt=eval_prompt,
                    system_instruction="You are a strict academic evaluator. Output JSON with is_acceptable (bool), score (float 0..1), feedback (str).",
                    json_schema=ShortAnswerEvaluationLLMResponse
                )
                eval_data = json.loads(raw_eval)
                is_acc = bool(eval_data.get("is_acceptable", False))
                ev_score = float(eval_data.get("score", 0.0))
                fb = eval_data.get("feedback", "Semantic evaluation completed.")
                return is_acc, ev_score, "semantic", fb
            except GeminiQuotaExceededError:
                logger.warning("Gemini quota exhausted during short answer semantic grading. Falling back to lexical.")
            except Exception as e:
                if is_gemini_quota_error(e):
                    logger.warning("Gemini quota exhausted during short answer semantic grading. Falling back to lexical.")
                else:
                    logger.warning(f"Live semantic grading fallback to lexical: {sanitize_error(e)}")

        # Strict rejection of arbitrary substring matching
        return False, 0.0, "semantic", f"Response did not adequately demonstrate key concepts. Expected: '{correct_ans}'."

    def _evaluate_short_answer(self, student_ans: str, correct_ans: str) -> bool:
        is_corr, _, _, _ = self._evaluate_short_answer_robust(student_ans, correct_ans)
        return is_corr

    # ==========================================================================
    # TASK F: Misconception Diagnosis
    # ==========================================================================
    def _diagnose_misconception_item(
        self,
        prompt: str,
        student_ans: str,
        correct_ans: str,
        cit: Citation
    ) -> MisconceptionItem:
        # Directly observed mistake (Task F requirement)
        observed = f"Selected '{student_ans}' instead of expected '{correct_ans}'."

        diag_prompt = (
            f"Question: {prompt}\n"
            f"Observed Student Error: {student_ans}\n"
            f"Correct Academic Fact: {correct_ans}\n"
            f"Source Topic: {cit.topic}\n\n"
            f"Diagnose the underlying conceptual confusion that led to this mistake. "
            f"Provide 1 sentence of actionable remediation advice referencing the material."
        )

        try:
            diag_res = gemini_service.generate_text(diag_prompt)
            lines = [l.strip() for l in diag_res.splitlines() if l.strip()]
            misconception_text = lines[0] if lines else f"Misunderstood core definition of {cit.topic}."
            advice_text = lines[1] if len(lines) > 1 else f"Review page {cit.page_number or cit.slide_number or 1} of {cit.source_file}."
        except Exception:
            misconception_text = f"Confusion between core principles and application in {cit.topic}."
            advice_text = f"Carefully re-read source excerpt in {cit.source_file}."

        return MisconceptionItem(
            topic_name=cit.topic or "Topic Concept",
            misconception=misconception_text,
            remediation_advice=advice_text,
            recommended_reading=cit,
            observed_mistake=observed
        )

# Global singleton
assessment_service = AssessmentService()
