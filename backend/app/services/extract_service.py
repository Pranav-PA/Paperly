import io
from pathlib import Path
from typing import Tuple
from pypdf import PdfReader
import docx


class DocumentExtractionService:
    MAX_CHARACTERS = 100_000  # Cap extracted text to avoid memory exhaustion on Termux

    @classmethod
    def extract_text_from_bytes(cls, filename: str, content: bytes, mime_type: str) -> Tuple[str, int]:
        """Extract text from uploaded document bytes according to file type."""
        ext = Path(filename).suffix.lower()
        extracted = ""

        if ext == ".pdf" or "pdf" in mime_type:
            extracted = cls._extract_pdf(content)
        elif ext in [".docx", ".doc"] or "word" in mime_type or "officedocument" in mime_type:
            extracted = cls._extract_docx(content)
        elif ext in [".txt", ".csv", ".md"]:
            extracted = content.decode("utf-8", errors="replace")
        else:
            extracted = content.decode("utf-8", errors="replace")

        # Trim to max characters
        if len(extracted) > cls.MAX_CHARACTERS:
            extracted = extracted[:cls.MAX_CHARACTERS] + "\n...[Content truncated for length]..."

        # Wrap in safe prompt-injection isolation delimiters
        safe_wrapped = (
            f'<untrusted_source_material filename="{filename}">\n'
            f"{extracted}\n"
            f"</untrusted_source_material>"
        )

        return safe_wrapped, len(extracted)

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        text_parts = []
        reader = PdfReader(io.BytesIO(content))
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"[Page {page_idx + 1}]\n{page_text}")
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_docx(content: bytes) -> str:
        doc = docx.Document(io.BytesIO(content))
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)
        return "\n".join(text_parts)
