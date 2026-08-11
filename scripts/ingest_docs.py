"""
scripts/ingest_docs.py - CLI Script for Document Ingestion into RAG Vector Store

Usage:
    python scripts/ingest_docs.py [--pdf-path path/to/file.pdf]
"""

import sys
import os
import argparse

# Add project root to python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv()

from chatbot.rag_service import ingest_pdf, DEFAULT_PDF_PATH
from common.logger import get_logger

logger = get_logger("ingest_docs")


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF documents into CityCare Clinic RAG Vector Store")
    parser.add_argument(
        "--pdf-path",
        type=str,
        default=DEFAULT_PDF_PATH,
        help="Path to PDF document to ingest (defaults to CityCare-Clinic-Patient-Handbook.pdf)",
    )
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not os.path.isabs(pdf_path):
        pdf_path = os.path.abspath(pdf_path)

    print(f"[RAG Ingestion] Target PDF Path: {pdf_path}")
    if not os.path.exists(pdf_path):
        print(f"[Error] File not found at '{pdf_path}'")
        sys.exit(1)

    try:
        count = ingest_pdf(pdf_path)
        print(f"[Success] Ingestion Complete! Indexed {count} document chunks into RAG vector store.")
    except Exception as err:
        print(f"[Error] Ingestion Failed: {err}")
        logger.error("Failed to ingest document", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
