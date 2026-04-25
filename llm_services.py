import json
from models import StudentProfile

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
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Explanation generation failed: {e}")
        return "An explanation could not be generated at this time."


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
