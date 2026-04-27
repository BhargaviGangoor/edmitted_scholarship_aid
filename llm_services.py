import json
from models import StudentProfile

EXPLANATION_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
)


def build_fallback_explanation(profile: StudentProfile, top_3: list) -> str:
    best = top_3[0]

    lines = [
        (
            f"Based on your profile ({profile.major}, GPA {profile.gpa}, "
            f"income ${profile.income:,.0f}, {profile.state}), these scholarships are strong matches."
        ),
        (
            f"Best overall fit: {best['name']} "
            f"(achievement {best['achievement_match_percentage']}%, need {best['need_match_percentage']}%)."
        ),
    ]

    for idx, sch in enumerate(top_3, start=1):
        lines.append(
            (
                f"{idx}. {sch['name']}: achievement {sch['achievement_match_percentage']}% and "
                f"need {sch['need_match_percentage']}%. {sch['description']}"
            )
        )

    return "\n".join(lines)


def extract_response_text(response) -> str:
    """Safely extract text from Gemini responses across SDK variations."""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content is not None else None
        if not parts:
            continue
        chunks = [getattr(part, "text", "") for part in parts]
        joined = "\n".join(chunk for chunk in chunks if chunk)
        if joined.strip():
            return joined.strip()

    return ""


def normalize_model_name(model_name: str) -> str:
    if model_name.startswith("models/"):
        return model_name.split("/", 1)[1]
    return model_name


def supports_generate_content(methods: list[str] | None) -> bool:
    if not methods:
        return False
    normalized = [m.lower() for m in methods]
    return any("generatecontent" in method for method in normalized)


def get_explanation_model_order(client) -> list[str]:
    """Prefer known good models, but intersect with account/API-available models when possible."""
    try:
        discovered_models: set[str] = set()

        for model in client.models.list():
            methods = getattr(model, "supported_generation_methods", None)
            if not supports_generate_content(methods):
                continue
            name = getattr(model, "name", "")
            if not name:
                continue
            discovered_models.add(normalize_model_name(name))

        if discovered_models:
            ordered = [m for m in EXPLANATION_MODELS if m in discovered_models]
            if ordered:
                return ordered

            # If none of the preferred names exist, still try a flash model first.
            flash_models = sorted(m for m in discovered_models if "flash" in m)
            if flash_models:
                return flash_models

            return sorted(discovered_models)
    except Exception as exc:
        print(f"Model discovery failed for explanation: {exc}")

    return list(EXPLANATION_MODELS)

def generate_explanation(client, profile: StudentProfile, final_matches: list) -> str:
    top_3 = final_matches[:3]
    if not top_3:
        return "No suitable scholarships found to explain."
        
    prompt = (
        f"Student Profile:\n"
        f"GPA: {profile.gpa}\n"
        f"Income: ${profile.income}\n"
        f"State: {profile.state}\n"
        f"Major: {profile.major}\n"
        f"Extracurriculars: {profile.extracurriculars}\n\n"
        "Top Scholarships Context:\n"
    )
    
    for sch in top_3:
        prompt += f"- Name: {sch['name']}\n"
        prompt += f"  Description: {sch['description']}\n"
        prompt += f"  Achievement Match: {sch['achievement_match_percentage']}%\n"
        prompt += f"  Need Match: {sch['need_match_percentage']}%\n\n"
        
    prompt += (
        "Instructions:\n"
        "1. Explain why these scholarships match the student.\n"
        "2. Highlight the best one.\n"
        "3. Keep the explanation clear and concise."
    )

    last_error = None
    model_order = get_explanation_model_order(client)
    for model_name in model_order:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            text = extract_response_text(response)
            if text:
                return text
        except Exception as e:
            last_error = e

    if last_error is not None:
        print(
            "Explanation generation failed, using local fallback: "
            f"tried={model_order}, last_error={last_error}"
        )

    return build_fallback_explanation(profile, top_3)


def parse_gradecard(client, text: str) -> dict:
    prompt = f"""
    You are an expert academic transcript and gradecard parser.
    Read the following gradecard text:
    
    "{text}"
    
    Extract the following information to build a student profile. 
    1. If a specific piece of information is missing (like income or extracurriculars), return null for that field.
    2. For the 'major', if it is not explicitly stated, infer the best college major based on their highest grades or hardest classes.
    3. Look for context clues for the 'state' (like the high school name).
    
    Return ONLY a raw JSON object with these exact keys. Do not wrap it in markdown blocks.
    {{
        "gpa": float or null,
        "income": float or null,
        "state": string or null,
        "major": string or null,
        "extracurriculars": string or null
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()
        
    return json.loads(raw_text)


def process_chat_message(client, messages, system_instruction: str) -> dict:
    contents = []
    for msg in messages:
        contents.append({
            "role": msg.role,
            "parts": [{"text": msg.content}]
        })

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config={"system_instruction": system_instruction}
    )
    
    raw_text = response.text.strip()
    
    # Check if the LLM returned the secret JSON
    if "trigger_search" in raw_text and "{" in raw_text:
        # Clean up markdown
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        try:
            agent_data = json.loads(raw_text)
            if agent_data.get("action") == "trigger_search":
                return {
                    "intercepted": True,
                    "profile": agent_data["profile"]
                }
        except Exception as parse_error:
            print(f"Agent JSON parse error: {parse_error}")
            pass
            
    # If it's not JSON, it's a normal chat message.
    return {
        "intercepted": False,
        "reply": raw_text
    }
