"""Small, deterministic language helpers for conversational Telegram workflows.

Gemini handles open-ended health conversation.  These helpers keep actions such as
booking and reading private records deterministic, testable, and scoped by the
existing gateway while still allowing patients to speak naturally.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import get_close_matches
import re
from typing import Optional, Sequence, TypeVar


@dataclass(frozen=True)
class NaturalIntent:
    """A patient-facing action inferred from ordinary text."""

    name: str
    specialization: Optional[str] = None


SPECIALIZATION_ALIASES = {
    "cardio": ("cardiologist", "cardiology", "heart doctor", "heart specialist"),
    "dermat": ("dermatologist", "dermatology", "skin doctor", "skin specialist"),
    "general": (
        "general physician",
        "general doctor",
        "family doctor",
        "family physician",
        "physician",
        "gp",
    ),
    "gyn": ("gynecologist", "gynaecologist", "gynecology", "gynaecology", "women's doctor"),
    "neuro": ("neurologist", "neurology", "brain specialist", "nerve specialist"),
    "ortho": ("orthopedic", "orthopaedic", "orthopedist", "bone doctor", "joint specialist"),
    "pediatric": ("pediatrician", "paediatrician", "pediatrics", "child doctor", "kids doctor"),
    "psychiatr": ("psychiatrist", "psychiatry", "mental health doctor"),
    "ent": ("ent doctor", "ear nose throat", "ear specialist"),
    "ophthalm": ("ophthalmologist", "eye doctor", "eye specialist"),
    "dent": ("dentist", "dental", "tooth doctor"),
}


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+'-]+", " ", text.casefold())).strip()


def _correct_status_typos(text: str) -> str:
    """Normalize common near-miss spellings in short registration questions."""
    targets = ("registered", "registration", "complete")
    corrected = []
    for token in text.split():
        if token in {"register", *targets}:
            corrected.append(token)
            continue
        if token.startswith(("reg", "complet")):
            match = get_close_matches(token, targets, n=1, cutoff=0.7)
            corrected.append(match[0] if match else token)
        else:
            corrected.append(token)
    return " ".join(corrected)


def extract_specialization(text: str) -> Optional[str]:
    """Return a stable specialization search stem from common patient wording."""
    normalized = _correct_status_typos(_plain(text))
    for search_stem, aliases in SPECIALIZATION_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", normalized) for alias in aliases):
            return search_stem
    match = re.search(
        r"(?:speciali[sz](?:ation|ed)?\s+(?:in|for)|doctor\s+for)\s+([a-z][a-z -]{2,35})",
        normalized,
    )
    return match.group(1).strip() if match else None


def detect_intent(text: str) -> Optional[NaturalIntent]:
    """Recognize high-confidence hospital actions without treating IDs as trusted."""
    normalized = _correct_status_typos(_plain(text))
    if not normalized:
        return None

    if re.search(
        r"\b(am i registered|is my (?:patient )?(?:registration|account) (?:complete|registered|active|linked)|"
        r"registration status|account status|check my registration|did i (?:finish|complete) registration|"
        r"do you (?:know|recognize) me)\b",
        normalized,
    ):
        return NaturalIntent("account_status")
    if re.search(
        r"\b(register|sign up|signup|create (?:an? |my )?(?:patient )?account|new patient)\b",
        normalized,
    ):
        return NaturalIntent("register")
    if re.search(r"\b(link|connect)\b.*\b(account|profile|medihub)\b", normalized):
        return NaturalIntent("link")
    if re.search(r"\b(prescription|prescriptions|medicine record|medical record|rx)\b", normalized):
        return NaturalIntent("prescriptions")
    if re.search(r"\b(facilities|facility|services|service|pharmacy|laboratory|lab)\b", normalized):
        return NaturalIntent("facilities")
    specialization = extract_specialization(normalized)
    if re.search(
        r"\b(?:is|was|has|did) (?:my |the )?(?:appointment |booking )?request "
        r"(?:approved|accepted|rejected|cancelled|completed|reviewed)\b|"
        r"\b(?:appointment|booking|request) (?:approval |current )?status\b|"
        r"\b(?:appointment|booking) (?:approved|accepted|rejected|cancelled|completed|pending)\b|"
        r"\bdid (?:the |my )?doctor (?:approve|accept|reject|review)\b|"
        r"\bhas (?:the |my )?doctor (?:approved|accepted|rejected|reviewed)\b",
        normalized,
    ):
        return NaturalIntent("appointment_status")
    if re.search(
        r"\b(book|schedule|make|need|want)\b.{0,30}\b(appointment|consultation|visit)\b|"
        r"\b(appointment|consultation)\b.{0,20}\b(book|schedule)\b",
        normalized,
    ):
        return NaturalIntent("book", specialization=specialization)
    if re.search(
        r"\b(my|upcoming|next|previous|past)\b.{0,20}\bappointments?\b|"
        r"\bappointments?\b.{0,20}\b(status|history|when|show|list)\b|"
        r"\b(show|list)\b.{0,20}\bappointments?\b",
        normalized,
    ):
        return NaturalIntent("appointments")

    if specialization:
        return NaturalIntent("specialization", specialization=specialization)
    if re.search(
        r"\b(doctors?|specialists?)\b.*\b(available|list|show|find|have|there)\b|"
        r"\b(show|list|find|available|which|need)\b.{0,24}\b(doctors?|specialists?)\b|"
        r"\bwho (?:are|is) (?:the )?doctors?\b",
        normalized,
    ):
        return NaturalIntent("doctors")
    if re.search(
        r"\b(hospitals?|clinics?)\b.*\b(available|list|show|find|near|there)\b|"
        r"\b(show|list|find|available|which)\b.{0,24}\b(hospitals?|clinics?)\b",
        normalized,
    ):
        return NaturalIntent("hospitals")
    if re.search(r"\b(what can you do|how can you help|help me|commands|options|menu)\b", normalized):
        return NaturalIntent("help")
    if len(normalized.split()) <= 6 and re.search(
        r"\b(hi|hello|hey|namaste|good morning|good afternoon|good evening)\b",
        normalized,
    ):
        return NaturalIntent("greeting")
    return None


def is_cancel_message(text: str) -> bool:
    normalized = _plain(text)
    return normalized in {
        "cancel",
        "cancel this",
        "never mind",
        "nevermind",
        "stop",
        "start over",
        "forget it",
    }


def is_affirmative(text: str) -> bool:
    normalized = _plain(text)
    return normalized in {
        "yes",
        "y",
        "yeah",
        "yep",
        "confirm",
        "confirmed",
        "go ahead",
        "book it",
        "please book it",
        "that works",
        "looks good",
        "yes book it",
        "yes please",
        "yes confirm",
    }


def is_negative(text: str) -> bool:
    normalized = _plain(text)
    return normalized in {"no", "n", "nope", "don't", "do not", "cancel it", "not now"}


def parse_natural_date(text: str, *, today: Optional[date] = None) -> Optional[str]:
    """Parse dates patients commonly type, including relative dates and weekdays."""
    base = today or date.today()
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    if "day after tomorrow" in normalized:
        return (base + timedelta(days=2)).isoformat()
    if re.search(r"\btomorrow\b", normalized):
        return (base + timedelta(days=1)).isoformat()
    if re.search(r"\btoday\b", normalized):
        return base.isoformat()

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for name, weekday in weekdays.items():
        if re.search(rf"\b{name}\b", normalized):
            days_ahead = (weekday - base.weekday()) % 7
            if "next" in normalized and days_ahead == 0:
                days_ahead = 7
            return (base + timedelta(days=days_ahead)).isoformat()

    cleaned = re.sub(r"\b(on|the)\b", " ", normalized)
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", cleaned)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group()).isoformat()
        except ValueError:
            return None

    formats = ("%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y")
    for value_format in formats:
        try:
            return datetime.strptime(cleaned, value_format).date().isoformat()
        except ValueError:
            pass
    for value_format in ("%d %B", "%d %b", "%B %d", "%b %d"):
        try:
            parsed = datetime.strptime(cleaned, value_format).date().replace(year=base.year)
            if parsed < base:
                parsed = parsed.replace(year=base.year + 1)
            return parsed.isoformat()
        except ValueError:
            pass
    return None


def parse_natural_time(text: str) -> Optional[str]:
    """Convert values such as '10 am' and '5:30 in the evening' to HH:MM."""
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    normalized = normalized.replace("noon", "12 pm").replace("midnight", "12 am")
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", normalized)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if minute > 59 or hour > (12 if meridiem else 23):
        return None
    if meridiem == "am":
        hour = 0 if hour == 12 else hour
    elif meridiem == "pm":
        hour = 12 if hour == 12 else hour + 12
    elif "evening" in normalized and hour < 12:
        hour += 12
    return f"{hour:02d}:{minute:02d}"


def parse_temperature(text: str) -> Optional[float]:
    """Extract a measured temperature and convert Celsius to Fahrenheit when stated."""
    match = re.search(r"(-?\d{2,3}(?:\.\d+)?)", text)
    if not match:
        return None
    value = float(match.group(1))
    normalized = text.casefold()
    if "celsius" in normalized or re.search(r"\b\d+(?:\.\d+)?\s*°?c\b", normalized):
        value = (value * 9 / 5) + 32
    return round(value, 1)


def parse_symptoms(text: str) -> list[str]:
    """Map a natural symptom sentence onto the API's supported symptom enum."""
    normalized = _plain(text)
    mappings = (
        ("fever", ("fever", "high temperature")),
        ("cough", ("cough", "coughing")),
        ("cold", ("cold", "runny nose", "blocked nose", "congestion")),
        ("bodyache", ("body ache", "bodyache", "body pain", "muscle pain", "muscle ache")),
        ("headache", ("headache", "head pain", "migraine")),
    )
    found = []
    for symptom, aliases in mappings:
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", normalized) and not re.search(
                rf"\b(no|without)\s+{re.escape(alias)}\b", normalized
            ):
                found.append(symptom)
                break
    if not found and normalized not in {"", "none", "no symptoms"}:
        found.append("other")
    return found


T = TypeVar("T")


def choice_index(text: str, choices: Sequence[T]) -> Optional[int]:
    """Resolve '2', 'number 2', or a small ordinal to a zero-based list index."""
    normalized = _plain(text)
    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
    number = ordinals.get(normalized)
    if number is None:
        match = re.fullmatch(r"(?:number\s+|option\s+)?(\d{1,2})", normalized)
        number = int(match.group(1)) if match else None
    if number is None or number < 1 or number > len(choices):
        return None
    return number - 1
