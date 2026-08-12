"""Grounded, text-mode prescription Q&A for manual safety validation."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from chatbot.prescription_assistant import (
    EMERGENCY_RESPONSE,
    MEDICAL_ADVICE_RESPONSE,
    PrescriptionAnswer,
    answer_question,
    is_emergency_message,
    is_medical_advice_request,
)


# The FastAPI application loads this file during startup. The CLI runs outside
# that lifecycle, so it loads the same project-level configuration explicitly.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def run_repl(patient_id: str, top_k: int = 3) -> None:
    """Run an interactive, patient-scoped prescription question loop."""
    print("CityCare prescription Q&A. Type 'exit' or 'quit' to end.")
    while True:
        try:
            question = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if question.casefold() in {"exit", "quit"}:
            print("Goodbye.")
            return
        if not question:
            continue

        result = answer_question(patient_id=patient_id, question=question, top_k=top_k)
        print(f"\nAnswer:\n{result.answer}\n\nRetrieved sources:\n{result.sources}")
