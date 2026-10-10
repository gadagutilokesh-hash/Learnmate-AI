import json
import logging
from typing import Dict, Any, List, Optional
from app.services.retrieval.hybrid_retriever import hybrid_retriever
from app.core.gemini import gemini_service
from app.models.schema import TutorQueryRequest, TutorQueryResponse, Citation

logger = logging.getLogger(__name__)

GROUNDED_TUTOR_SYSTEM_PROMPT = """You are LearnMate AI, an authoritative, source-grounded academic tutor.
Your highest imperative is ACADEMIC FIDELITY:
1. Ground your explanations SOLELY in the provided course excerpts.
2. For every assertion, refer directly to the supporting document, page, slide number, or video timestamp.
3. If the provided excerpts do not contain enough information to address the student's inquiry, explicitly declare: "I cannot find this information in your uploaded course materials."
4. NEVER fabricate or invent citations, page numbers, or textbook references.
5. If you provide any helpful general context outside the text, place it under a distinct header titled: "### Supplemental General Context (Not in Course Notes)".
"""

class GroundedTutorService:
    def answer_query(self, req: TutorQueryRequest) -> TutorQueryResponse:
        # 1. Retrieve top-k context passages using hybrid search
        retrieved_chunks = hybrid_retriever.retrieve(
            query=req.query,
            course_id=req.course_id,
            top_k=req.top_k,
            min_relevance=0.25
        )

        # 2. Strict Grounding Rejection Check
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

        citations = hybrid_retriever.format_citations(retrieved_chunks)

        # 3. Construct grounded prompt with source citations
        context_blocks = []
        for idx, c in enumerate(retrieved_chunks):
            loc = []
            if c.get("page_number"):
                loc.append(f"Page {c['page_number']}")
            if c.get("slide_number"):
                loc.append(f"Slide {c['slide_number']}")
            if c.get("start_timestamp"):
                loc.append(f"Timestamp {c['start_timestamp']}-{c.get('end_timestamp', '')}")

            loc_str = ", ".join(loc) if loc else "Document Content"
            context_blocks.append(
                f"[Source {idx+1}: {c.get('filename', 'Document')} ({loc_str})]:\n{c.get('content', '')}\n"
            )

        context_text = "\n".join(context_blocks)

        prompt = f"""Student Query: "{req.query}"

Retrieved Course Excerpts:
-------------------------
{context_text}
-------------------------

Please provide a clear, comprehensive, and grounded answer to the student query based on the above excerpts.
Cite the relevant sources (e.g., [Source 1], [Page X], [Slide Y]) directly in your explanation.
"""

        raw_answer = gemini_service.generate_text(
            prompt=prompt,
            system_instruction=GROUNDED_TUTOR_SYSTEM_PROMPT
        )

        # Generate intelligent follow-up questions
        followups = [
            f"How does this relate to {retrieved_chunks[0].get('topic', 'the foundational concepts')}?",
            "Would you like to test your understanding with an adaptive quiz on this topic?",
            "Can you explain the key formula or diagram associated with this section?"
        ]

        return TutorQueryResponse(
            answer=raw_answer,
            is_grounded=True,
            citations=citations,
            suggested_followups=followups
        )

grounded_tutor = GroundedTutorService()
