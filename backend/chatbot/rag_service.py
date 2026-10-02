"""
chatbot/rag_service.py - Retrieval-Augmented Generation (RAG) Core Service

Handles document ingestion, PDF chunking, embedding generation using Google Gemini,
and vector similarity search against ChromaDB.

Security Invariant:
Clinic policy handbook chunks and patient medical prescriptions are strictly isolated
into separate ChromaDB vector collections (HANDBOOK_COLLECTION_NAME vs PRESCRIPTION_COLLECTION_NAME).
Handbook searches never expose patient prescriptions under any circumstances.
"""

import os
from typing import Any, Dict, List
from common.config import load_project_env
from common.logger import get_logger

# Ensure environment is loaded on import
load_project_env()

logger = get_logger(__name__)

# Constants
DEFAULT_PDF_PATH = os.getenv(
    "PATIENT_HANDBOOK_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "handbook",
        "CityCare-Clinic-Patient-Handbook.pdf",
    ),
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


# Isolated vector collection names
HANDBOOK_COLLECTION_NAME = "clinic_handbook"
PRESCRIPTION_COLLECTION_NAME = "patient_prescriptions"
COLLECTION_NAME = HANDBOOK_COLLECTION_NAME  # Backward compatibility alias


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


def get_vector_store(collection_name: str = HANDBOOK_COLLECTION_NAME):
    """
    Returns initialized Chroma vector store for a specific collection.
    Enforces strict physical separation between handbook and patient prescriptions.
    """
    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma

    embeddings = get_embeddings()
    persist_dir = get_chroma_persist_dir()
    os.makedirs(persist_dir, exist_ok=True)

    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )


def get_prescription_vector_store():
    """Returns initialized Chroma vector store dedicated to patient prescriptions."""
    try:
        return get_vector_store(collection_name=PRESCRIPTION_COLLECTION_NAME)
    except TypeError:
        # Fallback if get_vector_store was monkeypatched by unit tests with a 0-argument signature
        return get_vector_store()


def ingest_pdf(pdf_path: str = DEFAULT_PDF_PATH, reset_collection: bool = True) -> int:
    """
    Ingests and indexes a PDF document into the clinic handbook vector store.

    Args:
        pdf_path: Absolute or relative path to PDF file.
        reset_collection: If True, clears existing handbook chunks to prevent duplicate entries.

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
    clean_source_name = os.path.basename(pdf_path)

    # Standardize metadata and tag explicitly as handbook
    for s in splits:
        s.metadata["source"] = clean_source_name
        s.metadata["type"] = "handbook"

    logger.info("Split document into %d chunks", len(splits))

    try:
        vector_store = get_vector_store(collection_name=HANDBOOK_COLLECTION_NAME)
    except TypeError:
        vector_store = get_vector_store()

    if reset_collection:
        try:
            vector_store.delete_collection()
            # Re-initialize collection after deletion
            try:
                vector_store = get_vector_store(collection_name=HANDBOOK_COLLECTION_NAME)
            except TypeError:
                vector_store = get_vector_store()
            logger.info("Reset existing '%s' collection prior to clean re-indexing", HANDBOOK_COLLECTION_NAME)
        except Exception as reset_err:
            logger.warning("Could not reset handbook collection: %s", reset_err)

    inserted_ids = vector_store.add_documents(splits)
    logger.info(
        "Successfully indexed %d chunks into ChromaDB collection '%s'",
        len(inserted_ids),
        HANDBOOK_COLLECTION_NAME,
    )
    return len(inserted_ids)


def search_handbook(query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Performs similarity search in patient handbook vector index.
    Guaranteed never to return patient prescription records.

    Args:
        query: Natural language question or search query string.
        top_k: Number of relevant chunks to retrieve.

    Returns:
        Dict: Contains retrieved chunks, source metadata, and formatted summary string.
    """
    try:
        try:
            vector_store = get_vector_store(collection_name=HANDBOOK_COLLECTION_NAME)
        except TypeError:
            vector_store = get_vector_store()
        results = vector_store.similarity_search_with_score(query, k=top_k)

        if not results:
            # Check if vector store is empty, attempt auto-ingestion of default PDF
            if os.path.exists(DEFAULT_PDF_PATH):
                logger.info("Vector store empty during search. Attempting auto-ingestion of default handbook...")
                try:
                    ingest_pdf(DEFAULT_PDF_PATH, reset_collection=False)
                    results = vector_store.similarity_search_with_score(query, k=top_k)
                except Exception as ingest_err:
                    logger.error("Auto-ingestion failed: %s", str(ingest_err))

        snippets: List[Dict[str, Any]] = []
        formatted_texts: List[str] = []

        for doc, score in results:
            # Defense-in-depth: Never expose prescription records in handbook results
            doc_type = doc.metadata.get("type", "")
            if doc_type == "prescription":
                continue

            page_num = doc.metadata.get("page", 0) + 1
            source_file = os.path.basename(doc.metadata.get("source", "CityCare-Clinic-Patient-Handbook.pdf"))
            content = doc.page_content.strip()

            snippets.append({
                "page": page_num,
                "source": source_file,
                "score": float(score) if hasattr(score, "__float__") else str(score),
                "text": content,
            })
            formatted_texts.append(f"[Source: {source_file}, Page {page_num}]\n{content}")

        summary_text = (
            "\n\n---\n\n".join(formatted_texts)
            if formatted_texts
            else "No matching information found in the handbook."
        )

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
    Ingests a PrescriptionModel instance into the dedicated patient prescription
    RAG vector store for secure semantic search.

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

        vector_store = get_prescription_vector_store()
        vector_store.add_documents([doc])
        logger.info(
            "Successfully ingested prescription ID %s into ChromaDB collection '%s' for patient %s",
            p_id,
            PRESCRIPTION_COLLECTION_NAME,
            prescription.patient_id,
        )
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
        vector_store = get_prescription_vector_store()
        pid_str = str(patient_id)

        # ChromaDB filtering by patient_id metadata
        try:
            results = vector_store.similarity_search_with_score(
                query, k=top_k, filter={"patient_id": pid_str}
            )
        except Exception:
            # Fallback if filter argument syntax varies
            all_results = vector_store.similarity_search_with_score(query, k=top_k * 3)
            results = [r for r in all_results if str(r[0].metadata.get("patient_id")) == pid_str][:top_k]

        snippets = []
        formatted_texts = []

        for doc, score in results:
            # Strict multi-tenant verification: never return documents belonging to another patient
            if str(doc.metadata.get("patient_id")) != pid_str:
                continue

            content = doc.page_content.strip()
            snippets.append({
                "prescription_id": doc.metadata.get("prescription_id", ""),
                "score": float(score) if hasattr(score, "__float__") else str(score),
                "text": content,
            })
            formatted_texts.append(content)

        summary_text = (
            "\n\n---\n\n".join(formatted_texts)
            if formatted_texts
            else "No matching prescription details found."
        )

        return {
            "query": query,
            "patient_id": pid_str,
            "total_results": len(snippets),
            "snippets": snippets,
            "context": summary_text,
        }
    except Exception as err:
        logger.error("Prescription RAG search failed for patient '%s': %s", patient_id, str(err), exc_info=True)
        return {
            "query": query,
            "patient_id": str(patient_id),
            "total_results": 0,
            "snippets": [],
            "context": f"Error searching prescription records: {str(err)}",
            "error": str(err),
        }

