"""
chatbot/gemini_client.py - Gemini SDK Wrapper & Function Calling Loop

Defines Gemini tool schemas for get_appointments and get_doctor_list,
and manages the multi-turn tool execution loop.
"""

from datetime import date
import json
import os
from typing import Any, Dict, List, Optional
from odmantic import AIOEngine

from google import genai
from google.genai import types

from chatbot.tools import execute_tool_call
from common.logger import get_logger

logger = get_logger(__name__)


def get_gemini_client() -> genai.Client:
    """Initialize and return google-genai Client using GEMINI_API_KEY."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not found in environment")
    return genai.Client(api_key=api_key)


# Tool Declarations for Gemini Function Calling
get_appointments_tool = types.FunctionDeclaration(
    name="get_appointments",
    description=(
        "Fetch scheduled appointments for a doctor between start_date and end_date. "
        "Use this tool whenever the user asks for appointment schedules, daily roster, or booked slots."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "doctor_id": types.Schema(
                type="STRING",
                description="The ID of the doctor (doctor profile ID or doctor user ID).",
            ),
            "start_date": types.Schema(
                type="STRING",
                description="Start date in YYYY-MM-DD format.",
            ),
            "end_date": types.Schema(
                type="STRING",
                description="End date in YYYY-MM-DD format.",
            ),
        },
        required=["doctor_id", "start_date", "end_date"],
    ),
)

get_doctor_list_tool = types.FunctionDeclaration(
    name="get_doctor_list",
    description=(
        "Fetch the list of all doctor profiles affiliated with the hospital. "
        "Use this tool when a hospital owner asks for the list of doctors or doctor IDs in their clinic."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "hospital_id": types.Schema(
                type="STRING",
                description="The string ObjectId of the hospital tenant.",
            ),
        },
        required=["hospital_id"],
    ),
)

search_patient_handbook_tool = types.FunctionDeclaration(
    name="search_patient_handbook",
    description=(
        "Search the CityCare Clinic Patient Handbook and knowledge base for clinic policies, opening hours, "
        "patient rules, services, cancellation guidelines, emergency procedures, and general FAQs."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "query": types.Schema(
                type="STRING",
                description="The search query string to look up in the handbook (e.g. 'cancellation policy', 'opening hours').",
            ),
        },
        required=["query"],
    ),
)

search_patient_prescriptions_tool = types.FunctionDeclaration(
    name="search_patient_prescriptions",
    description=(
        "Search the patient's medical prescriptions using RAG vector similarity search. "
        "Use this tool when a patient asks about their prescribed medicines, dosages, frequencies, "
        "doctor advice/notes, diagnoses, or prescription instructions."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "query": types.Schema(
                type="STRING",
                description="The query string regarding prescription details (e.g. 'fever medicine dosage', 'cough syrup instructions').",
            ),
        },
        required=["query"],
    ),
)

TOOLS = [
    types.Tool(
        function_declarations=[
            get_appointments_tool,
            get_doctor_list_tool,
            search_patient_handbook_tool,
            search_patient_prescriptions_tool,
        ]
    )
]


async def run_chat_completion(
    engine: AIOEngine,
    current_user: dict,
    messages_history: List[Dict[str, str]],
    user_prompt: str,
) -> str:
    """
    Executes a chat turn with Gemini using function calling tools.

    Args:
        engine: ODMantic MongoDB engine.
        current_user: JWT payload dict (user_id, role, hospital_id, name).
        messages_history: Prior chat messages list of dicts [{"role": "user"|"assistant", "content": "..."}].
        user_prompt: Latest user message string.

    Returns:
        str: Final natural language response text from assistant.
    """
    client = get_gemini_client()
    today_str = date.today().isoformat()
    role = current_user.get("role", "user")
    name = current_user.get("name", "User")
    hospital_id = current_user.get("hospital_id", "")
    user_id = current_user.get("user_id", "")

    system_instruction = f"""
You are the CityCare Clinic Schedule-Assistant, Prescription Assistant & Patient Knowledge AI.
You help patients, doctors, and hospital owners view schedules, appointments, doctor rosters, clinic policies, and patient prescriptions via RAG.

Current Context:
- User Name: {name}
- User Role: {role}
- User ID: {user_id}
- Hospital Tenant ID: {hospital_id}
- Today's Date: {today_str}

Rules:
1. Always use function calls (`get_appointments`, `get_doctor_list`, `search_patient_handbook`, `search_patient_prescriptions`) to retrieve accurate data. NEVER invent appointment data, prescriptions, dosages, clinic rules, or dates.
2. If asked about appointments or schedule, determine the relevant date or date range (default start_date and end_date to today's date '{today_str}' if not specified) and call `get_appointments`.
3. For doctors asking about their schedule, call `get_appointments` using their doctor ID (user ID '{user_id}').
4. For hospital owners asking about clinic doctors or schedules, first call `get_doctor_list(hospital_id='{hospital_id}')` if doctor IDs are needed, then call `get_appointments`.
5. For patient queries about their prescribed medicines, dosages, frequencies, doctor notes, or diagnoses, call `search_patient_prescriptions(query=...)` to fetch their prescription RAG records.
6. For general questions regarding clinic rules, patient handbook policies, opening hours, cancellations, services, or patient guidelines, call `search_patient_handbook(query=...)`.
7. Be concise, polite, professional, empathetic, and clear in formatting schedules, prescriptions, and handbook summaries.
8. If a tool call fails or returns an authorization error, explain the permission restriction politely.
"""

    # Format contents for Gemini SDK
    contents = []
    for msg in messages_history:
        contents.append(
            types.Content(
                role="user" if msg["role"] == "user" else "model",
                parts=[types.Part.from_text(text=msg["content"])],
            )
        )
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)],
        )
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=TOOLS,
        temperature=0.2,
    )

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    max_turns = 5

    try:
        for turn in range(max_turns):
            logger.info("Calling Gemini API model=%s turn=%d", model_name, turn)
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )

            # Check if model returned function calls
            function_calls = response.function_calls
            if function_calls:
                # Process model tool call requests
                contents.append(response.candidates[0].content)
                tool_response_parts = []

                for function_call in function_calls:
                    fn_name = function_call.name
                    fn_args = dict(function_call.args) if function_call.args else {}
                    logger.info("Gemini requested tool execution: %s(%s)", fn_name, fn_args)

                    # Dispatch tool call through security gate in tools.py
                    tool_result = await execute_tool_call(
                        engine=engine,
                        current_user=current_user,
                        tool_name=fn_name,
                        tool_args=fn_args,
                    )

                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": tool_result},
                        )
                    )

                contents.append(
                    types.Content(
                        role="user",
                        parts=tool_response_parts,
                    )
                )
            else:
                # Final text answer produced
                final_text = response.text or "I have processed your request."
                logger.info("Gemini returned final response text.")
                return final_text

        # If loop limit reached
        return "I completed checking your schedule request."

    except Exception as err:
        logger.error("Gemini API error: %s", str(err), exc_info=True)
        # Graceful fallback error response
        return f"Unable to reach Gemini assistant: {str(err)}"
