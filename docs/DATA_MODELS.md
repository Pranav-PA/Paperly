# Paperly — Data Models & PaperSchema AST

## 1. PaperSchema (Intermediate Document AST)

The core data structure that bridges AI generation, interactive editing, and document rendering (PDF/DOCX) is the `PaperSchema`.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PaperSchema",
  "type": "object",
  "required": ["metadata", "sections"],
  "properties": {
    "metadata": {
      "type": "object",
      "required": ["title", "subject", "total_marks", "duration_minutes"],
      "properties": {
        "institution_name": { "type": "string" },
        "title": { "type": "string" },
        "subtitle": { "type": "string" },
        "class_grade": { "type": "string" },
        "subject": { "type": "string" },
        "academic_year": { "type": "string" },
        "date": { "type": "string" },
        "duration_minutes": { "type": "integer" },
        "total_marks": { "type": "number" },
        "general_instructions": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "title", "questions"],
        "properties": {
          "id": { "type": "string" },
          "title": { "type": "string" },
          "instructions": { "type": "string" },
          "section_total_marks": { "type": "number" },
          "questions": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["id", "question_number", "type", "text", "marks"],
              "properties": {
                "id": { "type": "string" },
                "question_number": { "type": "integer" },
                "type": {
                  "type": "string",
                  "enum": [
                    "mcq",
                    "multi_select",
                    "numerical",
                    "assertion_reason",
                    "short_answer",
                    "long_answer",
                    "match_the_following",
                    "case_study"
                  ]
                },
                "text": { "type": "string" },
                "options": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "label": { "type": "string" },
                      "text": { "type": "string" }
                    }
                  }
                },
                "marks": { "type": "number" },
                "negative_marks": { "type": "number", "default": 0.0 },
                "difficulty": { "type": "string", "enum": ["easy", "medium", "hard"] },
                "topic": { "type": "string" },
                "answer_key": { "type": "string" },
                "detailed_solution": { "type": "string" },
                "verification_scratchpad": { "type": "string" }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## 2. Relational Database Models (SQLite / SQLAlchemy)

### Users
- `id`: String (UUID v4) [PK]
- `username`: String (Unique, Indexed)
- `hashed_password`: String (Bcrypt)
- `full_name`: String (Optional)
- `role`: String (Enum: 'admin', 'teacher')
- `is_active`: Boolean (Default: True)
- `created_at`: DateTime (UTC)

### Conversations
- `id`: String (UUID v4) [PK]
- `user_id`: String [FK -> Users.id]
- `title`: String
- `created_at`: DateTime (UTC)
- `updated_at`: DateTime (UTC)

### Messages
- `id`: String (UUID v4) [PK]
- `conversation_id`: String [FK -> Conversations.id]
- `role`: String (Enum: 'user', 'assistant', 'system')
- `content`: Text
- `metadata_json`: Text (JSON string storing tool calls, generation state, tokens)
- `created_at`: DateTime (UTC)

### Papers
- `id`: String (UUID v4) [PK]
- `conversation_id`: String [FK -> Conversations.id]
- `title`: String
- `current_version_id`: String (Nullable)
- `created_at`: DateTime (UTC)
- `updated_at`: DateTime (UTC)

### PaperVersions
- `id`: String (UUID v4) [PK]
- `paper_id`: String [FK -> Papers.id]
- `version_number`: Integer
- `schema_json`: Text (Full serialized PaperSchema)
- `change_summary`: String (Optional, e.g. "Replaced Q4")
- `created_at`: DateTime (UTC)

### UploadedFiles
- `id`: String (UUID v4) [PK]
- `conversation_id`: String [FK -> Conversations.id]
- `filename`: String
- `mime_type`: String
- `extracted_text`: Text
- `file_size`: Integer
- `created_at`: DateTime (UTC)
