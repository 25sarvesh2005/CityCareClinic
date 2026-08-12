"""Patient-scoped prescription question answering with medical safety guards."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from chatbot.rag_service import search_prescriptions_rag


EMERGENCY_RESPONSE = (
    "This may be an emergency. Please call 108 now or go to the nearest emergency "
    "department. CityCare Clinic is not an emergency facility."
)

MEDICAL_ADVICE_RESPONSE = (
    "I can explain what is written in your existing CityCare prescription records, "
    "but I cannot diagnose symptoms, choose a treatment, change a dose, or tell you "
    "whether a medicine is safe for you. Please consult your prescribing doctor."
)

NON_PRESCRIPTION_RESPONSE = (
    "Hey, I’m here and ready to help. I can explain medicines, dosage, timing, "
    "duration, doctor instructions, notes, and follow-up dates from your CityCare "
    "prescription records. What would you like me to check?"
)

EMERGENCY_PATTERNS = (
    r"\bchest pain\b",
    r"\b(can(?:not|'t)|unable to) breathe\b",
    r"\b(shortness of breath|breathless(?:ness)?)\b",
    r"\bsevere bleeding\b",
    r"\bbleeding (heavily|a lot|won't stop)\b",
    r"\b(suicidal|want to die|kill myself|self[- ]harm)\b",
    r"\b(sudden weakness|face droop|facial deviation|difficulty speaking)\b",
)

MEDICAL_ADVICE_PATTERNS = (
    r"\bwhat (medicine|tablet|drug|treatment) should i\b",
    r"\bwhich (medicine|tablet|drug|treatment) should i\b",
    r"\b(should|can|may) i (take|stop|start|increase|decrease|change)\b",
    r"\b(recommend|suggest) (a |any )?(medicine|tablet|drug|treatment|dose)\b",
    r"\bdiagnose\b",
    r"\bdo i have\b.{0,48}\b(disease|condition|infection|cancer|diabetes|hypertension|fever|covid|flu|allergy|problem)\b",
    r"\btreatment for\b",
    r"\bis it safe for me\b",
    r"\bside effects?\b",
    r"\bdrug interactions?\b",
)

PRESCRIPTION_LIST_PATTERNS = (
    r"\b(which|list|show|display|view|find|tell me)\b.{0,48}\b(prescriptions?|prescription records?|records?|rx|documents?)\b",
    r"\b(prescriptions?|prescription records?|records?|rx|documents?)\b.{0,48}\b(do i have|for me|in my account|available|issued)\b",
)

MEDICATION_DETAIL_PATTERNS = (
    r"\b(timing|time|when|schedule|frequency|dose|dosage|duration|instruction|instructions)\b",
    r"\b(medicine|medicines|tablet|tablets|drug|drugs|goli|syrup|capsule|capsules)\b",
)

MEDICINE_NOUN_PATTERN = (
    r"\b(medicine|medicines|medication|medications|tablet|tablets|drug|drugs|"
    r"goli|syrup|capsule|capsules|pill|pills)\b"
)

FOLLOW_UP_PATTERNS = (
    r"\bfollow[- ]?up\b",
    r"\b(see|show|visit|meet|go to|consult)\b.{0,40}\bdoctor\b.{0,40}\bagain\b",
    r"\bdoctor\b.{0,40}\bagain\b",
    r"\bnext\b.{0,24}\b(visit|appointment|consultation|doctor)\b",
)

PRESCRIPTION_TOPIC_PATTERNS = (
    r"\b(prescriptions?|prescribed|prescription records?|rx|records?)\b",
    r"\b(medicines?|medications?|tablets?|drugs?|goli|syrup|capsules?|pills?)\b",
    r"\b(dose|dosage|timing|frequency|duration|instructions?|notes?|follow[- ]?up)\b",
    r"\b(diagnosis|doctor advice|doctor note|pdf|document)\b",
    *FOLLOW_UP_PATTERNS,
    r"\b(what did (the )?doctor (give|write|prescribe))\b",
    r"\b(what (was|is) (given|written|prescribed))\b",
)

QUESTION_STOPWORDS = {
    "a",
    "about",
    "again",
    "am",
    "and",
    "are",
    "available",
    "bata",
    "batao",
    "can",
    "do",
    "does",
    "dose",
    "dosage",
    "document",
    "documented",
    "documents",
    "drug",
    "drugs",
    "duration",
    "explain",
    "for",
    "frequency",
    "get",
    "give",
    "given",
    "got",
    "hai",
    "he",
    "has",
    "have",
    "i",
    "in",
    "instruction",
    "instructions",
    "is",
    "listed",
    "ka",
    "ke",
    "ki",
    "kya",
    "me",
    "need",
    "medicine",
    "medicines",
    "mera",
    "mere",
    "meri",
    "my",
    "of",
    "on",
    "please",
    "pls",
    "record",
    "records",
    "schedule",
    "should",
    "tablet",
    "tablets",
    "take",
    "taking",
    "tell",
    "the",
    "to",
    "time",
    "timing",
    "what",
    "when",
    "which",
    "with",
    "written",
}

SYSTEM_PROMPT = """You are the CityCare Clinic prescription Q&A assistant.

