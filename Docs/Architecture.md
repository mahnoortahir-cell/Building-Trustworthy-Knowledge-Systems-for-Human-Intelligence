# NoorOS System Architecture

## 1. Overview

NoorOS is a multi-tenant, trustworthy AI knowledge platform.

It allows organizations to upload documents, transform them into searchable knowledge, retrieve relevant evidence, and generate grounded answers with source citations.

NoorOS is not intended to be a basic "chat with PDF" application. It is designed as a modular Knowledge Operating System that supports:

- secure access
- document ingestion
- knowledge processing
- semantic retrieval
- AI-assisted reasoning
- citations
- evaluation
- auditability
- monitoring

---

## 2. Core Objectives

NoorOS must:

- securely authenticate users
- isolate every organization's data
- authorize actions within a specific organization
- preserve original documents and processing metadata
- transform documents into retrievable knowledge
- generate answers grounded in evidence
- provide traceable citations
- communicate insufficient evidence
- evaluate retrieval and answer quality
- keep important operations auditable
- support replaceable AI and infrastructure providers

---

## 3. High-Level Architecture

```text
Client Application
        |
        v
FastAPI Backend
        |
        +---------------- Authentication
        |
        +---------------- Organizations
        |
        +---------------- Document Ingestion
        |
        +---------------- Knowledge Processing
        |
        +---------------- Retrieval
        |
        +---------------- AI Reasoning
        |
        +---------------- Evaluation
        |
        +---------------- Audit and Monitoring
        |
        v
Storage Layer
        |
        +---------------- Relational Database
        |
        +---------------- File Storage
        |
        +---------------- Vector Database
```

---

## 4. Main Architectural Layers

### 4.1 API Layer

The API layer receives HTTP requests, validates input, applies dependencies, and returns structured responses.

Primary technologies:

- FastAPI
- Pydantic
- OAuth2 bearer authentication

Responsibilities:

- request validation
- response serialization
- authentication
- organization-scoped authorization
- HTTP error handling

Complex business logic should remain inside feature services rather than API route functions.

---

### 4.2 Authentication Layer

Authentication identifies the user making a request.

Current capabilities:

- secure user registration
- Argon2 password hashing
- OAuth2-compatible login
- JWT access tokens
- current-user resolution
- inactive-user rejection

JWT tokens identify users through the `sub` claim.

Changing authorization information, such as organization roles, must be retrieved from the database rather than permanently trusted from the JWT.

---

### 4.3 Authorization Layer

Authorization determines what an authenticated user may do.

Current organization roles:

- owner
- admin
- member

Authorization must be organization-specific.

A user who is an owner in one organization must not automatically receive owner permissions in another organization.

---

### 4.4 Organization Layer

Organizations are the tenants of NoorOS.

A user may belong to multiple organizations through membership records.

All business resources must belong to an organization, including:

- documents
- document versions
- chunks
- embeddings
- conversations
- messages
- evaluations
- audit logs

Every organization-owned query must include organization scope.

---

### 4.5 Document Ingestion Layer

The document ingestion layer accepts files and creates persistent document records.

Initial supported format:

- PDF

Possible future formats:

- DOCX
- TXT
- HTML
- Markdown
- web pages

Planned document flow:

```text
Upload File
     |
     v
Validate File
     |
     v
Create Document Record
     |
     v
Store Original File
     |
     v
Create Document Version
     |
     v
Extract Text
     |
     v
Clean and Normalize Text
     |
     v
Create Chunks
     |
     v
Generate Embeddings
     |
     v
Store Vectors
```

Long-running processing should eventually move from the HTTP request into background workers.

---

### 4.6 Knowledge Layer

The knowledge layer transforms extracted text into structured units suitable for retrieval.

Primary entities:

- Document
- DocumentVersion
- Chunk
- Embedding

Every chunk must retain metadata that connects it to its original source.

Example metadata:

- organization ID
- document ID
- document version ID
- source filename
- page number
- section heading
- chunk index
- token count
- checksum
- processing timestamp

This traceability is necessary for trustworthy citations.

---

### 4.7 Retrieval Layer

The retrieval layer finds evidence relevant to a user query.

Planned flow:

```text
User Query
    |
    v
Validate Query
    |
    v
Generate Query Embedding
    |
    v
Organization-Scoped Vector Search
    |
    v
Apply Metadata Filters
    |
    v
Retrieve Candidate Chunks
    |
    v
Optional Reranking
    |
    v
Create Evidence Context
```

Retrieval must always filter by organization.

A request from one organization must never retrieve chunks belonging to another organization.

Initial vector database candidate:

- Qdrant

The retrieval implementation should use internal interfaces so that another vector database can be introduced later.

---

### 4.8 Reasoning Layer

The reasoning layer uses retrieved evidence to generate an answer.

The language model is not treated as the source of organizational knowledge.

The organization's indexed documents are the knowledge source.

The language model should:

- understand the user's question
- synthesize retrieved evidence
- avoid unsupported claims
- identify insufficient evidence
- produce clear answers
- attach citations
- communicate uncertainty

Planned flow:

```text
Question
   +
Retrieved Evidence
   +
System Instructions
        |
        v
Language Model
        |
        v
Grounded Answer
        +
Citations
        +
Confidence Information
```

---

### 4.9 Trust Layer

Trust is a core architectural concern.

The trust layer should support:

- source citations
- document traceability
- page-level source references
- retrieval scores
- insufficient-evidence responses
- tenant isolation
- authorization
- audit logs
- prompt version tracking
- model version tracking
- document checksums
- processing statuses

