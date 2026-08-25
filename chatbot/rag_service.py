"""
chatbot/rag_service.py - Retrieval-Augmented Generation (RAG) Core Service

Handles document ingestion, PDF chunking, embedding generation using Google Gemini,
and vector similarity search against ChromaDB (with MongoDB Atlas fallback support).
"""

import os
from typing import Any, Dict, List, Optional
from common.logger import get_logger

logger = get_logger(__name__)

# Constants
DEFAULT_PDF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "RAG",
    "CityCare-Clinic-Patient-Handbook.pdf",
)
def get_chroma_persist_dir() -> str:
    override = os.getenv("CHROMA_PERSIST_DIR")
    if override:
        return override
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "chroma_db",
    )


COLLECTION_NAME = "clinic_handbook"


def get_api_key() -> str:
    """Retrieve Google/Gemini API key from environment."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("Neither GEMINI_API_KEY nor GOOGLE_API_KEY set in environment.")
    return api_key or ""


def get_embeddings():
    """Returns GoogleGenerativeAIEmbeddings instance."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    api_key = get_api_key()
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY or GOOGLE_API_KEY for embedding generation.")

    model_name = os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-001")
    return GoogleGenerativeAIEmbeddings(model=model_name, api_key=api_key)


def get_vector_store():
    """
    Returns initialized vector store.
    Prioritizes ChromaDB persistent vector store for local development reliability.
    Falls back to MongoDBAtlasVectorSearch if MONGO_URL and Atlas index are present.
    """
    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma

    embeddings = get_embeddings()
    persist_dir = get_chroma_persist_dir()
    os.makedirs(persist_dir, exist_ok=True)

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    return vector_store


def ingest_pdf(pdf_path: str = DEFAULT_PDF_PATH) -> int:
    """
    Ingests and indexes a PDF document into the vector store.

    Args:
        pdf_path: Absolute or relative path to PDF file.

    Returns:
        int: Number of chunks indexed.
    """
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Target PDF file not found at path: {pdf_path}")

    logger.info("Starting PDF ingestion for: %s", pdf_path)
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    logger.info("Loaded %d pages from PDF", len(documents))

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    splits = text_splitter.split_documents(documents)
    logger.info("Split document into %d chunks", len(splits))

    vector_store = get_vector_store()
    inserted_ids = vector_store.add_documents(splits)
    logger.info("Successfully indexed %d chunks into ChromaDB collection '%s'", len(inserted_ids), COLLECTION_NAME)
    return len(inserted_ids)