You may only relay or explain information explicitly present in the retrieved
prescription records below. Never invent, infer, or recommend a new dose,
frequency, duration, diagnosis, treatment, medicine substitution, side effect,
or drug interaction. If the answer is not explicitly documented, say that it is
not shown in the prescription and ask the patient to consult the prescribing
doctor. Do not diagnose symptoms or provide new medical advice.

Use a short, clean, empathetic response. Do not dump every prescription unless
the patient clearly asks to see all prescription details. If the patient asks
about one medicine, answer only that medicine. Prefer this readable format when
details are available:

Medicine: <name>
Dose: <dose written>
Timing: <timing/frequency written, explained plainly if obvious>
Meal timing from prescription: <only if written>
Duration: <duration written>
Doctor instruction as written: <instruction written>

Do not show raw prescription IDs unless the patient asks for IDs.
"""


@dataclass(frozen=True)
class PrescriptionAnswer:
    """Visible result of one validated prescription-Q&A turn."""

    answer: str
    sources: str
    emergency: bool = False
    medical_advice: bool = False


def is_emergency_message(message: str) -> bool:
    """Return True when a message requires the fixed emergency response."""
    normalized = message.casefold()
    return any(re.search(pattern, normalized) for pattern in EMERGENCY_PATTERNS)


def is_medical_advice_request(message: str) -> bool:
    """Return True when the user is asking for diagnosis or treatment advice."""
    normalized = message.casefold()
    if is_prescription_listing_request(normalized):
        return False
    return any(re.search(pattern, normalized) for pattern in MEDICAL_ADVICE_PATTERNS)


def is_prescription_listing_request(message: str) -> bool:
    """Return True when the user is asking to list existing prescription records."""
    normalized = message.casefold()
    return any(re.search(pattern, normalized) for pattern in PRESCRIPTION_LIST_PATTERNS)


def is_prescription_related_request(
    message: str,
    prescriptions: Sequence[Any] | None = None,
) -> bool:
    """Return True when the patient is asking about stored prescription content."""
    normalized = message.casefold()
    if is_prescription_listing_request(normalized):
        return True
    if any(re.search(pattern, normalized) for pattern in PRESCRIPTION_TOPIC_PATTERNS):
        return True
    return bool(prescriptions and _find_medication_matches(prescriptions, message))


def _numbered_sources(retrieval: dict[str, Any]) -> str:
    """Render retrieved prescription text with stable line references."""
    snippets = retrieval.get("snippets") or []
    if not snippets:
        return "No prescription records were retrieved."

    rendered: list[str] = []
    for index, snippet in enumerate(snippets, start=1):
        prescription_id = snippet.get("prescription_id") or f"result-{index}"
        lines = [
            line.strip()
            for line in (snippet.get("text") or "").splitlines()
            if line.strip()
        ]
        if not lines:
            continue
        rendered.append(f"Prescription {prescription_id}")
        rendered.extend(
            f"  {line_number}. {line}"
            for line_number, line in enumerate(lines, start=1)
        )

    return (
        "\n".join(rendered)
        if rendered
        else "No readable prescription records were retrieved."
    )


def _field(record: Any, name: str, default: Any = "") -> Any:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)


def _med_field(medication: Any, name: str, default: str = "") -> str:
    if isinstance(medication, dict):
        return str(medication.get(name, default) or default)
    return str(getattr(medication, name, default) or default)


def _record_id(record: Any, fallback: int) -> str:
    raw_id = _field(record, "id") or _field(record, "prescription_id")
    return str(raw_id or f"result-{fallback}")


def _display_text(value: Any, fallback: str = "Not specified") -> str:
    text = str(value or "").strip()
    return text if text and text.casefold() != "none" else fallback


def _title_case_medicine(name: str) -> str:
    cleaned = _display_text(name, "Unnamed medicine")
    if cleaned.isupper() or cleaned.islower():
        return cleaned.title()
    return cleaned


def _dose_word(count_text: str) -> str:
    return "dose" if count_text == "1" else "doses"


def _explain_frequency(frequency: str) -> tuple[str, str | None]:
    """Explain common morning-afternoon-night notation without changing it."""
    cleaned = _display_text(frequency, "Not specified")
    match = re.match(
        r"^\s*(\d+)\s*[-/]\s*(\d+)\s*[-/]\s*(\d+)\s*(.*)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not match:
        return f"Frequency: {cleaned}", None

    morning, afternoon, night, meal_note = match.groups()
    slots = (
        ("Morning", morning),
        ("Afternoon", afternoon),
        ("Night", night),
    )
    explained_slots = [
        f"{label}: {'none' if count == '0' else f'{count} {_dose_word(count)}'}"
        for label, count in slots
    ]
    meal_timing = meal_note.strip() or None
    return f"Timing: {'; '.join(explained_slots)}", meal_timing


def _format_medicine_explanation(medication: Any) -> list[str]:
    medicine_name = _title_case_medicine(_med_field(medication, "medicine_name", ""))
    dosage = _display_text(_med_field(medication, "dosage", ""))
    duration = _display_text(_med_field(medication, "duration", ""))
    instructions = _display_text(_med_field(medication, "instructions", ""), "")
    frequency = _med_field(medication, "frequency", "")
    timing_line, meal_timing = _explain_frequency(frequency)

    lines = [
        f"Medicine: {medicine_name}",
        f"Dose: {dosage}",
        timing_line,
    ]
    if meal_timing:
        lines.append(f"Meal timing from prescription: {meal_timing}")
    lines.append(f"Duration: {duration}")
    if instructions:
        lines.append(f"Doctor instruction as written: {instructions}")
    return lines


def prescriptions_to_retrieval(prescriptions: Sequence[Any]) -> dict[str, Any]:
    """Convert database prescription records into the same snippet shape as RAG."""
    snippets: list[dict[str, Any]] = []
    formatted_texts: list[str] = []

    for index, prescription in enumerate(prescriptions, start=1):
        prescription_id = _record_id(prescription, index)
        medications = _field(prescription, "medications", []) or []
        medication_lines = []
        for medication in medications:
            medication_lines.append(
                "- "
                f"{_med_field(medication, 'medicine_name', 'Unnamed medicine')}: "
                f"Dosage={_med_field(medication, 'dosage', 'Not specified')}, "
                f"Frequency={_med_field(medication, 'frequency', 'Not specified')}, "
                f"Duration={_med_field(medication, 'duration', 'Not specified')}, "
                f"Instructions={_med_field(medication, 'instructions', 'None')}"
            )

        content = (
            "MEDICAL PRESCRIPTION RECORD\n"
            f"Prescription ID: {prescription_id}\n"
            f"Patient Name: {_field(prescription, 'patient_name', 'Patient')}\n"
            f"Doctor Name: {_field(prescription, 'doctor_name', 'Doctor')}\n"
            f"Issuance Date: {_field(prescription, 'date', 'Not specified')}\n"
            f"Diagnosis: {_field(prescription, 'diagnosis', 'Not specified')}\n\n"
            "Prescribed Medications:\n"
            f"{chr(10).join(medication_lines) if medication_lines else '- No medicines listed'}\n\n"
            f"Doctor Advice / Notes: {_field(prescription, 'notes', None) or 'None'}\n"
            f"Follow-up Date: {_field(prescription, 'follow_up_date', None) or 'Not specified'}"
        )
        snippets.append(
            {
                "prescription_id": prescription_id,
                "score": 0.0,
                "text": content,
            }
        )
        formatted_texts.append(content)

    return {
        "total_results": len(snippets),
        "snippets": snippets,
        "context": "\n\n---\n\n".join(formatted_texts)
        if formatted_texts
        else "No matching prescription details found.",
    }


def _deterministic_answer_from_records(prescriptions: Sequence[Any]) -> str:
    """Fallback answer when Gemini is unavailable but database records exist."""
    records = list(prescriptions)
    if not records:
        return (
            "I could not find any CityCare prescription records for your account yet. "
            "Please contact the clinic or your doctor if you expected one."
        )

    lines = [
        "Here is the dosage and timing exactly from your CityCare prescription records, "
        "with the common morning-afternoon-night notation explained."
    ]
    for index, prescription in enumerate(records, start=1):
        prescription_id = _record_id(prescription, index)
        lines.append("")
        lines.append(
            f"Prescription {index} - {_display_text(_field(prescription, 'date', ''))}"
            f" - {_display_text(_field(prescription, 'doctor_name', ''), 'Doctor')}"
        )
        lines.append(f"Diagnosis written: {_display_text(_field(prescription, 'diagnosis', ''))}")
        lines.append(f"Prescription ID: {prescription_id}")

        medications = _field(prescription, "medications", []) or []
        if medications:
            for medication in medications:
                lines.append("")
                lines.extend(_format_medicine_explanation(medication))
        else:
            lines.append("")
            lines.append("Medicines: No medicines listed in this prescription.")

        notes = _display_text(_field(prescription, "notes", None), "")
        follow_up = _display_text(_field(prescription, "follow_up_date", None), "Not specified")
        if notes:
            lines.append(f"Doctor notes: {notes}")
        lines.append(f"Follow-up: {follow_up}")

    lines.append("")
    lines.append(
        "If any timing/instruction looks confusing or conflicting, please confirm it with "
        "your prescribing doctor before taking or changing medicine."
    )
    return "\n".join(lines)


def _format_prescription_listing(prescriptions: Sequence[Any]) -> str:
    """List existing prescriptions without turning it into medical advice."""
    records = list(prescriptions)
    if not records:
        return (
            "I could not find any CityCare prescription records for your account yet. "
            "Please contact the clinic or your doctor if you expected one."
        )

    plural = "" if len(records) == 1 else "s"
    lines = [f"I found {len(records)} CityCare prescription record{plural} in your account."]

    for index, prescription in enumerate(records, start=1):
        prescription_id = _record_id(prescription, index)
        medications = _field(prescription, "medications", []) or []
        medicine_summary = ", ".join(
            f"{_title_case_medicine(_med_field(medication, 'medicine_name', ''))} "
            f"({_display_text(_med_field(medication, 'dosage', ''))})"
            for medication in medications
        )

        lines.append("")
        lines.append(
            f"Prescription {index} - {_display_text(_field(prescription, 'date', ''))}"
        )
        lines.append(
            f"Doctor: {_display_text(_field(prescription, 'doctor_name', ''), 'Doctor')}"
        )
        lines.append(
            f"Diagnosis written: {_display_text(_field(prescription, 'diagnosis', ''))}"
        )
        lines.append(
            "Medicines documented: "
            f"{medicine_summary if medicine_summary else 'No medicines listed'}"
        )
        lines.append(
            f"Follow-up: {_display_text(_field(prescription, 'follow_up_date', None), 'Not specified')}"
        )
        lines.append(f"Prescription ID: {prescription_id}")

    lines.append("")
    lines.append(
        "I can also explain the dosage and timing written in these records. "
        "For symptoms, side effects, dose changes, or treatment decisions, please consult your doctor."
    )
    return "\n".join(lines)


def _normalized_text(value: str) -> str:
    """Normalize patient/medicine text for safe fuzzy matching."""
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    return " ".join(tokens)


def _meaningful_question_tokens(question: str) -> list[str]:
    """Keep likely medicine-name words from a patient question."""
    tokens = re.findall(r"[a-z0-9]+", question.casefold())
    return [
        token
        for token in tokens
        if token not in QUESTION_STOPWORDS and len(token) > 1
    ]


def _looks_like_medication_detail_request(question: str) -> bool:
    """Return True for questions about written dose, timing, or instructions."""
    normalized = question.casefold()
    return any(re.search(pattern, normalized) for pattern in MEDICATION_DETAIL_PATTERNS)


def _mentions_medicine_noun(question: str) -> bool:
    """Return True when the question explicitly mentions medicine/tablet language."""
    return bool(re.search(MEDICINE_NOUN_PATTERN, question.casefold()))


def _looks_like_follow_up_request(question: str) -> bool:
    """Return True when the patient asks when to see the doctor again."""
    normalized = question.casefold()
    return any(re.search(pattern, normalized) for pattern in FOLLOW_UP_PATTERNS)


def _find_medication_matches(
    prescriptions: Sequence[Any],
    question: str,
) -> list[tuple[int, Any, Any]]:
    """Find medicines explicitly named by the patient question."""
    question_tokens = _meaningful_question_tokens(question)
    if not question_tokens:
        return []

    normalized_question = _normalized_text(question)
    question_token_set = set(question_tokens)
    matches: list[tuple[int, Any, Any]] = []

    for index, prescription in enumerate(prescriptions, start=1):
        medications = _field(prescription, "medications", []) or []
        for medication in medications:
            medicine_name = _med_field(medication, "medicine_name", "")
            normalized_medicine = _normalized_text(medicine_name)
            if not normalized_medicine:
                continue

            medicine_tokens = set(re.findall(r"[a-z0-9]+", normalized_medicine))
            overlap = question_token_set.intersection(medicine_tokens)
            exact_phrase_match = (
                len(normalized_medicine) >= 4
                and normalized_medicine in normalized_question
            )

            if exact_phrase_match or overlap:
                matches.append((index, prescription, medication))

    return matches


def _focused_records_for_medicine_matches(
    matches: Sequence[tuple[int, Any, Any]],
) -> list[dict[str, Any]]:
    """Build a smaller source set so Gemini answers only the requested medicine."""
    focused_records: list[dict[str, Any]] = []
    for index, prescription, medication in matches:
        focused_records.append(
            {
                "id": _record_id(prescription, index),
                "patient_name": _field(prescription, "patient_name", "Patient"),
                "doctor_name": _field(prescription, "doctor_name", "Doctor"),
                "date": _field(prescription, "date", "Not specified"),
                "diagnosis": _field(prescription, "diagnosis", "Not specified"),
                "medications": [medication],
                "notes": _field(prescription, "notes", None),
                "follow_up_date": _field(prescription, "follow_up_date", None),
            }
        )
    return focused_records


def _available_medicine_names(prescriptions: Sequence[Any]) -> str:
    """Return a compact list of documented medicine names for not-found answers."""
    names: list[str] = []
    seen: set[str] = set()
    for prescription in prescriptions:
        medications = _field(prescription, "medications", []) or []
        for medication in medications:
            display_name = _title_case_medicine(_med_field(medication, "medicine_name", ""))
            key = display_name.casefold()
            if key and key not in seen:
                seen.add(key)
                names.append(display_name)
    return ", ".join(names)


def _unknown_medicine_answer(
    question: str,
    prescriptions: Sequence[Any],
    matches: Sequence[tuple[int, Any, Any]] | None = None,
) -> str | None:
    """Avoid sending unknown medicine-name questions to Gemini with unrelated records."""
    if matches is None:
        matches = _find_medication_matches(prescriptions, question)
    if matches:
        return None
    if not (_looks_like_medication_detail_request(question) and _mentions_medicine_noun(question)):
        return None

    medicine_names = _available_medicine_names(prescriptions)
    if not (_meaningful_question_tokens(question) and medicine_names):
        return None

    return (
        "I could not find a medicine matching that name in your CityCare "
        "prescription records.\n\n"
        f"Available medicines documented: {medicine_names}\n\n"
        "Please check the medicine name or ask your prescribing doctor if "
        "you are unsure."
    )


def _format_matching_medicine_answer(
    matches: Sequence[tuple[int, Any, Any]],
) -> str:
    """Render only the medicine(s) that match the patient's question."""
    intro = (
        "I found this medicine in your CityCare prescription records."
        if len(matches) == 1
        else "I found these medicines in your CityCare prescription records."
    )
    lines = [intro]

    for index, prescription, medication in matches:
        lines.append("")
        lines.append(
            f"Prescription {index} - {_display_text(_field(prescription, 'date', ''))}"
            f" - {_display_text(_field(prescription, 'doctor_name', ''), 'Doctor')}"
        )
        lines.extend(_format_medicine_explanation(medication))

    lines.append("")
    lines.append(
        "For symptoms, side effects, dose changes, or treatment decisions, "
        "please consult your doctor."
    )
    return "\n".join(lines)


