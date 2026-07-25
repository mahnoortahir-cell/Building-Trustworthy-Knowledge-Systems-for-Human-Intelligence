from collections.abc import Sequence

from app.documents.retrieval import RetrievedChunk


SYSTEM_PROMPT = """
You are a document question-answering assistant.

Answer only from the supplied document context.

Rules:
- Do not invent information.
- Do not use outside knowledge.
- If the context is insufficient, say that the documents do not contain enough information.
- Give a clear and concise answer.
- Do not copy large passages verbatim.
- Do not mention chunk IDs or retrieval scores.
""".strip()


def build_document_answer_prompt(
    *,
    question: str,
    context_chunks: Sequence[RetrievedChunk],
) -> tuple[str, str]:
    context_sections = []

    for index, chunk in enumerate(context_chunks, start=1):
        cleaned_content = " ".join(chunk.content.split())

        context_sections.append(
            f"[Source {index}]\n{cleaned_content}"
        )

    context = "\n\n".join(context_sections)

    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Document context:\n{context}\n\n"
        "Provide a grounded answer based only on the document context."
    )

    return SYSTEM_PROMPT, user_prompt