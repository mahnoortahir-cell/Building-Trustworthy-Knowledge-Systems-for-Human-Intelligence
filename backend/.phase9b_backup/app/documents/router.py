from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.documents.answer_streaming import (
    encode_sse,
    stream_answer_sse_events,
)
from app.documents.stream_cancellation import (
    StreamNotFoundError,
    StreamOwnershipError,
    stream_cancellation_registry,
)
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
    RagRetrievalError,
    RagValidationError,
    generate_document_answer,
    generate_document_answer_stream,
)

from app.documents.conversation_schemas import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    ConversationRegenerateRequest,
    ConversationRegenerateResponse,
)
from app.documents.conversation_title_service import (
    assign_automatic_conversation_title,
)
from app.documents.conversation_regenerate_service import (
    regenerate_conversation_answer,
)
from app.documents.conversation_search_service import (
    search_document_conversations,
)
from app.documents.conversation_service import (
    ConversationNotFoundError,
    ConversationPersistenceError,
    ConversationValidationError,
    add_conversation_message,
    create_document_conversation,
    delete_document_conversation,
    get_conversation_history,
    get_document_conversation,
    list_conversation_messages,
    list_document_conversations,
    update_document_conversation,
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
    """
    Generate a grounded answer from uploaded documents.

    When conversation_id is provided:
    - validate the conversation belongs to the organisation;
    - load its previous messages;
    - save the user message;
    - generate an answer using the previous history;
    - save the assistant response;
    - commit both messages atomically.

    Without conversation_id, the request remains a one-off question.
    """

    conversation = None
    conversation_history = []

    normalized_conversation_id = (
        payload.conversation_id.strip()
        if payload.conversation_id is not None
        else None
    )

    try:
        if payload.conversation_id is not None:
            if not normalized_conversation_id:
                raise ConversationValidationError(
                    "conversation_id must not be empty."
                )

            conversation = get_document_conversation(
                db,
                organization_id=membership.organization_id,
                conversation_id=normalized_conversation_id,
            )

            conversation_history = get_conversation_history(
                db,
                organization_id=membership.organization_id,
                conversation_id=conversation.id,
                limit=20,
            )

            add_conversation_message(
                db,
                conversation=conversation,
                role="user",
                content=payload.question,
                commit=False,
            )

        llm_provider = get_llm_provider()

        result = generate_document_answer(
            db,
            question=payload.question,
            organization_id=membership.organization_id,
            embedding_provider=get_embedding_provider(),
            search_store=DatabaseChunkSearchStore(),
            answer_generator=LLMAnswerGenerator(
                provider=llm_provider,
            ),
            limit=payload.limit,
            document_id=payload.document_id,
            document_version_id=payload.document_version_id,
            conversation_history=conversation_history,
        )

        if conversation is not None:
            add_conversation_message(
                db,
                conversation=conversation,
                role="assistant",
                content=result.answer,
                commit=False,
            )

            assign_automatic_conversation_title(
                db,
                conversation=conversation,
                provider=llm_provider,
                user_message=payload.question,
                assistant_message=result.answer,
            )

            db.commit()
            db.refresh(conversation)

    except ConversationNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except (
        ConversationValidationError,
        RagValidationError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except ConversationPersistenceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except UnsupportedLLMProviderError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except RagRetrievalError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except RagGenerationError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise

    return DocumentAnswerResponse(
        conversation_id=(
            conversation.id
            if conversation is not None
            else None
        ),
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


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreateRequest,
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ConversationResponse:
    try:
        conversation = create_document_conversation(
            db,
            organization_id=membership.organization_id,
            created_by_user_id=membership.user_id,
            title=payload.title,
        )
    except ConversationPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ConversationResponse.model_validate(conversation)


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
)
def get_conversations(
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    limit: int = 50,
    offset: int = 0,
) -> ConversationListResponse:
    try:
        conversations = list_document_conversations(
            db,
            organization_id=membership.organization_id,
            limit=limit,
            offset=offset,
        )
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    results = [
        ConversationResponse.model_validate(conversation)
        for conversation in conversations
    ]

    return ConversationListResponse(
        conversations=results,
        count=len(results),
    )



@router.get(
    "/conversations/search",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
)
def search_conversations_endpoint(
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    query: str,
    limit: int = 20,
    offset: int = 0,
    include_message_content: bool = False,
) -> ConversationListResponse:
    """
    Search conversations in the authenticated organisation.

    Title search is enabled by default. Message-content search can be
    enabled with include_message_content=true.
    """

    try:
        conversations = search_document_conversations(
            db,
            organization_id=membership.organization_id,
            query=query,
            limit=limit,
            offset=offset,
            include_message_content=include_message_content,
        )

    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    conversation_items = [
        ConversationResponse.model_validate(conversation)
        for conversation in conversations
    ]

    return ConversationListResponse(
        conversations=conversation_items,
        count=len(conversation_items),
    )



@router.post(
    "/conversations/{conversation_id}/regenerate",
    response_model=ConversationRegenerateResponse,
    status_code=status.HTTP_200_OK,
)
def regenerate_conversation_response(
    conversation_id: str,
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    payload: ConversationRegenerateRequest,
) -> ConversationRegenerateResponse:
    """
    Generate a fresh answer for the latest user message.

    The previous assistant answer remains stored. A new assistant message
    is appended to the conversation.
    """

    try:
        result = regenerate_conversation_answer(
            db,
            organization_id=membership.organization_id,
            conversation_id=conversation_id,
            embedding_provider=get_embedding_provider(),
            search_store=DatabaseChunkSearchStore(),
            answer_generator=LLMAnswerGenerator(
                provider=get_llm_provider(),
            ),
            context_limit=payload.context_limit,
            history_limit=payload.history_limit,
            document_id=payload.document_id,
            document_version_id=payload.document_version_id,
        )

    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except ConversationPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ConversationRegenerateResponse(
        answer=result.answer,
        citations=result.citations,
        conversation_id=result.conversation_id,
        assistant_message_id=result.assistant_message_id,
        source_user_message_id=result.source_user_message_id,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_conversation(
    conversation_id: str,
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ConversationDetailResponse:
    try:
        conversation = get_document_conversation(
            db,
            conversation_id=conversation_id,
            organization_id=membership.organization_id,
        )

        messages = list_conversation_messages(
            db,
            conversation_id=conversation.id,
            organization_id=membership.organization_id,
            limit=100,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return ConversationDetailResponse(
        id=conversation.id,
        organization_id=conversation.organization_id,
        created_by_user_id=conversation.created_by_user_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            ConversationMessageResponse.model_validate(message)
            for message in messages
        ],
    )

@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdateRequest,
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ConversationResponse:
    try:
        conversation = update_document_conversation(
            db,
            organization_id=membership.organization_id,
            conversation_id=conversation_id,
            title=payload.title,
        )

    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ConversationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except ConversationPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: str,
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> Response:
    try:
        delete_document_conversation(
            db,
            conversation_id=conversation_id,
            organization_id=membership.organization_id,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConversationPersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)




@router.post(
    "/answer/stream/{stream_id}/cancel",
    status_code=status.HTTP_200_OK,
)
def cancel_document_answer_stream(
    stream_id: str,
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
) -> dict[str, str | bool | None]:
    """
    Cancel an active streamed document answer.

    Cross-organisation stream identifiers are intentionally returned as
    not-found so stream ownership information is not exposed.
    """

    try:
        stream_state = stream_cancellation_registry.cancel(
            stream_id=stream_id,
            organization_id=membership.organization_id,
        )

    except (
        StreamNotFoundError,
        StreamOwnershipError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer stream was not found.",
        ) from exc

    return {
        "stream_id": stream_state.stream_id,
        "conversation_id": stream_state.conversation_id,
        "cancelled": stream_state.is_cancelled,
        "completed": stream_state.is_completed,
    }

@router.post(
    "/answer/stream",
    status_code=status.HTTP_200_OK,
)
def stream_document_answer(
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    payload: DocumentAnswerRequest,
) -> StreamingResponse:
    """
    Stream a grounded document answer using Server-Sent Events.

    Event order:
    - start
    - citations
    - token, repeated while generation continues
    - complete

    When conversation_id is supplied, the user and assistant messages are
    committed atomically only after successful stream completion.
    """

    conversation = None
    conversation_history = []

    normalized_conversation_id = (
        payload.conversation_id.strip()
        if payload.conversation_id is not None
        else None
    )

    try:
        if payload.conversation_id is not None:
            if not normalized_conversation_id:
                raise ConversationValidationError(
                    "conversation_id must not be empty."
                )

            conversation = get_document_conversation(
                db,
                organization_id=membership.organization_id,
                conversation_id=normalized_conversation_id,
            )

            conversation_history = get_conversation_history(
                db,
                organization_id=membership.organization_id,
                conversation_id=conversation.id,
                limit=100,
            )

            add_conversation_message(
                db,
                conversation=conversation,
                role="user",
                content=payload.question,
                commit=False,
            )

        llm_provider = get_llm_provider()

        result = generate_document_answer_stream(
            db,
            question=payload.question,
            organization_id=membership.organization_id,
            embedding_provider=get_embedding_provider(),
            search_store=DatabaseChunkSearchStore(),
            answer_generator=LLMAnswerGenerator(
                provider=llm_provider,
            ),
            limit=payload.limit,
            document_id=payload.document_id,
            document_version_id=payload.document_version_id,
            conversation_history=conversation_history,
        )

    except ConversationNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except (
        ConversationValidationError,
        RagValidationError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except ConversationPersistenceError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except UnsupportedLLMProviderError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except RagRetrievalError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except RagGenerationError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise

    conversation_id = (
        conversation.id
        if conversation is not None
        else None
    )

    stream_state = stream_cancellation_registry.register(
        organization_id=membership.organization_id,
        conversation_id=conversation_id,
    )

    stream_id = stream_state.stream_id

    def is_cancelled() -> bool:
        return stream_cancellation_registry.is_cancelled(
            stream_id=stream_id,
            organization_id=membership.organization_id,
        )

    def cancel_answer() -> None:
        db.rollback()

    def remove_failed_stream() -> None:
        try:
            stream_cancellation_registry.remove(
                stream_id=stream_id,
                organization_id=membership.organization_id,
            )
        except (
            StreamNotFoundError,
            StreamOwnershipError,
        ):
            pass

    def complete_answer(
        complete_text: str,
    ) -> str | None:
        if conversation is None:
            stream_cancellation_registry.mark_completed(
                stream_id=stream_id,
                organization_id=membership.organization_id,
            )
            return None

        assistant_message = add_conversation_message(
            db,
            conversation=conversation,
            role="assistant",
            content=complete_text,
            commit=False,
        )

        assign_automatic_conversation_title(
            db,
            conversation=conversation,
            provider=llm_provider,
            user_message=payload.question,
            assistant_message=complete_text,
        )

        db.commit()
        db.refresh(conversation)
        db.refresh(assistant_message)

        stream_cancellation_registry.mark_completed(
            stream_id=stream_id,
            organization_id=membership.organization_id,
        )

        return assistant_message.id

    def event_generator():
        try:
            yield from stream_answer_sse_events(
                answer_chunks=result.answer_chunks,
                citations=result.citations,
                conversation_id=conversation_id,
                complete_answer=complete_answer,
                stream_id=stream_id,
                is_cancelled=is_cancelled,
                cancel_answer=cancel_answer,
            )

        except GeneratorExit:
            try:
                stream_cancellation_registry.cancel(
                    stream_id=stream_id,
                    organization_id=membership.organization_id,
                )
            except (
                StreamNotFoundError,
                StreamOwnershipError,
            ):
                pass

            db.rollback()
            raise

        except RagGenerationError as exc:
            db.rollback()
            remove_failed_stream()

            yield encode_sse(
                "error",
                {
                    "detail": str(exc),
                },
            )

        except ConversationPersistenceError as exc:
            db.rollback()
            remove_failed_stream()

            yield encode_sse(
                "error",
                {
                    "detail": str(exc),
                },
            )

        except Exception:
            db.rollback()
            remove_failed_stream()

            yield encode_sse(
                "error",
                {
                    "detail": (
                        "Unable to complete the streamed document answer."
                    ),
                },
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

