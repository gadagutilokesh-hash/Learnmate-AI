import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.services.retrieval.hybrid_retriever import hybrid_retriever
from app.core.gemini import (
    gemini_service, GeminiQuotaExceededError, is_gemini_quota_error,
    GeminiServiceUnavailableError, is_gemini_transient_error,
    get_friendly_service_unavailable_message,
    extract_gemini_retry_delay, get_friendly_quota_message, sanitize_error
)
from app.core.config import settings
from app.models.schema import TutorQueryRequest, TutorQueryResponse, Citation

logger = logging.getLogger(__name__)

class GroundedTutorLLMResponse(BaseModel):
    """
    Pydantic schema enforcing structured output for the grounded AI tutor.
    The model provides the answer, grounding assessment, and 1-based source indices.
    All citation metadata (page, slide, filename, timestamp) is strictly resolved
    by the backend from the verified retrieved chunks, preventing hallucination.
    """
    answer: str = Field(
        description="Clear, comprehensive, and source-grounded academic explanation based strictly on the provided course excerpts."
    )
    is_sufficiently_grounded: bool = Field(
        description="Set to true if and only if the retrieved course excerpts contain sufficient evidence to answer the student inquiry. If evidence is insufficient, set to false."
    )
    cited_source_indices: List[int] = Field(
        default_factory=list,
        description="List of 1-based source indices (e.g. [1, 2]) that directly substantiate facts in the answer. Only include indices of sources that were provided."
    )
    insufficient_evidence_reason: Optional[str] = Field(
        default=None,
        description="If is_sufficiently_grounded is false, explain why the uploaded course materials cannot substantiate an answer."
    )

GROUNDED_TUTOR_SYSTEM_PROMPT = """You are LearnMate AI, an authoritative, source-grounded academic tutor.
Your highest imperative is ACADEMIC FIDELITY:
1. Ground your explanations SOLELY in the provided course excerpts.
2. If the provided excerpts do not contain enough verified information to address the student's inquiry, set is_sufficiently_grounded to false and state what is missing.
3. NEVER fabricate facts, citations, or references not supported by the excerpts.
4. Set cited_source_indices to include only the 1-based indices (e.g., [1, 2]) of sources from which you drew factual assertions.
5. Do NOT invent source numbers outside the range of provided excerpts.
"""

