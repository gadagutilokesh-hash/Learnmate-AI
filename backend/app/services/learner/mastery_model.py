import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
from datetime import datetime, timezone, timedelta

from app.db.storage import storage as default_storage
storage = default_storage
from app.core.config import settings
from app.models.schema import (
    TopicMastery, LearnerProfileResponse, MasteryHistoryRecord,
    RecommendedActivity, StudyPlanItem, StudyPlanRequest, StudyPlanResponse,
    Citation
)

logger = logging.getLogger(__name__)

from collections import namedtuple

_BaseSchedule = namedtuple("_BaseSchedule", ["review_interval_days", "consecutive_correct", "next_review_at"])

class SpacedSchedule(_BaseSchedule):
    def __getitem__(self, item):
        if isinstance(item, str):
            if item == "review_interval_days":
                return self.review_interval_days
            if item == "consecutive_correct":
                return self.consecutive_correct
            if item == "next_review_at":
                return self.next_review_at
            raise KeyError(item)
        return super().__getitem__(item)

class BayesianKnowledgeTracingService:
    """
    Deterministic Bayesian Knowledge Tracing (BKT) and Advanced Personalization Engine.

    Mathematical Formulation:
      P(L_t | Correct)   = (P(L_{t-1}) * (1 - S)) / (P(L_{t-1}) * (1 - S) + (1 - P(L_{t-1})) * G)
      P(L_t | Incorrect) = (P(L_{t-1}) * S)       / (P(L_{t-1}) * S       + (1 - P(L_{t-1})) * (1 - G))
      P(L_{t+1})         = P(L_t | Obs) + (1 - P(L_t | Obs)) * T

    Parameters:
      P(L_0): Prior mastery probability
      P(T):   Learning transition probability
      P(G):   Guess probability
      P(S):   Slip probability
    """
    def __init__(
        self,
        default_prior: Optional[float] = None,
        default_transit: Optional[float] = None,
        default_guess: Optional[float] = None,
        default_slip: Optional[float] = None,
        default_review_interval: Optional[float] = None,
        max_review_interval: Optional[float] = None,
        storage: Optional[Any] = None,
        prior: Optional[float] = None,
        transit: Optional[float] = None,
        guess: Optional[float] = None,
        slip: Optional[float] = None
    ):
        p_prior = prior if prior is not None else default_prior
        p_transit = transit if transit is not None else default_transit
        p_guess = guess if guess is not None else default_guess
        p_slip = slip if slip is not None else default_slip

        self.default_prior = p_prior if p_prior is not None else getattr(settings, "BKT_DEFAULT_PRIOR", 0.15)
        self.default_transit = p_transit if p_transit is not None else getattr(settings, "BKT_DEFAULT_TRANSIT", 0.15)
        self.default_guess = p_guess if p_guess is not None else getattr(settings, "BKT_DEFAULT_GUESS", 0.20)
        self.default_slip = p_slip if p_slip is not None else getattr(settings, "BKT_DEFAULT_SLIP", 0.10)
        self.default_review_interval = default_review_interval if default_review_interval is not None else getattr(settings, "SPACED_REPETITION_DEFAULT_INTERVAL_DAYS", 1.0)
        self.max_review_interval = max_review_interval if max_review_interval is not None else getattr(settings, "SPACED_REPETITION_MAX_INTERVAL_DAYS", 30.0)
        self._storage = storage

    @property
    def storage(self):
        return self._storage if self._storage is not None else globals().get("storage", default_storage)

    # ==========================================================================
    # TASK B & D: Persistent Mastery & Spaced Repetition Scheduling
    # ==========================================================================
    def calculate_spaced_repetition_schedule(
        self,
        current_interval: float,
        mastery_score: float,
        is_correct: bool,
        current_streak: int = 0,
        consecutive_streak: Optional[int] = None
    ) -> SpacedSchedule:
        """
        Computes the updated review interval (days), streak, and ISO timestamp for next review.
        """
        streak = consecutive_streak if consecutive_streak is not None else current_streak
        now = datetime.now(timezone.utc)
        if is_correct:
            new_streak = streak + 1
            if mastery_score >= 0.85:
                multiplier = 2.5
            elif mastery_score >= 0.70:
                multiplier = 1.8
            elif mastery_score >= 0.50:
                multiplier = 1.4
            else:
                multiplier = 1.1

            new_interval = min(self.max_review_interval, max(self.default_review_interval, current_interval * multiplier))
        else:
            new_streak = 0
            new_interval = self.default_review_interval

        next_review_dt = now + timedelta(days=new_interval)
        return SpacedSchedule(round(new_interval, 2), new_streak, next_review_dt.isoformat())

    def update_mastery(
        self,
        user_id: str,
        topic_name: str,
        is_correct: bool,
        transit: Optional[float] = None,
        guess: Optional[float] = None,
        slip: Optional[float] = None,
        prior: Optional[float] = None,
        assessment_id: Optional[str] = None,
        observed_score: Optional[float] = None
    ) -> float:
        """
        Updates topic mastery using Bayesian Knowledge Tracing with persistent audit history
        and spaced repetition revision scheduling.
        """
        T = transit if transit is not None else self.default_transit
        G = guess if guess is not None else self.default_guess
        S = slip if slip is not None else self.default_slip
        L0 = prior if prior is not None else self.default_prior

        existing = self.storage.get_topic_mastery(user_id, topic_name)
        if existing:
            prior_L = existing["mastery_score"]
            curr_interval = existing.get("review_interval_days") or self.default_review_interval
            curr_streak = existing.get("consecutive_correct") or 0
        else:
            prior_L = L0
            curr_interval = self.default_review_interval
            curr_streak = 0

        # Compute posterior given evidence
        if is_correct:
            numerator = prior_L * (1.0 - S)
            denominator = numerator + (1.0 - prior_L) * G
        else:
            numerator = prior_L * S
            denominator = numerator + (1.0 - prior_L) * (1.0 - G)

        denominator = max(1e-6, denominator)
        posterior = numerator / denominator

        # Transition to next latent knowledge state
        updated_L = posterior + (1.0 - posterior) * T
        updated_L = max(0.01, min(0.99, updated_L))

        # Compute transparent Spaced Repetition schedule
        new_interval, new_streak, next_review_at = self.calculate_spaced_repetition_schedule(
            current_interval=curr_interval,
            mastery_score=updated_L,
            is_correct=is_correct,
            current_streak=curr_streak
        )

        self.storage.save_topic_mastery(
            user_id=user_id,
            topic_name=topic_name,
            mastery_score=round(updated_L, 4),
            p_transit=T,
            p_guess=G,
            p_slip=S,
            attempts_delta=1,
            correct_delta=1 if is_correct else 0,
            assessment_id=assessment_id,
            is_correct=is_correct,
            observed_score=observed_score if observed_score is not None else (1.0 if is_correct else 0.0),
            next_review_at=next_review_at,
            review_interval_days=new_interval,
            consecutive_correct=new_streak,
            repetition_count_delta=1 if is_correct else 0
        )
        return round(updated_L, 4)

    # ==========================================================================
    # TASK B, C, D: Profile, History & Recommendations
    # ==========================================================================
    def get_learner_profile(self, user_id: str = "student_default", course_id: Optional[str] = None) -> LearnerProfileResponse:
        records = self.storage.list_topic_masteries(user_id)
        now = datetime.now(timezone.utc)

        # Handle brand new learners without assuming existing mastery (Task B & G)
        if not records:
            curriculum_topics = self.storage.get_all_topics(course_id)
            if not curriculum_topics:
                curriculum_topics = ["Supervised Learning", "Linear Regression", "Gradient Descent", "Neural Networks", "Optimization"]

            unassessed_models: List[TopicMastery] = []
            for t in curriculum_topics:
                unassessed_models.append(TopicMastery(
                    topic_name=t,
                    mastery_score=0.0,
                    p_transit=self.default_transit,
                    p_guess=self.default_guess,
                    p_slip=self.default_slip,
                    attempts_count=0,
                    correct_count=0,
                    status="unassessed",
                    is_overdue=False,
                    overdue_reason=None
                ))

            # Initial diagnostic recommendation
            diagnostic_activity = RecommendedActivity(
                id=str(uuid.uuid4()),
                type="diagnostic_review",
                priority="urgent",
                title="Initialize Diagnostic Assessment",
                description="Complete an initial 5-question multi-topic assessment to calibrate your personalized learning model.",
                action="quiz",
                topic=curriculum_topics[0] if curriculum_topics else "General",
                reason="Calibrate Bayesian Knowledge Tracing baseline across foundational concepts."
            )

            provisional_plan = self.generate_study_plan(StudyPlanRequest(user_id=user_id, course_id=course_id, daily_study_minutes=30))

            return LearnerProfileResponse(
                user_id=user_id,
                name="Learner",
                overall_mastery=0.0,
                is_new_learner=True,
                topics=unassessed_models,
                weak_topics=[],
                strong_topics=[],
                upcoming_reviews=[],
                recent_assessments=[],
                history=[],
                recommended_activities=[diagnostic_activity],
                study_plan=provisional_plan
            )

        # Process active learner profile
        topic_models: List[TopicMastery] = []
        weak: List[str] = []
        strong: List[str] = []
        upcoming_reviews: List[TopicMastery] = []
        total_score = 0.0

        for r in records:
            score = r["mastery_score"]
            total_score += score
            status = "mastered" if score >= 0.75 else ("in_progress" if score >= 0.45 else "needs_practice")
            if score < 0.50:
                weak.append(r["topic_name"])
            elif score >= 0.75:
                strong.append(r["topic_name"])

            # Check Spaced Repetition overdue status (Task D)
            is_overdue = False
            days_overdue = 0.0
            overdue_reason = None
            next_rev_str = r.get("next_review_at")
            if next_rev_str:
                try:
                    rev_dt = datetime.fromisoformat(next_rev_str)
                    if rev_dt.tzinfo is None:
                        rev_dt = rev_dt.replace(tzinfo=timezone.utc)
                    if now >= rev_dt:
                        is_overdue = True
                        days_overdue = round((now - rev_dt).total_seconds() / 86400.0, 2)
                        if score < 0.50:
                            overdue_reason = f"Overdue for review with mastery at {int(score*100)}%. Immediate reinforcement recommended to prevent memory decay."
                        else:
                            overdue_reason = f"Retention maintenance: scheduled review to solidify long-term recall."
                except Exception:
                    pass

            tm = TopicMastery(
                topic_name=r["topic_name"],
                mastery_score=score,
                p_transit=r["p_transit"],
                p_guess=r["p_guess"],
                p_slip=r["p_slip"],
                attempts_count=r["attempts_count"],
                correct_count=r["correct_count"],
                status=status,
                last_attempt_at=r.get("last_attempt_at"),
                next_review_at=r.get("next_review_at"),
                review_interval_days=r.get("review_interval_days", 1.0),
                consecutive_correct=r.get("consecutive_correct", 0),
                repetition_count=r.get("repetition_count", 0),
                is_overdue=is_overdue,
                days_overdue=days_overdue,
                overdue_reason=overdue_reason
            )
            topic_models.append(tm)
            if r.get("next_review_at"):
                upcoming_reviews.append(tm)

        overall = total_score / len(records) if records else 0.0

        # Sort upcoming reviews chronologically
        upcoming_reviews.sort(key=lambda t: t.next_review_at or "")

        recent_assessments = self.storage.list_assessments(user_id, limit=5)
        raw_history = self.storage.list_mastery_history(user_id, limit=25)
        history_models = [MasteryHistoryRecord(**h) for h in raw_history]

        # Build personalized recommendations with genuine citations and prerequisites (Task C)
        activities = self._build_personalized_recommendations(weak, strong, records, course_id)

        # Generate personalized study plan (Task F)
        study_plan = self.generate_study_plan(StudyPlanRequest(user_id=user_id, course_id=course_id, daily_study_minutes=30))

        return LearnerProfileResponse(
            user_id=user_id,
            name="Learner",
            overall_mastery=round(overall, 3),
            is_new_learner=False,
            topics=topic_models,
            weak_topics=weak,
            strong_topics=strong,
            upcoming_reviews=upcoming_reviews,
            recent_assessments=recent_assessments,
            history=history_models,
            recommended_activities=activities,
            study_plan=study_plan
        )

    def _build_personalized_recommendations(
        self,
        weak_topics: List[str],
        strong_topics: List[str],
        records: List[Dict[str, Any]],
        course_id: Optional[str] = None
    ) -> List[RecommendedActivity]:
        """
        Builds personalized recommendations incorporating:
        - Current topic mastery
        - Prerequisite relationships
        - Genuine source citations
        - Spaced repetition overdue status
        """
        recs: List[RecommendedActivity] = []
        chunks = self.storage.get_chunks_for_course(course_id) if course_id else []
        if not chunks:
            # Fallback to all chunks
            chunks = self.storage.get_all_chunks()

        # Build quick topic -> chunk citation lookup
        chunk_by_topic: Dict[str, Dict[str, Any]] = {}
        for c in chunks:
            top = (c.get("topic") or "").strip().lower()
            if top and top not in chunk_by_topic:
                chunk_by_topic[top] = c

        now = datetime.now(timezone.utc)

        # 1. Check Prerequisite relationships for weak topics
        mastery_map = {r["topic_name"]: r["mastery_score"] for r in records}
        all_prereqs = self.storage.get_topic_prerequisites(course_id=course_id)
        for w in weak_topics:
            prereqs = self.storage.get_topic_prerequisites(course_id=course_id, topic_name=w)
            for p in prereqs:
                p_name = p["prerequisite_topic"]
                p_mastery = mastery_map.get(p_name, 0.0)
                if p_mastery < 0.50:
                    cit = self._make_citation_for_topic(p_name, chunk_by_topic)
                    recs.append(RecommendedActivity(
                        id=str(uuid.uuid4()),
                        type="prerequisite_study",
                        priority="urgent",
                        title=f"Strengthen Prerequisite: {p_name}",
                        description=f"{w} builds directly on foundational concepts in {p_name}. Solidifying this prerequisite will resolve comprehension roadblocks.",
                        action="tutor",
                        topic=p_name,
                        reason=f"Prerequisite for target topic {w} (current mastery: {int(p_mastery*100)}%).",
                        citation=cit,
                        source_citation=cit
                    ))

            # Also check if w itself is a prerequisite for downstream topics
            downstream = [p["topic_name"] for p in all_prereqs if p.get("prerequisite_topic", "").lower() == w.lower()]
            if downstream:
                cit = self._make_citation_for_topic(w, chunk_by_topic)
                recs.append(RecommendedActivity(
                    id=str(uuid.uuid4()),
                    type="prerequisite_study",
                    priority="urgent",
                    title=f"Core Prerequisite: {w}",
                    description=f"{w} is an essential prerequisite required for downstream topics ({', '.join(downstream[:2])}). Solidifying {w} unlocks higher curriculum mastery.",
                    action="tutor",
                    topic=w,
                    reason=f"Foundational prerequisite required by downstream topic: {downstream[0]}.",
                    citation=cit,
                    source_citation=cit
                ))

        # 2. Check Spaced Repetition Overdue topics
        for r in records:
            next_rev_str = r.get("next_review_at")
            if next_rev_str:
                try:
                    rev_dt = datetime.fromisoformat(next_rev_str)
                    if rev_dt.tzinfo is None:
                        rev_dt = rev_dt.replace(tzinfo=timezone.utc)
                    if now >= rev_dt:
                        t_name = r["topic_name"]
                        cit = self._make_citation_for_topic(t_name, chunk_by_topic)
                        recs.append(RecommendedActivity(
                            id=str(uuid.uuid4()),
                            type="spaced_revision",
                            priority="high",
                            title=f"Spaced Review: {t_name}",
                            description=f"Scheduled review interval reached. Reinforcing this concept now maximizes long-term memory retention.",
                            action="quiz",
                            topic=t_name,
                            reason="Scheduled memory consolidation based on previous practice timeline.",
                            citation=cit,
                            source_citation=cit
                        ))
                except Exception:
                    pass

        # 3. Weak Topics Review & Practice
        for w in weak_topics[:3]:
            cit = self._make_citation_for_topic(w, chunk_by_topic)
            recs.append(RecommendedActivity(
                id=str(uuid.uuid4()),
                type="review_source",
                priority="high",
                title=f"Review Course Text: {w}",
                description=f"Mastery in {w} is below 50%. Consult the textbook/lecture excerpts before attempting another quiz.",
                action="tutor",
                topic=w,
                reason=f"Current BKT mastery is {int(mastery_map.get(w, 0.0)*100)}%.",
                citation=cit,
                source_citation=cit
            ))
            recs.append(RecommendedActivity(
                id=str(uuid.uuid4()),
                type="practice_quiz",
                priority="medium",
                title=f"Targeted Adaptive Quiz: {w}",
                description=f"Attempt a short quiz on {w} to convert newly reviewed concepts into measurable mastery.",
                action="quiz",
                topic=w,
                reason="Targeted retrieval practice to increase BKT mastery belief.",
                citation=cit,
                source_citation=cit
            ))

        # 4. Mastered Topics Advance to Challenges
        if strong_topics:
            s_top = strong_topics[0]
            cit = self._make_citation_for_topic(s_top, chunk_by_topic)
            recs.append(RecommendedActivity(
                id=str(uuid.uuid4()),
                type="challenge_assessment",
                priority="medium",
                title=f"Mastery Challenge: {s_top}",
                description=f"High conceptual mastery ({int(mastery_map.get(s_top, 0.8)*100)}%) attained. Advance to hard numerical and analytical synthesis problems.",
                action="quiz",
                topic=s_top,
                reason="Advancing to harder question difficulty to solidify mastery.",
                citation=cit,
                source_citation=cit
            ))

        # Deduplicate recommendations by topic and title
        seen_keys = set()
        unique_recs = []
        for r in recs:
            key = (r.topic.lower(), r.type)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_recs.append(r)

        return unique_recs[:6]

    def _make_citation_for_topic(self, topic_name: str, chunk_by_topic: Dict[str, Dict[str, Any]]) -> Optional[Citation]:
        top_lower = topic_name.strip().lower()
        chunk = chunk_by_topic.get(top_lower)
        if not chunk:
            for k, c in chunk_by_topic.items():
                if top_lower in k or k in top_lower:
                    chunk = c
                    break
        if not chunk:
            return None

        return Citation(
            source_file=chunk.get("filename", "Course Materials"),
            source_type=chunk.get("source_type", "pdf"),
            page_number=chunk.get("page_number"),
            slide_number=chunk.get("slide_number"),
            start_timestamp=chunk.get("start_timestamp"),
            end_timestamp=chunk.get("end_timestamp"),
            excerpt=chunk.get("content", "")[:280],
            topic=chunk.get("topic", topic_name),
            concept=chunk.get("concept")
        )

    # ==========================================================================
    # TASK F: Personalized Study Plan
    # ==========================================================================
    def generate_study_plan(self, req: StudyPlanRequest) -> StudyPlanResponse:
        """
        Generates a transparent, time-bounded study plan:
        - Bounded by daily study time (e.g. 30 min/day).
        - Sequences: Prerequisites -> Overdue Reviews -> Weak Topics -> Challenge Sets.
        - Provides provisional 14-day schedule if target exam date is unknown.
        """
        now = datetime.now(timezone.utc)
        daily_mins = max(15, min(180, req.daily_study_minutes))
        is_provisional = req.target_exam_date is None

        if req.target_exam_date:
            try:
                exam_dt = datetime.fromisoformat(req.target_exam_date.replace("Z", "+00:00"))
                if exam_dt.tzinfo is None:
                    exam_dt = exam_dt.replace(tzinfo=timezone.utc)
                total_days = max(1, min(60, (exam_dt - now).days))
            except Exception:
                total_days = 14
                is_provisional = True
        else:
            total_days = 14

        records = self.storage.list_topic_masteries(req.user_id)
        chunks = self.storage.get_chunks_for_course(req.course_id) if req.course_id else self.storage.get_all_chunks()
        chunk_by_topic: Dict[str, Dict[str, Any]] = {}
        for c in chunks:
            top = (c.get("topic") or "").strip().lower()
            if top and top not in chunk_by_topic:
                chunk_by_topic[top] = c

        weak_topics = [r["topic_name"] for r in records if r["mastery_score"] < 0.50]
        overdue_topics = []
        for r in records:
            if r.get("next_review_at"):
                try:
                    rev_dt = datetime.fromisoformat(r["next_review_at"])
                    if rev_dt.tzinfo is None:
                        rev_dt = rev_dt.replace(tzinfo=timezone.utc)
                    if now >= rev_dt:
                        overdue_topics.append(r["topic_name"])
                except Exception:
                    pass

        # Identify all distinct topics in curriculum
        all_topics = [r["topic_name"] for r in records]
        if not all_topics:
            all_topics = self.storage.get_all_topics(req.course_id) or ["Supervised Learning", "Linear Regression", "Gradient Descent", "Neural Networks", "Optimization"]

        items: List[StudyPlanItem] = []
        topic_cursor = 0

        for day_idx in range(1, total_days + 1):
            day_dt = now + timedelta(days=day_idx)
            date_str = day_dt.strftime("%Y-%m-%d")

            # Divide daily minutes into 2 structured study modules
            mod1_mins = int(daily_mins * 0.6)
            mod2_mins = daily_mins - mod1_mins

            # Select target topic for the day
            if overdue_topics and (day_idx % 2 == 1 or not weak_topics):
                chosen_topic = overdue_topics[(day_idx - 1) % len(overdue_topics)]
                act_type = "spaced_repetition"
                reason = "Consolidate memory retention based on spaced repetition schedule."
            elif weak_topics:
                chosen_topic = weak_topics[(day_idx - 1) % len(weak_topics)]
                # Check prerequisite
                prereqs = self.storage.get_topic_prerequisites(course_id=req.course_id, topic_name=chosen_topic)
                if prereqs and day_idx <= 3:
                    chosen_topic = prereqs[0]["prerequisite_topic"]
                    act_type = "prerequisite_foundations"
                    reason = f"Establish foundations for downstream topic."
                else:
                    act_type = "concept_review"
                    reason = f"Remediate weak concept with current mastery below 50%."
            else:
                chosen_topic = all_topics[topic_cursor % len(all_topics)]
                topic_cursor += 1
                act_type = "mastery_challenge"
                reason = "Curriculum synthesis and challenge question mastery."

            cit = self._make_citation_for_topic(chosen_topic, chunk_by_topic)

            # Module 1: Content exploration or source review
            items.append(StudyPlanItem(
                day_number=day_idx,
                day_offset=day_idx,
                date=date_str,
                suggested_date=date_str,
                topic_name=chosen_topic,
                topic=chosen_topic,
                title=f"{act_type.replace('_', ' ').title()}: {chosen_topic}",
                description=f"Deep review of {chosen_topic} core principles and formulation.",
                activity_type=act_type,
                suggested_duration_minutes=mod1_mins,
                reason=reason,
                citation=cit,
                source_citation=cit,
                priority="high" if act_type in ["prerequisite_foundations", "spaced_repetition"] else "normal"
            ))

            # Module 2: Active practice quiz testing the concept
            items.append(StudyPlanItem(
                day_number=day_idx,
                day_offset=day_idx,
                date=date_str,
                suggested_date=date_str,
                topic_name=chosen_topic,
                topic=chosen_topic,
                title=f"Practice Assessment: {chosen_topic}",
                description=f"Active recall questions calibrated to current knowledge belief.",
                activity_type="targeted_quiz",
                suggested_duration_minutes=mod2_mins,
                reason=f"Practice 3-5 questions on {chosen_topic} with immediate feedback.",
                citation=cit,
                source_citation=cit,
                priority="normal"
            ))

        total_study_hours = round((total_days * daily_mins) / 60.0, 1)
        notes = (
            f"{'Provisional 14-day study schedule' if is_provisional else f'Targeted exam preparation schedule ({total_days} days)'}. "
            f"Daily study budget: {daily_mins} minutes ({total_study_hours} total hours planned). "
            f"Prioritizes prerequisites, spaced repetition memory consolidation, and weak concept remediation."
        )

        prov_notice = "Provisional 14-day study schedule. Target exam date not specified." if is_provisional else None

        return StudyPlanResponse(
            user_id=req.user_id,
            is_provisional=is_provisional,
            target_exam_date=req.target_exam_date,
            daily_study_minutes=daily_mins,
            total_days=total_days,
            total_study_hours=total_study_hours,
            items=items,
            schedule=items,
            provisional_notice=prov_notice,
            weak_topics_addressed=list(set(weak_topics)),
            overdue_topics_scheduled=list(set(overdue_topics)),
            notes=notes
        )

mastery_service = BayesianKnowledgeTracingService()