def _targeted_medicine_answer(
    question: str,
    prescriptions: Sequence[Any],
) -> str | None:
    """Return a focused medicine answer when the question names one."""
    records = list(prescriptions)
    if not (_looks_like_medication_detail_request(question) or _mentions_medicine_noun(question)):
        return None

    matches = _find_medication_matches(records, question)
    if matches:
        return _format_matching_medicine_answer(matches)

    return _unknown_medicine_answer(question, records, matches)


def _format_follow_up_answer(prescriptions: Sequence[Any]) -> str:
    """Fallback answer for follow-up-date questions."""
    records = list(prescriptions)
    follow_up_lines: list[str] = []

    for index, prescription in enumerate(records, start=1):
        follow_up = _display_text(
            _field(prescription, "follow_up_date", None),
            "Not specified",
        )
        if follow_up == "Not specified":
            continue

        follow_up_lines.append("")
        follow_up_lines.append(
            f"Prescription {index} - {_display_text(_field(prescription, 'date', ''))}"
            f" - {_display_text(_field(prescription, 'doctor_name', ''), 'Doctor')}"
        )
        follow_up_lines.append(f"Follow-up: {follow_up}")

    if not follow_up_lines:
        return (
            "I could not find a follow-up date written in your CityCare prescription "
            "records. Please contact the clinic or your prescribing doctor to confirm "
            "when you should visit again."
        )

    return "\n".join(
        [
            "Here is the follow-up timing written in your CityCare prescription records.",
            *follow_up_lines,
            "",
            "If your symptoms worsen or you feel unwell before then, please contact your doctor sooner.",
        ]
    )


