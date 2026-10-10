import os
import logging
from typing import List, Tuple
from app.services.ingestion.base import ExtractedChunk, chunk_text

logger = logging.getLogger(__name__)

class PPTXParser:
    """
    Presentation extractor using python-pptx.
    Preserves exact slide numbers, shape titles, bullet hierarchies, tables, and speaker notes.
    """
    def parse(self, file_path: str, default_topic: str = "Presentation") -> Tuple[List[ExtractedChunk], int]:
        chunks: List[ExtractedChunk] = []
        total_slides = 0

        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            total_slides = len(prs.slides)

            current_topic = default_topic

            for slide_index, slide in enumerate(prs.slides):
                slide_number = slide_index + 1
                slide_texts = []
                slide_title = None

                # Extract shapes and tables
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        text = shape.text_frame.text.strip()
                        if text:
                            if slide_title is None and len(text) < 100:
                                slide_title = text
                                current_topic = text
                            slide_texts.append(text)

                    if shape.has_table:
                        table = shape.table
                        table_rows = []
                        for row in table.rows:
                            row_vals = [cell.text.strip() for cell in row.cells]
                            table_rows.append(" | ".join(row_vals))
                        if table_rows:
                            table_md = "\n".join(table_rows)
                            chunks.append(ExtractedChunk(
                                content=f"Slide {slide_number} Table:\n{table_md}",
                                source_type="pptx",
                                chunk_type="table",
                                slide_number=slide_number,
                                topic=current_topic
                            ))

                # Extract speaker notes if available
                if slide.has_notes_slide:
                    notes_frame = slide.notes_slide.notes_text_frame
                    if notes_frame and notes_frame.text.strip():
                        slide_texts.append(f"Speaker Notes: {notes_frame.text.strip()}")

                full_slide_text = "\n".join(slide_texts).strip()
                if full_slide_text:
                    slide_chunks = chunk_text(
                        text=full_slide_text,
                        source_type="pptx",
                        slide_number=slide_number,
                        chunk_type="text",
                        topic=slide_title or current_topic
                    )
                    chunks.extend(slide_chunks)

        except Exception as e:
            logger.error(f"Failed to parse PPTX {file_path}: {e}")
            raise e

        return chunks, total_slides

pptx_parser = PPTXParser()
