from collections.abc import Iterator, Sequence

from sqlalchemy.orm import Session

from app.documents.conversation_memory import (
    ConversationMemoryValidationError,
    build_conversation_context,
)
from app.documents.conversation_types import (
    ConversationHistoryMessage,
)
from app.documents.embeddings import EmbeddingProvider
from app.documents.rag import (
    AnswerCitation,
    AnswerGenerator,
    GeneratedAnswer,
    StreamingAnswerGenerator,
    StreamingGeneratedAnswer,
)
from app.documents.retrieval import (
    ChunkSearchStore,
    RetrievedChunk,
)
from app.documents.retrieval_service import (
    RetrievalEmbeddingError,
    RetrievalValidationError,
    search_document_chunks,
)


INSUFFICIENT_CONTEXT_ANSWER = (
    "I could not find enough relevant information "
    "in the selected documents."
)


class RagValidationError(ValueError):
    """Raised when a document-answer request is invalid."""


class RagGenerationError(RuntimeError):
    """Raised when answer generation fails or returns invalid output."""


class RagRetrievalError(RuntimeError):
    """Raised when document retrieval cannot be completed."""


def _deduplicate_chunks(
    chunks: Sequence[RetrievedChunk],
) -> list[RetrievedChunk]:
    """
    Remove chunks with identical normalized content.

    The original retrieval order is preserved so the best-ranked duplicate
    remains available for generation and citation.
    """

    unique_chunks: list[RetrievedChunk] = []
    seen_content: set[str] = set()

    for chunk in chunks:
        normalized_content = " ".join(
            chunk.content.casefold().split()
        )

        if not normalized_content:
            continue

        if normalized_content in seen_content:
            continue

        seen_content.add(normalized_content)
        unique_chunks.append(chunk)

    return unique_chunks


def _validate_conversation_history(
    history: Sequence[ConversationHistoryMessage],
) -> None:
    """
    Validate history received from the conversation persistence layer.
    """

    if len(history) > 100:
        raise RagValidationError(
            "Conversation history must not exceed 100 messages."
        )

    for message in history:
        if message.role not in {"user", "assistant"}:
            raise RagValidationError(
                "Conversation history contains an unsupported role."
            )

        if not message.content.strip():
            raise RagValidationError(
                "Conversation history contains an empty message."
            )


def _validate_answer_request(
    *,
    question: str,
    limit: int,
    document_id: str | None,
    document_version_id: str | None,
    conversation_history: Sequence[
        ConversationHistoryMessage
    ],
) -> tuple[str, list[ConversationHistoryMessage]]:
    normalized_question = question.strip()

    if not normalized_question:
        raise RagValidationError(
            "Question must not be empty."
        )

    if len(normalized_question) > 10_000:
        raise RagValidationError(
            "Question must not exceed 10000 characters."
        )

    if limit < 1:
        raise RagValidationError(
            "Context limit must be at least 1."
        )

    if limit > 20:
        raise RagValidationError(
            "Context limit must not exceed 20."
        )

    if document_version_id and not document_id:
        raise RagValidationError(
            "document_id is required when document_version_id is supplied."
        )

    _validate_conversation_history(conversation_history)

    try:
        prepared_history = build_conversation_context(
            conversation_history,
        )
    except ConversationMemoryValidationError as exc:
        raise RagValidationError(str(exc)) from exc

    return normalized_question, prepared_history


def _retrieve_document_context(
    db: Session,
    *,
    question: str,
    organization_id: str,
    embedding_provider: EmbeddingProvider,
    search_store: ChunkSearchStore,
    limit: int,
    document_id: str | None,
    document_version_id: str | None,
) -> list[RetrievedChunk]:
    try:
        chunks = search_document_chunks(
            db,
            query=question,
            organization_id=organization_id,
            provider=embedding_provider,
            store=search_store,
            limit=limit,
            document_id=document_id,
            document_version_id=document_version_id,
        )

    except RetrievalValidationError as exc:
        raise RagValidationError(str(exc)) from exc

    except RetrievalEmbeddingError as exc:
        raise RagRetrievalError(
            "Unable to create the query embedding."
        ) from exc

    except Exception as exc:
        raise RagRetrievalError(
            "Unable to retrieve relevant document context."
        ) from exc

    return _deduplicate_chunks(chunks)