def _deterministic_answer_for_question(
    question: str,
    prescriptions: Sequence[Any],
) -> str:
    """Fallback answer that respects medication-specific questions."""
    records = list(prescriptions)
    targeted_answer = _targeted_medicine_answer(question, records)
    if targeted_answer:
        return targeted_answer
    if _looks_like_follow_up_request(question):
        return _format_follow_up_answer(records)
    return _deterministic_answer_from_records(records)


def _prescription_gemini_enabled() -> bool:
    """Use Gemini for prescription chat when an API key exists, unless disabled."""
    flag = (os.getenv("PRESCRIPTION_AI_USE_GEMINI") or "").strip().casefold()
    if flag in {"0", "false", "no", "off"}:
        return False
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _generate_grounded_answer(question: str, sources: str) -> str:
    """Ask Gemini to explain only the supplied prescription evidence."""
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY.")

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    response = client.models.generate_content(
        model=model,
        contents=(
            "Retrieved prescription records:\n"
            f"{sources}\n\n"
            f"Patient question: {question}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
        ),
    )
    return (
        response.text
        or "I could not prepare an answer from the retrieved prescription records."
    )


def answer_from_prescription_records(
    question: str,
    prescriptions: Sequence[Any],
) -> PrescriptionAnswer:
    """Answer from already-authorized database prescription records."""
    if is_emergency_message(question):
        return PrescriptionAnswer(
            answer=EMERGENCY_RESPONSE,
            sources="Emergency safety check triggered.",
            emergency=True,
        )

    records = list(prescriptions)
    if is_prescription_listing_request(question):
        retrieval = prescriptions_to_retrieval(records)
        return PrescriptionAnswer(
            answer=_format_prescription_listing(records),
            sources=_numbered_sources(retrieval),
        )

    if is_medical_advice_request(question):
        return PrescriptionAnswer(
            answer=MEDICAL_ADVICE_RESPONSE,
            sources="Medical-advice safety check triggered.",
            medical_advice=True,
        )

    if not is_prescription_related_request(question, records):
        return PrescriptionAnswer(
            answer=NON_PRESCRIPTION_RESPONSE,
            sources="Non-prescription conversation intent detected.",
        )

    if not records:
        return PrescriptionAnswer(
            answer=(
                "I could not find any CityCare prescription records for your account yet. "
                "Please contact the clinic or your doctor if you expected one."
            ),
            sources="No prescription records were retrieved.",
        )

    medicine_matches: list[tuple[int, Any, Any]] = []
    if _looks_like_medication_detail_request(question) or _mentions_medicine_noun(question):
        medicine_matches = _find_medication_matches(records, question)

    unknown_medicine_answer = _unknown_medicine_answer(question, records, medicine_matches)
    if unknown_medicine_answer:
        retrieval = prescriptions_to_retrieval(records)
        return PrescriptionAnswer(
            answer=unknown_medicine_answer,
            sources=_numbered_sources(retrieval),
        )

    source_records: Sequence[Any] = (
        _focused_records_for_medicine_matches(medicine_matches)
        if medicine_matches
        else records
    )
    retrieval = prescriptions_to_retrieval(source_records)
    sources = _numbered_sources(retrieval)

    if _prescription_gemini_enabled():
        try:
            answer = _generate_grounded_answer(question, sources)
        except Exception:
            answer = _deterministic_answer_for_question(question, records)
    else:
        answer = _deterministic_answer_for_question(question, records)
    return PrescriptionAnswer(answer=answer, sources=sources)


