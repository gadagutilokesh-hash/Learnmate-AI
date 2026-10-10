from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import re

@dataclass
class ExtractedChunk:
    content: str
    source_type: str  # "pdf", "pptx", "mp4", "audio"
    chunk_type: str = "text"  # "text", "table", "diagram", "transcript"
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    start_timestamp: Optional[str] = None
    end_timestamp: Optional[str] = None
    topic: Optional[str] = None
    concept: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

def chunk_text(
    text: str,
    source_type: str,
    page_number: Optional[int] = None,
    slide_number: Optional[int] = None,
    start_timestamp: Optional[str] = None,
    end_timestamp: Optional[str] = None,
    chunk_type: str = "text",
    max_words: int = 200,
    overlap_words: int = 40,
    topic: Optional[str] = None,
    concept: Optional[str] = None
) -> List[ExtractedChunk]:
    """
    Source-aware chunker that splits text while strictly preserving page/slide/timestamp context.
    """
    cleaned = re.sub(r'\s+', ' ', text).strip()
    if not cleaned:
        return []

    words = cleaned.split()
    if len(words) <= max_words:
        return [ExtractedChunk(
            content=cleaned,
            source_type=source_type,
            chunk_type=chunk_type,
            page_number=page_number,
            slide_number=slide_number,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            topic=topic,
            concept=concept
        )]

    chunks = []
    step = max_words - overlap_words
    for i in range(0, len(words), step):
        chunk_words = words[i:i + max_words]
        chunk_str = " ".join(chunk_words)
        chunks.append(ExtractedChunk(
            content=chunk_str,
            source_type=source_type,
            chunk_type=chunk_type,
            page_number=page_number,
            slide_number=slide_number,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            topic=topic,
            concept=concept
        ))
        if i + max_words >= len(words):
            break
    return chunks