def _build_citations(
    chunks: Sequence[RetrievedChunk],
) -> list[AnswerCitation]:
    return [
        AnswerCitation(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_version_id=chunk.document_version_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=chunk.score,
        )
        for chunk in chunks
    ]


def generate_document_answer(
    db: Session,
    *,
    question: str,
    organization_id: str,
    embedding_provider: EmbeddingProvider,
    search_store: ChunkSearchStore,
    answer_generator: AnswerGenerator,
    limit: int = 5,
    document_id: str | None = None,
    document_version_id: str | None = None,
    conversation_history: Sequence[
        ConversationHistoryMessage
    ] = (),
) -> GeneratedAnswer:
    """
    Retrieve relevant document chunks and generate a complete grounded answer.
    """

    normalized_question, prepared_history = _validate_answer_request(
        question=question,
        limit=limit,
        document_id=document_id,
        document_version_id=document_version_id,
        conversation_history=conversation_history,
    )

    unique_chunks = _retrieve_document_context(
        db,
        question=normalized_question,
        organization_id=organization_id,
        embedding_provider=embedding_provider,
        search_store=search_store,
        limit=limit,
        document_id=document_id,
        document_version_id=document_version_id,
    )

    if not unique_chunks:
        return GeneratedAnswer(
            answer=INSUFFICIENT_CONTEXT_ANSWER,
            citations=[],
        )

    try:
        generated_text = answer_generator.generate_answer(
            question=normalized_question,
            context_chunks=unique_chunks,
            conversation_history=prepared_history,
        )

    except Exception as exc:
        raise RagGenerationError(
            "Failed to generate a document answer."
        ) from exc

    if not isinstance(generated_text, str):
        raise RagGenerationError(
            "Answer generator returned an invalid response."
        )

    answer = generated_text.strip()

    if not answer:
        raise RagGenerationError(
            "Answer generator returned an empty answer."
        )

    return GeneratedAnswer(
        answer=answer,
        citations=_build_citations(unique_chunks),
    )


def generate_document_answer_stream(
    db: Session,
    *,
    question: str,
    organization_id: str,
    embedding_provider: EmbeddingProvider,
    search_store: ChunkSearchStore,
    answer_generator: StreamingAnswerGenerator,
    limit: int = 5,
    document_id: str | None = None,
    document_version_id: str | None = None,
    conversation_history: Sequence[
        ConversationHistoryMessage
    ] = (),
) -> StreamingGeneratedAnswer:
    """
    Retrieve document context and return a lazy grounded-answer stream.

    Retrieval and request validation happen immediately. LLM generation begins
    only when the caller consumes answer_chunks.
    """

    normalized_question, prepared_history = _validate_answer_request(
        question=question,
        limit=limit,
        document_id=document_id,
        document_version_id=document_version_id,
        conversation_history=conversation_history,
    )

    unique_chunks = _retrieve_document_context(
        db,
        question=normalized_question,
        organization_id=organization_id,
        embedding_provider=embedding_provider,
        search_store=search_store,
        limit=limit,
        document_id=document_id,
        document_version_id=document_version_id,
    )

    if not unique_chunks:
        return StreamingGeneratedAnswer(
            answer_chunks=iter([INSUFFICIENT_CONTEXT_ANSWER]),
            citations=[],
        )

    def validated_answer_chunks() -> Iterator[str]:
        emitted_text = False

        try:
            chunks = answer_generator.stream_answer(
                question=normalized_question,
                context_chunks=unique_chunks,
                conversation_history=prepared_history,
            )

            for chunk in chunks:
                if not isinstance(chunk, str):
                    raise RagGenerationError(
                        "Answer generator streamed an invalid response."
                    )

                if not chunk:
                    continue

                emitted_text = True
                yield chunk

        except RagGenerationError:
            raise

        except Exception as exc:
            raise RagGenerationError(
                "Failed to generate a streamed document answer."
            ) from exc

        if not emitted_text:
            raise RagGenerationError(
                "Answer generator returned an empty streamed answer."
            )

    return StreamingGeneratedAnswer(
        answer_chunks=validated_answer_chunks(),
        citations=_build_citations(unique_chunks),
    )
