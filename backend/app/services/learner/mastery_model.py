import logging
from typing import List, Dict, Any, Optional
from app.db.storage import storage
from app.models.schema import TopicMastery, LearnerProfileResponse

logger = logging.getLogger(__name__)

class BayesianKnowledgeTracingService:
    """
    Deterministic Bayesian Knowledge Tracing (BKT) engine for topic mastery tracking.
    Formulation:
      P(L_t | Correct)   = (P(L_{t-1}) * (1 - S)) / (P(L_{t-1}) * (1 - S) + (1 - P(L_{t-1})) * G)
      P(L_t | Incorrect) = (P(L_{t-1}) * S)       / (P(L_{t-1}) * S       + (1 - P(L_{t-1})) * (1 - G))
      P(L_{t+1})         = P(L_t | Obs) + (1 - P(L_t | Obs)) * T
    """
    def __init__(self, default_transit: float = 0.15, default_guess: float = 0.20, default_slip: float = 0.10):
        self.default_transit = default_transit
        self.default_guess = default_guess
        self.default_slip = default_slip

    def update_mastery(
        self,
        user_id: str,
        topic_name: str,
        is_correct: bool,
        transit: Optional[float] = None,
        guess: Optional[float] = None,
        slip: Optional[float] = None
    ) -> float:
        T = transit or self.default_transit
        G = guess or self.default_guess
        S = slip or self.default_slip

        existing = storage.get_topic_mastery(user_id, topic_name)
        if existing:
            prior_L = existing["mastery_score"]
        else:
            prior_L = 0.15  # Default initial prior for new topic

        # Compute posterior given evidence
        if is_correct:
            numerator = prior_L * (1.0 - S)
            denominator = numerator + (1.0 - prior_L) * G
        else:
            numerator = prior_L * S
            denominator = numerator + (1.0 - prior_L) * (1.0 - G)

        denominator = max(1e-6, denominator)
        posterior = numerator / denominator

        # Transition to next state
        updated_L = posterior + (1.0 - posterior) * T
        updated_L = max(0.01, min(0.99, updated_L))

        storage.save_topic_mastery(
            user_id=user_id,
            topic_name=topic_name,
            mastery_score=round(updated_L, 4),
            p_transit=T,
            p_guess=G,
            p_slip=S,
            attempts_delta=1,
            correct_delta=1 if is_correct else 0
        )
        return round(updated_L, 4)

    def get_learner_profile(self, user_id: str = "student_default") -> LearnerProfileResponse:
        records = storage.list_topic_masteries(user_id)
        
        # If student has no topics yet, seed with course topics if available
        if not records:
            all_topics = storage.get_all_topics()
            if not all_topics:
                all_topics = ["Supervised Learning", "Linear Regression", "Gradient Descent", "Neural Networks", "Optimization"]
            for t in all_topics:
                storage.save_topic_mastery(user_id, t, mastery_score=0.20, attempts_delta=0, correct_delta=0)
            records = storage.list_topic_masteries(user_id)

        topic_models: List[TopicMastery] = []
        weak: List[str] = []
        strong: List[str] = []
        total_score = 0.0

        for r in records:
            score = r["mastery_score"]
            total_score += score
            status = "mastered" if score >= 0.75 else ("in_progress" if score >= 0.45 else "needs_practice")
            if score < 0.50:
                weak.append(r["topic_name"])
            elif score >= 0.75:
                strong.append(r["topic_name"])

            topic_models.append(TopicMastery(
                topic_name=r["topic_name"],
                mastery_score=score,
                p_transit=r["p_transit"],
                p_guess=r["p_guess"],
                p_slip=r["p_slip"],
                attempts_count=r["attempts_count"],
                correct_count=r["correct_count"],
                status=status
            ))

        overall = total_score / len(records) if records else 0.0

        recent_assessments = storage.list_assessments(user_id, limit=5)
        
        # Build adaptive recommendations
        activities = self._build_recommendations(weak, strong, records)

        return LearnerProfileResponse(
            user_id=user_id,
            name="Learner",
            overall_mastery=round(overall, 3),
            topics=topic_models,
            weak_topics=weak,
            strong_topics=strong,
            recent_assessments=recent_assessments,
            recommended_activities=activities
        )

    def _build_recommendations(self, weak_topics: List[str], strong_topics: List[str], records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        recs = []
        for w in weak_topics[:3]:
            recs.append({
                "type": "diagnostic_review",
                "priority": "high",
                "title": f"Review Core Foundations: {w}",
                "description": f"Mastery in {w} is below target. Review lecture slides and test key concepts.",
                "action": "tutor",
                "topic": w
            })
            recs.append({
                "type": "adaptive_quiz",
                "priority": "medium",
                "title": f"Practice Quiz: {w}",
                "description": "5 targeted questions with immediate citation feedback to reinforce understanding.",
                "action": "quiz",
                "topic": w
            })

        if not recs and records:
            # Advance to challenge
            recs.append({
                "type": "challenge_assessment",
                "priority": "medium",
                "title": "Comprehensive Challenge Assessment",
                "description": "Cross-topic questions testing synthesis across slides and textbooks.",
                "action": "quiz",
                "topic": "Comprehensive"
            })
        return recs

mastery_service = BayesianKnowledgeTracingService()