def search_handbook(query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Performs similarity search in patient handbook vector index.

    Args:
        query: Natural language question or search query string.
        top_k: Number of relevant chunks to retrieve.

    Returns:
        Dict: Contains retrieved chunks, source metadata, and formatted summary string.
    """
    try:
        vector_store = get_vector_store()
        results = vector_store.similarity_search_with_score(query, k=top_k)

        if not results:
            # Check if vector store is empty, attempt auto-ingestion of default PDF
            if os.path.exists(DEFAULT_PDF_PATH):
                logger.info("Vector store empty during search. Attempting auto-ingestion of default handbook...")
                try:
                    ingest_pdf(DEFAULT_PDF_PATH)
                    results = vector_store.similarity_search_with_score(query, k=top_k)
                except Exception as ingest_err:
                    logger.error("Auto-ingestion failed: %s", str(ingest_err))

        snippets: List[Dict[str, Any]] = []
        formatted_texts: List[str] = []

        for doc, score in results:
            page_num = doc.metadata.get("page", 0) + 1
            source_file = os.path.basename(doc.metadata.get("source", "Patient Handbook"))
            content = doc.page_content.strip()

            snippets.append({
                "page": page_num,
                "source": source_file,
                "score": float(score) if hasattr(score, "__float__") else str(score),
                "text": content,
            })
            formatted_texts.append(f"[Source: {source_file}, Page {page_num}]\n{content}")

        summary_text = "\n\n---\n\n".join(formatted_texts) if formatted_texts else "No matching information found in the handbook."

        return {
            "query": query,
            "total_results": len(snippets),
            "snippets": snippets,
            "context": summary_text,
        }

    except Exception as err:
        logger.error("RAG search failed for query '%s': %s", query, str(err), exc_info=True)
        return {
            "query": query,
            "total_results": 0,
            "snippets": [],
            "context": f"Error querying handbook: {str(err)}",
            "error": str(err),
        }


def ingest_prescription_doc(prescription) -> bool:
    """
    Ingests a PrescriptionModel instance into the RAG vector store for semantic search.

    Args:
        prescription: PrescriptionModel instance.

    Returns:
        bool: True if ingestion succeeded.
    """
    try:
        from langchain_core.documents import Document

        p_id = str(prescription.id)
        meds_text = []
        for m in prescription.medications:
            med_line = (
                f"• {m.get('medicine_name', '')}: Dosage={m.get('dosage', '')}, "
                f"Frequency={m.get('frequency', '')}, Duration={m.get('duration', '')}, "
                f"Instructions={m.get('instructions', 'None')}"
            )
            meds_text.append(med_line)

        content = (
            f"MEDICAL PRESCRIPTION RECORD\n"
            f"Prescription ID: {p_id}\n"
            f"Patient ID: {prescription.patient_id}\n"
            f"Patient Name: {prescription.patient_name}\n"
            f"Doctor Name: {prescription.doctor_name}\n"
            f"Issuance Date: {prescription.date}\n"
            f"Diagnosis: {prescription.diagnosis}\n\n"
            f"Prescribed Medications:\n" + "\n".join(meds_text) + "\n\n"
            f"Doctor Advice / Notes: {prescription.notes or 'None'}\n"
            f"Follow-up Date: {prescription.follow_up_date or 'Not specified'}\n"
        )

        doc = Document(
            page_content=content,
            metadata={
                "patient_id": str(prescription.patient_id),
                "prescription_id": p_id,
                "type": "prescription",
                "source": "Medical Prescription",
            },
        )

        vector_store = get_vector_store()
        vector_store.add_documents([doc])
        logger.info("Successfully ingested prescription ID %s into ChromaDB for patient %s", p_id, prescription.patient_id)
        return True
    except Exception as err:
        logger.error("Failed to ingest prescription into RAG vector store: %s", str(err), exc_info=True)
        return False


def search_prescriptions_rag(query: str, patient_id: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Searches patient's prescriptions using RAG vector similarity search,
    scoped strictly to the specified patient_id.

    Args:
        query: Patient's natural language question (e.g. 'what is my dosage for fever?').
        patient_id: Patient UserModel ObjectId string.
        top_k: Max results to retrieve.

    Returns:
        Dict: Context summary string and prescription snippets.
    """
    try:
        vector_store = get_vector_store()

        # ChromaDB filtering by patient_id metadata
        try:
            results = vector_store.similarity_search_with_score(
                query, k=top_k, filter={"patient_id": patient_id}
            )
        except Exception:
            # Fallback if filter argument syntax varies
            all_results = vector_store.similarity_search_with_score(query, k=top_k * 3)
            results = [r for r in all_results if r[0].metadata.get("patient_id") == patient_id][:top_k]

        snippets = []
        formatted_texts = []

        for doc, score in results:
            content = doc.page_content.strip()
            snippets.append({
                "prescription_id": doc.metadata.get("prescription_id", ""),
                "score": float(score) if hasattr(score, "__float__") else str(score),
                "text": content,
            })
            formatted_texts.append(content)

        summary_text = "\n\n---\n\n".join(formatted_texts) if formatted_texts else "No matching prescription details found."

        return {
            "query": query,
            "patient_id": patient_id,
            "total_results": len(snippets),
            "snippets": snippets,
            "context": summary_text,
        }
    except Exception as err:
        logger.error("Prescription RAG search failed for patient '%s': %s", patient_id, str(err), exc_info=True)
        return {
            "query": query,
            "patient_id": patient_id,
            "total_results": 0,
            "snippets": [],
            "context": f"Error searching prescription records: {str(err)}",
            "error": str(err),
        }