NoorOS should prefer stating that evidence is insufficient instead of generating an unsupported answer.

---

### 4.10 Evaluation Layer

The evaluation layer measures whether NoorOS is working correctly.

Planned evaluation categories:

- retrieval relevance
- answer faithfulness
- citation correctness
- answer completeness
- tenant isolation
- processing quality
- latency
- error rate

Evaluation should include:

- automated tests
- benchmark datasets
- manually reviewed examples
- regression testing

---

### 4.11 Operations Layer

The operations layer supports running and maintaining NoorOS.

Planned capabilities:

- structured logging
- health checks
- Alembic migrations
- background jobs
- error tracking
- monitoring
- Docker deployment
- continuous integration
- automated testing

Current operational foundations:

- FastAPI health endpoint
- environment-based configuration
- Alembic migrations
- pytest test suite
- Git feature branches
- Pull Request workflow

---

## 5. Data Storage

### 5.1 Relational Database

Current development database:

- SQLite

Planned production database:

- PostgreSQL

The relational database stores:

- users
- organizations
- memberships
- document metadata
- document versions
- chunk metadata
- processing statuses
- conversations
- messages
- evaluations
- audit logs

The relational database is the source of truth for document and authorization records.

---

### 5.2 File Storage

Original uploaded files should not be stored directly inside the relational database.

Development storage:

- local filesystem

Possible production storage:

- Amazon S3
- Azure Blob Storage
- Google Cloud Storage
- S3-compatible object storage

---

### 5.3 Vector Database

Embeddings and searchable vector metadata will initially be stored in:

- Qdrant

The relational database remains the source of truth for document and chunk identities.

Qdrant will provide semantic vector search.

---

## 6. Multi-Tenant Data Model

```text
User
  |
  v
Membership
  |
  v
Organization
  |
  +---------------- Documents
  |
  +---------------- Conversations
  |
  +---------------- Evaluations
  |
  +---------------- Audit Logs
```

A membership connects:

- one user
- one organization
- one role

Every organization-owned query must validate membership before returning or changing data.

---

## 7. Proposed Document Data Model

```text
Organization
    |
    v
Document
    |
    v
DocumentVersion
    |
    v
Chunk
    |
    v
Embedding
```

### 7.1 Document

Represents the logical document visible to users.

Proposed fields:

- id
- organization_id
- title
- original_filename
- content_type
- status
- created_by_user_id
- created_at
- updated_at

---

### 7.2 DocumentVersion

Represents one uploaded or processed version of a document.

Proposed fields:

- id
- document_id
- version_number
- storage_path
- file_size
- file_checksum
- extraction_status
- processing_error
- created_at

---

### 7.3 Chunk

Represents a retrievable section of extracted document text.

Proposed fields:

- id
- organization_id
- document_id
- document_version_id
- text
- page_number
- section_title
- chunk_index
- token_count
- metadata
- created_at

---

### 7.4 Embedding

Represents vector-generation metadata for one chunk.

The actual vector may be stored in Qdrant.

Proposed fields:

- id
- chunk_id
- provider
- model_name
- dimensions
- vector_reference
- created_at

---

## 8. Feature-Oriented Project Structure

NoorOS uses a feature-oriented architecture.

```text
backend/app/
|
+-- core/
+-- shared/
+-- auth/
+-- organizations/
+-- users/
+-- documents/
+-- knowledge/
+-- retrieval/
+-- chat/
+-- evaluation/
+-- audit/
+-- main.py
```

Each feature may contain:

- router
- schemas
- service
- dependencies
- models
- exceptions
- tests

Shared infrastructure should be placed inside `core` or `shared`.

---

## 9. Important Engineering Principles

### Organization scope is mandatory

Every organization-owned resource must be queried using organization scope.

### Database authorization is authoritative

JWT tokens identify users, but current organization roles must come from the database.

### Generated answers require evidence

The system must not present unsupported model output as verified knowledge.

### AI providers must remain replaceable

Embedding models, language models, and vector databases should be accessed through internal service interfaces.

### Processing must be reproducible

NoorOS should record information such as:

- parser version
- chunking strategy
- embedding model
- model version
- processing timestamp
- document checksum

### Failures must remain visible

Processing failures should produce clear statuses and error records rather than silently disappearing.

### Original sources must be preserved

Generated answers and retrieved chunks must remain traceable to their original documents.

---

## 10. Current Status

Implemented:

- FastAPI application foundation
- environment configuration
- SQLAlchemy database layer
- Alembic migrations
- users
- organizations
- memberships
- secure registration
- login
- JWT authentication
- current-user endpoint
- role-based authorization
- organization-scoped authorization
- organization management endpoints
- automated authentication tests

Next major capability:

- document ingestion and document lifecycle management

---

## 11. Planned Implementation Sequence

```text
Document Model
      |
      v
Document Migration
      |
      v
Upload Endpoint
      |
      v
File Validation
      |
      v
File Storage
      |
      v
Text Extraction
      |
      v
Document Versioning
      |
      v
Chunking
      |
      v
Embedding Generation
      |
      v
Vector Search
      |
      v
Grounded Question Answering
      |
      v
Evaluation and Monitoring
```

---

## 12. Definition of Trustworthy Knowledge

In NoorOS, knowledge is considered trustworthy when:

- its organization ownership is known
- its original source is preserved
- retrieved passages can be traced to that source
- generated claims are supported by evidence
- citations identify the relevant source location
- uncertainty is communicated clearly
- processing history can be audited
- unauthorized users cannot access the data

This definition should guide all future architectural and product decisions.