class GroundedTutorService:
    def answer_query(self, req: TutorQueryRequest) -> TutorQueryResponse:
        min_rel = getattr(settings, "MIN_RELEVANCE_SCORE", 0.25)

        # 1. Retrieve top-k context passages using hybrid search
        try:
            retrieved_chunks = hybrid_retriever.retrieve(
                query=req.query,
                course_id=req.course_id,
                top_k=req.top_k,
                min_relevance=min_rel
            )
        except GeminiQuotaExceededError as q_err:
            logger.warning(f"Live Gemini quota exceeded during tutor retrieval: {q_err}")
            return TutorQueryResponse(
                answer=q_err.message,
                is_grounded=False,
                citations=[],
                unsupported_reason=None,
                is_error=True,
                error_type="quota_exceeded",
                retry_after=q_err.retry_after_human
            )
        except GeminiServiceUnavailableError as s_err:
            logger.warning(f"Live Gemini service unavailable during tutor retrieval: {s_err}")
            return TutorQueryResponse(
                answer=s_err.message,
                is_grounded=False,
                citations=[],
                unsupported_reason=None,
                is_error=True,
                error_type="service_unavailable",
                retry_after=s_err.retry_after_human
            )
        except Exception as retr_err:
            if is_gemini_quota_error(retr_err):
                _, human = extract_gemini_retry_delay(retr_err)
                msg = get_friendly_quota_message(retr_err, retry_after_human=human)
                logger.warning(f"Live Gemini quota error detected during retrieval: {msg}")
                return TutorQueryResponse(
                    answer=msg,
                    is_grounded=False,
                    citations=[],
                    unsupported_reason=None,
                    is_error=True,
                    error_type="quota_exceeded",
                    retry_after=human
                )
            if is_gemini_transient_error(retr_err):
                _, human = extract_gemini_retry_delay(retr_err)
                msg = get_friendly_service_unavailable_message(retr_err, retry_after_human=human)
                logger.warning(f"Live Gemini service unavailable detected during retrieval: {msg}")
                return TutorQueryResponse(
                    answer=msg,
                    is_grounded=False,
                    citations=[],
                    unsupported_reason=None,
                    is_error=True,
                    error_type="service_unavailable",
                    retry_after=human
                )
            sanitized = sanitize_error(retr_err)
            logger.error(f"Error during tutor retrieval: {sanitized}")
            return TutorQueryResponse(
                answer=f"AI Tutor retrieval error: {sanitized}",
                is_grounded=False,
                citations=[],
                unsupported_reason=None,
                is_error=True,
                error_type="retrieval_error"
            )

        # 2. Strict Grounding Rejection Check: No chunks exceeded relevance threshold
        if not retrieved_chunks:
            return TutorQueryResponse(
                answer=(
                    "I cannot find this topic or concept in your uploaded course materials. "
                    "To maintain complete academic accuracy and prevent misinformation, LearnMate AI only answers questions "
                    "supported by your textbooks, lecture slides, or video transcripts."
                ),
                is_grounded=False,
                citations=[],
                unsupported_reason="No matching excerpts exceeded the relevance threshold in uploaded course materials.",
                external_context_notes=(
                    "Tip: Verify that the document containing this topic is uploaded to the course, "
                    "or check the spelling of your query keywords."
                ),
                suggested_followups=[
                    "What topics are covered in the uploaded syllabus?",
                    "Can you summarize the main concepts from the first lecture?"
                ]
            )

        # 3. Construct grounded prompt with source citations and metadata
        context_blocks = []
        for idx, c in enumerate(retrieved_chunks):
            source_num = idx + 1
            loc = []
            if c.get("page_number"):
                loc.append(f"Page {c['page_number']}")
            if c.get("slide_number"):
                loc.append(f"Slide {c['slide_number']}")
            if c.get("start_timestamp"):
                loc.append(f"Timestamp {c['start_timestamp']}-{c.get('end_timestamp', '')}")

            loc_str = ", ".join(loc) if loc else "Document Content"
            context_blocks.append(
                f"[Source {source_num}: {c.get('filename', 'Document')} ({loc_str})]:\n{c.get('content', '')}\n"
            )

        context_text = "\n".join(context_blocks)

        prompt = f"""Student Query: "{req.query}"

Retrieved Course Excerpts:
-------------------------
{context_text}
-------------------------

Please provide a clear, comprehensive, and grounded answer to the student query based solely on the above excerpts.
Return your response structured as JSON adhering to the specified schema.
Indicate which sources you cited via cited_source_indices. If the excerpts do not contain enough facts to answer, set is_sufficiently_grounded to false.
"""

        # 4. Generate structured response with live Gemini or offline fallback
        try:
            raw_response = gemini_service.generate_text(
                prompt=prompt,
                system_instruction=GROUNDED_TUTOR_SYSTEM_PROMPT,
                json_schema=GroundedTutorLLMResponse
            )

            # Validate output using Pydantic
            try:
                parsed_llm = GroundedTutorLLMResponse.model_validate_json(raw_response)
            except Exception as parse_err:
                logger.warning(f"Structured response JSON validation fallback: {parse_err}. Attempting raw dict parse.")
                data = json.loads(raw_response)
                parsed_llm = GroundedTutorLLMResponse.model_validate(data)

        except GeminiQuotaExceededError as q_err:
            logger.warning(f"Live Gemini quota exceeded for tutor query: {q_err.message}")
            return TutorQueryResponse(
                answer=q_err.message,
                is_grounded=False,
                citations=[],
                unsupported_reason=None,
                is_error=True,
                error_type="quota_exceeded",
                retry_after=q_err.retry_after_human
            )
        except GeminiServiceUnavailableError as s_err:
            logger.warning(f"Live Gemini service unavailable for tutor query: {s_err.message}")
            return TutorQueryResponse(
                answer=s_err.message,
                is_grounded=False,
                citations=[],
                unsupported_reason=None,
                is_error=True,
                error_type="service_unavailable",
                retry_after=s_err.retry_after_human
            )
        except Exception as gen_err:
            if is_gemini_quota_error(gen_err):
                _, human = extract_gemini_retry_delay(gen_err)
                msg = get_friendly_quota_message(gen_err, retry_after_human=human)
                logger.warning(f"Live Gemini quota error detected for tutor query: {msg}")
                return TutorQueryResponse(
                    answer=msg,
                    is_grounded=False,
                    citations=[],
                    unsupported_reason=None,
                    is_error=True,
                    error_type="quota_exceeded",
                    retry_after=human
                )
            if is_gemini_transient_error(gen_err):
                _, human = extract_gemini_retry_delay(gen_err)
                msg = get_friendly_service_unavailable_message(gen_err, retry_after_human=human)
                logger.warning(f"Live Gemini service unavailable detected for tutor query: {msg}")
                return TutorQueryResponse(
                    answer=msg,
                    is_grounded=False,
                    citations=[],
                    unsupported_reason=None,
                    is_error=True,
                    error_type="service_unavailable",
                    retry_after=human
                )
            sanitized_err = sanitize_error(gen_err)
            logger.error(f"AI Tutor generation failed for tutor query: {sanitized_err}")
            return TutorQueryResponse(
                answer=f"AI Tutor service error: {sanitized_err}",
                is_grounded=False,
                citations=[],
                unsupported_reason=None,
                is_error=True,
                error_type="service_error"
            )

        # 5. Programmatic Citation Validation (Do NOT rely on prompting alone)
        # Verify cited indices against actual retrieved chunks; reject any out-of-bounds or fabricated indices
        valid_citations: List[Citation] = []
        seen_indices = set()

        for s_idx in parsed_llm.cited_source_indices:
            # Source indices are 1-based
            if isinstance(s_idx, int) and 1 <= s_idx <= len(retrieved_chunks) and s_idx not in seen_indices:
                seen_indices.add(s_idx)
                chunk = retrieved_chunks[s_idx - 1]
                valid_citations.append(Citation(
                    source_file=chunk.get("filename", "Course Document"),
                    source_type=chunk.get("source_type", "pdf"),
                    page_number=chunk.get("page_number"),
                    slide_number=chunk.get("slide_number"),
                    start_timestamp=chunk.get("start_timestamp"),
                    end_timestamp=chunk.get("end_timestamp"),
                    excerpt=chunk.get("content", "")[:280] + ("..." if len(chunk.get("content", "")) > 280 else ""),
                    relevance_score=chunk.get("hybrid_score"),
                    topic=chunk.get("topic"),
                    concept=chunk.get("concept")
                ))
            else:
                logger.warning(f"Rejected invalid or fabricated citation index: {s_idx} (valid range: 1..{len(retrieved_chunks)})")

        # 6. Flag insufficient evidence or ungrounded assertions
        if not parsed_llm.is_sufficiently_grounded or not valid_citations:
            unsupported_reason = parsed_llm.insufficient_evidence_reason or (
                "The retrieved course excerpts do not contain sufficient verified evidence to support this query."
                if not parsed_llm.is_sufficiently_grounded
                else "No valid source citations could be verified in the course materials."
            )
            answer_text = parsed_llm.answer
            # Ensure the user understands evidence is insufficient
            if "cannot find" not in answer_text.lower() and "insufficient" not in answer_text.lower() and "unable" not in answer_text.lower():
                answer_text = (
                    f"I cannot find sufficient evidence in your uploaded course materials to substantiate an answer to this inquiry. "
                    f"{unsupported_reason}"
                )

            return TutorQueryResponse(
                answer=answer_text,
                is_grounded=False,
                citations=[],
                unsupported_reason=unsupported_reason,
                external_context_notes="Tip: Upload the relevant lecture slide deck or chapter PDF to expand course coverage.",
                suggested_followups=[
                    f"Can you explain {retrieved_chunks[0].get('topic', 'the foundational concepts')} instead?",
                    "What topics are covered in the uploaded course documents?"
                ]
            )

        # 7. Follow-up recommendations grounded in course topics
        primary_topic = retrieved_chunks[0].get("topic", "the foundational concepts")
        followups = [
            f"How does this relate to {primary_topic}?",
            "Would you like to test your understanding with an adaptive quiz on this topic?",
            "Can you explain the key formula or diagram associated with this section?"
        ]

        return TutorQueryResponse(
            answer=parsed_llm.answer,
            is_grounded=True,
            citations=valid_citations,
            suggested_followups=followups
        )

grounded_tutor = GroundedTutorService()
