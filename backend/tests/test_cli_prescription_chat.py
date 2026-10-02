from chatbot.prescription_assistant import (
    EMERGENCY_RESPONSE,
    MEDICAL_ADVICE_RESPONSE,
    NON_PRESCRIPTION_RESPONSE,
    answer_from_prescription_records,
    answer_question,
)


def test_emergency_message_bypasses_retrieval_and_llm(monkeypatch):
    monkeypatch.setattr(
        "chatbot.prescription_assistant.search_prescriptions_rag",
        lambda **_: (_ for _ in ()).throw(AssertionError("Retrieval must not run for emergency messages")),
    )

    result = answer_question("patient-123", "I have chest pain and cannot breathe")

    assert result.emergency is True
    assert result.answer == EMERGENCY_RESPONSE


def test_medical_advice_message_bypasses_retrieval_and_llm(monkeypatch):
    monkeypatch.setattr(
        "chatbot.prescription_assistant.search_prescriptions_rag",
        lambda **_: (_ for _ in ()).throw(AssertionError("Retrieval must not run for advice messages")),
    )

    result = answer_question("patient-123", "Which medicine should I take for fever?")

    assert result.medical_advice is True
    assert result.answer == MEDICAL_ADVICE_RESPONSE


def test_prescription_listing_question_is_not_medical_advice(monkeypatch):
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda *_: (_ for _ in ()).throw(AssertionError("Listing must not need LLM generation")),
    )

    result = answer_from_prescription_records(
        "Which prescriptions do I have?",
        [
            {
                "id": "rx-list-123",
                "date": "2026-08-12",
                "doctor_name": "Dr. Prescription",
                "diagnosis": "Viral fever",
                "medications": [
                    {
                        "medicine_name": "paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "3 days",
                    }
                ],
                "follow_up_date": "2026-08-19",
            }
        ],
    )

    assert result.medical_advice is False
    assert result.answer != MEDICAL_ADVICE_RESPONSE
    assert "I found 1 CityCare prescription record" in result.answer
    assert "Prescription 1 - 2026-08-12" in result.answer
    assert "Doctor: Dr. Prescription" in result.answer
    assert "Medicines documented: Paracetamol (500mg)" in result.answer
    assert "rx-list-123" in result.answer


def test_specific_medicine_timing_question_only_returns_matching_medicine(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Specific medicine timing questions should not need LLM generation")
        ),
    )

    result = answer_from_prescription_records(
        "what is timing for neend ki goli",
        [
            {
                "id": "rx-specific-123",
                "date": "2026-08-13",
                "doctor_name": "Rudra Dalal",
                "diagnosis": "man ki bimari",
                "medications": [
                    {
                        "medicine_name": "paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "5 days",
                        "instructions": "khane ke phele",
                    },
                    {
                        "medicine_name": "neend ki goli",
                        "dosage": "5mg",
                        "frequency": "0-0-1 before sleeping",
                        "duration": "5 days",
                        "instructions": "raat ko sone se phle",
                    },
                ],
            }
        ],
    )

    assert "Neend Ki Goli" in result.answer
    assert "Dose: 5mg" in result.answer
    assert "Timing: Morning: none; Afternoon: none; Night: 1 dose" in result.answer
    assert "Meal timing from prescription: before sleeping" in result.answer
    assert "Doctor instruction as written: raat ko sone se phle" in result.answer
    assert "Paracetamol" not in result.answer
    assert "Diagnosis written" not in result.answer
    assert "rx-specific-123" not in result.answer


def test_unknown_medicine_detail_question_does_not_dump_full_prescription(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Unknown medicine detail questions should not need LLM generation")
        ),
    )

    result = answer_from_prescription_records(
        "timing for xyz medicine",
        [
            {
                "id": "rx-specific-123",
                "date": "2026-08-13",
                "doctor_name": "Rudra Dalal",
                "diagnosis": "viral",
                "medications": [
                    {
                        "medicine_name": "paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "5 days",
                    }
                ],
            }
        ],
    )

    assert "I could not find a medicine matching that name" in result.answer
    assert "Available medicines documented: Paracetamol" in result.answer
    assert "Diagnosis written" not in result.answer
    assert "Prescription ID" not in result.answer


def test_follow_up_question_uses_gemini_when_api_key_available(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("PRESCRIPTION_AI_USE_GEMINI", raising=False)
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda question, sources: "Gemini answer: your follow-up date is 2026-08-20.",
    )

    result = answer_from_prescription_records(
        "when do i have to show to doctor again",
        [
            {
                "id": "rx-follow-up",
                "date": "2026-08-13",
                "doctor_name": "Rudra Dalal",
                "diagnosis": "viral",
                "medications": [
                    {
                        "medicine_name": "paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "5 days",
                    }
                ],
                "follow_up_date": "2026-08-20",
            }
        ],
    )

    assert result.medical_advice is False
    assert result.answer == "Gemini answer: your follow-up date is 2026-08-20."


