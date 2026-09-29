# Paperly — API Specification

Base URL: `https://<tunnel-url>.trycloudflare.com/api/v1` (or local `http://localhost:8000/api/v1`)

---

## 1. Authentication Endpoints

### 1.1 Login
- **Endpoint**: `POST /auth/login`
- **Description**: Authenticate teacher using username and password. Returns JWT token.
- **Request Body** (`application/x-www-form-urlencoded` or `application/json`):
  ```json
  {
    "username": "teacher01",
    "password": "mypassword123"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "usr_9a8b7c",
      "username": "teacher01",
      "full_name": "Sarah Jenkins",
      "role": "teacher"
    }
  }
  ```

### 1.2 Get Current User
- **Endpoint**: `GET /auth/me`
- **Headers**: `Authorization: Bearer <access_token>`
- **Response** (`200 OK`):
  ```json
  {
    "id": "usr_9a8b7c",
    "username": "teacher01",
    "full_name": "Sarah Jenkins",
    "role": "teacher"
  }
  ```

---

## 2. Conversation Endpoints

### 2.1 List Conversations
- **Endpoint**: `GET /conversations`
- **Response** (`200 OK`):
  ```json
  [
    {
      "id": "conv_1a2b3c",
      "title": "NEET Physics — Electrostatics",
      "paper_id": "paper_xyz789",
      "updated_at": "2026-09-29T10:30:00Z",
      "created_at": "2026-09-29T09:00:00Z"
    }
  ]
  ```

### 2.2 Create Conversation
- **Endpoint**: `POST /conversations`
- **Request Body**:
  ```json
  {
    "title": "New Assessment"
  }
  ```
- **Response** (`201 Created`):
  ```json
  {
    "id": "conv_1a2b3c",
    "title": "New Assessment",
    "created_at": "2026-09-29T09:00:00Z"
  }
  ```

### 2.3 Send Message (Streaming / Synchronous)
- **Endpoint**: `POST /conversations/{id}/messages`
- **Request Body**:
  ```json
  {
    "content": "Make a 40-question NEET Physics paper on Electrostatics, moderate difficulty."
  }
  ```
- **Response** (`200 OK` / SSE `text/event-stream`):
  Streaming events providing status and final output:
  ```json
  { "type": "status", "message": "Analyzing requirements..." }
  { "type": "status", "message": "Researching NEET exam pattern..." }
  { "type": "message", "role": "assistant", "content": "How many total marks should the paper be, or should I follow the standard NEET 180-mark layout?" }
  ```

### 2.4 Upload Source Material
- **Endpoint**: `POST /conversations/{id}/upload`
- **Request**: Multipart Form Data (`file: <binary>`)
- **Supported Formats**: `.pdf`, `.docx`, `.pptx`, `.txt`, `.csv`, `.png`, `.jpg`
- **Response** (`200 OK`):
  ```json
  {
    "file_id": "file_4d5e6f",
    "filename": "Chapter_Electrostatics.pdf",
    "extracted_characters": 18450,
    "status": "ready"
  }
  ```

---

## 3. Paper & Document Endpoints

### 3.1 Get Paper
- **Endpoint**: `GET /papers/{id}`
- **Response** (`200 OK`):
  Returns full `PaperSchema` JSON structure.

### 3.2 Edit Paper Conversational
- **Endpoint**: `POST /papers/{id}/edit`
- **Request Body**:
  ```json
  {
    "instruction": "Replace question 5 with a numerical problem on Gauss's Law."
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "paper_id": "paper_xyz789",
    "version_number": 2,
    "change_summary": "Replaced Q5 with a 3-mark numerical problem on Gauss's Law",
    "paper_schema": { ... }
  }
  ```

### 3.3 Export Paper
- **Endpoint**: `GET /papers/{id}/export/{format}`
- **Path Parameters**: `format` can be `pdf` or `docx`
- **Query Parameters**: `include_answers=false`
- **Response**: Binary stream (`application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)

### 3.4 Export Solutions / Answer Key
- **Endpoint**: `GET /papers/{id}/solutions/{format}`
- **Response**: Binary stream of the answer key and step-by-step solutions document.
