import os
import re
import logging
from typing import List, Tuple
from app.services.ingestion.base import ExtractedChunk, chunk_text
from app.core.gemini import gemini_service

logger = logging.getLogger(__name__)

class PDFParser:
    """
    High-fidelity PDF document extractor using PyMuPDF (fitz).
    Extracts text, tables, and multimodal diagrams with exact page-level provenance.
    """
    def parse(self, file_path: str, default_topic: str = "General") -> Tuple[List[ExtractedChunk], int]:
        chunks: List[ExtractedChunk] = []
        total_pages = 0

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            total_pages = len(doc)

            current_topic = default_topic

            for page_index in range(total_pages):
                page = doc[page_index]
                page_number = page_index + 1  # 1-indexed

                # 1. Text extraction
                raw_text = page.get_text("text")

                # Detect header/topic if page begins with a heading pattern
                first_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
                if first_lines:
                    first_line = first_lines[0]
                    if len(first_line) < 80 and not first_line.endswith("."):
                        current_topic = first_line

                # 2. Table extraction (PyMuPDF 1.23+)
                try:
                    tables = page.find_tables()
                    for t in tables:
                        table_data = t.extract()
                        if table_data:
                            table_md = "\n".join([" | ".join([str(c or "") for c in row]) for row in table_data])
                            chunks.append(ExtractedChunk(
                                content=f"Table on page {page_number}:\n{table_md}",
                                source_type="pdf",
                                chunk_type="table",
                                page_number=page_number,
                                topic=current_topic,
                                metadata={"rows": len(table_data)}
                            ))
                except Exception as e_table:
                    logger.debug(f"Table parsing skipped on page {page_number}: {e_table}")

                # 3. Text chunking
                if raw_text.strip():
                    page_chunks = chunk_text(
                        text=raw_text,
                        source_type="pdf",
                        page_number=page_number,
                        chunk_type="text",
                        topic=current_topic
                    )
                    chunks.extend(page_chunks)

                # 4. Multimodal diagram / image extraction
                try:
                    images = page.get_images(full=True)
                    for img_index, img_info in enumerate(images[:2]):  # Limit to 2 per page to balance throughput
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image.get("image")
                        image_ext = base_image.get("ext", "png")
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)

                        # Only analyze diagrams of significant size
                        if width > 150 and height > 150 and image_bytes:
                            description = gemini_service.generate_multimodal_description(
                                image_bytes=image_bytes,
                                mime_type=f"image/{image_ext}",
                                prompt=f"Explain what this diagram, chart, or figure illustrates in educational context from page {page_number}."
                            )
                            chunks.append(ExtractedChunk(
                                content=f"[Diagram/Figure on Page {page_number}]: {description}",
                                source_type="pdf",
                                chunk_type="diagram",
                                page_number=page_number,
                                topic=current_topic,
                                metadata={"width": width, "height": height, "format": image_ext}
                            ))
                except Exception as e_img:
                    logger.debug(f"Image extraction skipped on page {page_number}: {e_img}")

            doc.close()

        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise e

        return chunks, total_pages

pdf_parser = PDFParser()