def test_follow_up_question_has_clean_structured_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Prescription AI should not call Gemini without an API key")
        ),
    )

    result = answer_from_prescription_records(
        "when do i have to show to doctor again",
        [
            {
                "id": "rx-follow-up",
                "date": "2026-08-13",
                "doctor_name": "Rudra Dalal",
                "diagnosis": "viral",
                "medications": [
                    {
                        "medicine_name": "paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "5 days",
                    }
                ],
                "follow_up_date": "2026-08-20",
            }
        ],
    )

    assert "Follow-up: 2026-08-20" in result.answer
    assert "Paracetamol" not in result.answer
    assert result.answer != MEDICAL_ADVICE_RESPONSE


def test_non_prescription_message_does_not_dump_prescription_records(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Small talk should not be answered from prescription records")
        ),
    )

    result = answer_from_prescription_records(
        "how are you",
        [
            {
                "id": "rx-small-talk",
                "date": "2026-08-12",
                "doctor_name": "Dr. Prescription",
                "diagnosis": "Viral fever",
                "medications": [
                    {
                        "medicine_name": "Paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "3 days",
                    }
                ],
            }
        ],
    )

    assert result.answer == NON_PRESCRIPTION_RESPONSE
    assert "Paracetamol" not in result.answer
    assert "dosage and timing exactly" not in result.answer


def test_prescription_records_use_structured_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("PRESCRIPTION_AI_USE_GEMINI", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("Prescription AI should not call Gemini without an API key")
        ),
    )

    result = answer_from_prescription_records(
        "Explain my dosage and timing",
        [
            {
                "id": "rx-default-structured",
                "date": "2026-08-12",
                "doctor_name": "Dr. Prescription",
                "diagnosis": "Viral fever",
                "medications": [
                    {
                        "medicine_name": "Paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "3 days",
                        "instructions": "After food",
                    }
                ],
            }
        ],
    )

    assert "Paracetamol" in result.answer
    assert "Timing: Morning: 1 dose; Afternoon: none; Night: 1 dose" in result.answer
    assert "Meal timing from prescription: after meals" in result.answer


def test_prescription_records_use_gemini_when_api_key_available(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("PRESCRIPTION_AI_USE_GEMINI", raising=False)
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda question, sources: (
            "Gemini grounded answer: your prescription record lists Paracetamol."
        ),
    )

    result = answer_from_prescription_records(
        "What is written in my prescription?",
        [
            {
                "id": "rx-gemini",
                "date": "2026-08-12",
                "doctor_name": "Dr. Prescription",
                "diagnosis": "Viral fever",
                "medications": [
                    {
                        "medicine_name": "Paracetamol",
                        "dosage": "500mg",
                        "frequency": "1-0-1 after meals",
                        "duration": "3 days",
                    }
                ],
            }
        ],
    )

    assert result.answer == (
        "Gemini grounded answer: your prescription record lists Paracetamol."
    )


def test_answer_displays_numbered_prescription_sources(monkeypatch):
    monkeypatch.setattr(
        "chatbot.prescription_assistant.search_prescriptions_rag",
        lambda **_: {
            "snippets": [
                {
                    "prescription_id": "rx-123",
                    "text": "MEDICAL PRESCRIPTION RECORD\nMedicine: Paracetamol\nFrequency: Twice daily",
                }
            ]
        },
    )
    monkeypatch.setattr(
        "chatbot.prescription_assistant._generate_grounded_answer",
        lambda question, sources: "Take it as documented [Prescription rx-123, line 2].",
    )

    result = answer_question("patient-123", "What is my medicine?")

    assert result.emergency is False
    assert "Prescription rx-123" in result.sources
    assert "1. MEDICAL PRESCRIPTION RECORD" in result.sources
    assert "2. Medicine: Paracetamol" in result.sources


def test_generation_failure_does_not_expose_internal_error(monkeypatch):
    monkeypatch.setattr(
        "chatbot.prescription_assistant.search_prescriptions_rag",
        lambda **_: {"snippets": [{"prescription_id": "rx-123", "text": "Medicine: Paracetamol"}]},
    )

    def fail_generation(*_):
        raise RuntimeError("private service diagnostic")

    monkeypatch.setattr("chatbot.prescription_assistant._generate_grounded_answer", fail_generation)

    result = answer_question("patient-123", "What is my medicine?")

    assert result.answer == "I could not prepare a grounded answer. Please consult your prescribing doctor."
    assert "private service diagnostic" not in result.answer
