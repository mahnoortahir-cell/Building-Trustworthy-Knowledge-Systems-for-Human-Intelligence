from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.documents.embedding_service import DatabaseEmbeddingStore
from app.documents.embeddings import get_embedding_provider
from app.documents.retrieval import DatabaseChunkSearchStore
from app.documents.retrieval_schemas import (
    RetrievedChunkResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.documents.retrieval_service import (
    RetrievalEmbeddingError,
    RetrievalValidationError,
    search_document_chunks,
)
from app.documents.schemas import (
    DocumentResponse,
    DocumentVersionResponse,
)
from app.documents.service import (
    DocumentCreationError,
    DocumentStorageError,
    InvalidDocumentError,
    create_document_records,
    delete_stored_file,
    process_document_extraction,
    store_uploaded_file,
)
from app.models.membership import Membership
from app.organizations.dependencies import get_current_membership
from app.documents.llm_answer_generator import LLMAnswerGenerator
from app.documents.llm_factory import (
    UnsupportedLLMProviderError,
    get_llm_provider,
)

from app.documents.rag_schemas import (
    AnswerCitationResponse,
    DocumentAnswerRequest,
    DocumentAnswerResponse,
)
from app.documents.rag_service import (
    RagGenerationError,
    RagValidationError,
    generate_document_answer,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/documents",
    tags=["Documents"],
)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    title: Annotated[str, Form(min_length=1, max_length=255)],
    file: Annotated[UploadFile, File()],
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentResponse:
    storage_path: str | None = None

    try:
        storage_path, file_size, file_checksum = await store_uploaded_file(
            file=file,
            organization_id=membership.organization_id,
        )

        document, version = create_document_records(
            db=db,
            organization_id=membership.organization_id,
            created_by_user_id=membership.user_id,
            title=title,
            original_filename=file.filename or "document.pdf",
            content_type=file.content_type or "application/pdf",
            storage_path=storage_path,
            file_size=file_size,
            file_checksum=file_checksum,
        )

        process_document_extraction(
            db,
            document,
            version,
            embedding_provider=get_embedding_provider(),
            embedding_store=DatabaseEmbeddingStore(),
        )

    except InvalidDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except DocumentCreationError as exc:
        if storage_path is not None:
            delete_stored_file(storage_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except Exception:
        if storage_path is not None:
            delete_stored_file(storage_path)

        raise

    return DocumentResponse(
        id=document.id,
        organization_id=document.organization_id,
        created_by_user_id=document.created_by_user_id,
        title=document.title,
        original_filename=document.original_filename,
        content_type=document.content_type,
        status=document.status.value,
        created_at=document.created_at,
        updated_at=document.updated_at,
        latest_version=DocumentVersionResponse(
            id=version.id,
            version_number=version.version_number,
            storage_path=version.storage_path,
            file_size=version.file_size,
            file_checksum=version.file_checksum,
            extraction_status=version.extraction_status.value,
            created_at=version.created_at,
        ),
    )


@router.post(
    "/search",
    response_model=SemanticSearchResponse,
    status_code=status.HTTP_200_OK,
)
def semantic_search(
    payload: SemanticSearchRequest,
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> SemanticSearchResponse:
    try:
        results = search_document_chunks(
            db,
            query=payload.query,
            organization_id=membership.organization_id,
            provider=get_embedding_provider(),
            store=DatabaseChunkSearchStore(),
            limit=payload.limit,
            document_id=payload.document_id,
            document_version_id=payload.document_version_id,
        )
    except RetrievalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except RetrievalEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return SemanticSearchResponse(
        query=payload.query.strip(),
        result_count=len(results),
        results=[
            RetrievedChunkResponse(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                document_version_id=result.document_version_id,
                chunk_index=result.chunk_index,
                content=result.content,
                score=result.score,
            )
            for result in results
        ],
    )

@router.post(
    "/answer",
    response_model=DocumentAnswerResponse,
    status_code=status.HTTP_200_OK,
)
def answer_document_question(
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    payload: DocumentAnswerRequest,
) -> DocumentAnswerResponse:
    try:
        result = generate_document_answer(
            db,
            question=payload.question,
            organization_id=membership.organization_id,
            embedding_provider=get_embedding_provider(),
            search_store=DatabaseChunkSearchStore(),
            answer_generator=LLMAnswerGenerator(
                provider=get_llm_provider(),
            ),
            limit=payload.limit,
            document_id=payload.document_id,
            document_version_id=payload.document_version_id,
        )

    except RagValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except UnsupportedLLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except RagGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return DocumentAnswerResponse(
        answer=result.answer,
        citations=[
            AnswerCitationResponse(
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                document_version_id=(
                    citation.document_version_id
                ),
                chunk_index=citation.chunk_index,
                content=citation.content,
                score=citation.score,
            )
            for citation in result.citations
        ],
    )