def answer_question(patient_id: str, question: str, top_k: int = 3) -> PrescriptionAnswer:
    """Answer one patient question without allowing unsafe requests into the LLM."""
    if is_emergency_message(question):
        return PrescriptionAnswer(
            answer=EMERGENCY_RESPONSE,
            sources="Emergency safety check triggered.",
            emergency=True,
        )

    if is_medical_advice_request(question):
        return PrescriptionAnswer(
            answer=MEDICAL_ADVICE_RESPONSE,
            sources="Medical-advice safety check triggered.",
            medical_advice=True,
        )

    retrieval = search_prescriptions_rag(query=question, patient_id=patient_id, top_k=top_k)
    sources = _numbered_sources(retrieval)
    if retrieval.get("error"):
        return PrescriptionAnswer(
            answer=(
                "I could not retrieve your prescription details. Please contact the clinic "
                "or your doctor."
            ),
            sources=sources,
        )
    if not retrieval.get("snippets"):
        return PrescriptionAnswer(
            answer=(
                "I could not find that information in the retrieved prescription records. "
                "Please consult your prescribing doctor."
            ),
            sources=sources,
        )

    try:
        answer = _generate_grounded_answer(question, sources)
    except Exception:
        answer = (
            "I could not prepare a grounded answer. Please consult your prescribing doctor."
        )
    return PrescriptionAnswer(answer=answer, sources=sources)
