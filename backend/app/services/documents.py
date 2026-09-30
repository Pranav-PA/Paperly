"""Storage and text views of a paper version, whichever kind it is (Paperly schema, Word or PDF file)."""
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings
from app.models.paper import PaperVersion
from app.schemas.paper_schema import PaperMetadata, PaperSchema
from app.services import doc_edit
from app.services.ai_service import AIService

EXTENSIONS = {"docx": ".docx", "pdf": ".pdf"}
MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def file_path(version: PaperVersion) -> Optional[Path]:
    return Path(settings.DOCS_DIR) / version.file_name if version.file_name else None


def read_file(version: PaperVersion) -> bytes:
    path = file_path(version)
    if not path or not path.exists():
        raise FileNotFoundError("The document file for this version is missing on the server.")
    return path.read_bytes()


def write_file(version_id: str, kind: str, data: bytes) -> str:
    name = f"{version_id}{EXTENSIONS[kind]}"
    (Path(settings.DOCS_DIR) / name).write_bytes(data)
    return name


def stub_schema(title: str) -> PaperSchema:
    """Minimal schema stored alongside Word/PDF versions (title for lists; older apps still parse it)."""
    return PaperSchema(metadata=PaperMetadata(title=title[:200] or "Document"))


def title_from_filename(filename: str) -> str:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return stem[:1].upper() + stem[1:] if stem else "Document"


def doc_context(version: Optional[PaperVersion]) -> Tuple[Optional[str], str]:
    """(kind, text the assistant sees) for the current version."""
    if version is None:
        return None, ""
    if version.doc_kind == "paperly":
        return "paperly", AIService.render_paperly(PaperSchema.model_validate_json(version.schema_json))
    data = read_file(version)
    blocks = doc_edit.docx_blocks(data) if version.doc_kind == "docx" else doc_edit.pdf_blocks(data)
    lines = []
    for b in blocks:
        text = b.text.replace("\n", " / ")
        tag = " (table)" if b.in_table else ""
        look = doc_edit.style_tag(b)
        lines.append(f"[{b.id}]{tag} {look} {text}".replace("  ", " ") if text.strip() else f"[{b.id}] (blank line)")
    return version.doc_kind, "\n".join(lines)
