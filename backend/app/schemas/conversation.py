from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ConversationCreate(BaseModel):
    title: Optional[str] = "New Assessment"


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, description="Teacher prompt or instruction")


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata_json: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(ConversationSummary):
    messages: List[MessageResponse] = []
    latest_paper_id: Optional[str] = None


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    extracted_characters: int
    status: str
