import os
import psycopg2
from fastapi import FastAPI
from dotenv import load_dotenv
from google import genai

from models import StudentProfile, GradecardRequest, ChatRequest
from scoring import achievement_percentage, need_percentage
from database import get_student_embedding, get_all_eligible_scholarships, embedding_fallback_active
from llm_services import generate_explanation, parse_gradecard, process_chat_message

app = FastAPI()
FINAL_MATCH_LIMIT = 10

STATE_TO_ABBR = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO",
    "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
    "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "DISTRICT OF COLUMBIA": "DC"
}


def normalize_state_input(state: str) -> str:
    value = state.strip().upper()
    if len(value) == 2 and value.isalpha():
        return value
    return STATE_TO_ABBR.get(value, state)

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

@app.get("/")
def home():
    return {"message": "API is working"}

@app.post("/api/match-scholarships")
def match_scholarships_api(profile: StudentProfile):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return {"matches": [], "error": "Missing DATABASE_URL"}

    with psycopg2.connect(database_url, sslmode="require") as conn:
        try:
            student_embedding = get_student_embedding(
                client,
                profile.major,
                profile.extracurriculars
            )
        except Exception as exc:
            return {
                "status": "error",
                "matches": [],
                "error": f"Unable to create student embedding: {exc}"
            }
        
        search_text = f"{profile.major} {profile.extracurriculars}"

        normalized_state = normalize_state_input(profile.state)

        rows = get_all_eligible_scholarships(
            conn,
            student_embedding,
            search_text,
            profile.gpa,
            profile.income,
            normalized_state
        )

    fallback_mode = embedding_fallback_active()

    valid_scholarships = []

    # 1. Score all eligible scholarships returned by SQL filters.
    for row in rows:
        distance = float(row[3])
        text_rank = float(row[4])
        income_ceiling = float(row[5]) if row[5] is not None else None
        
        base_achievement = achievement_percentage(distance)
        
        # HYBRID FUSION: Add a bonus up to 20% if exact keywords matched!
        keyword_bonus = min(20.0, text_rank * 100.0)
        achievement_match = round(min(100.0, base_achievement + keyword_bonus), 2)

        # During provider quota fallback, rely more on lexical match signal
        # to keep retrieval usable without lowering the >=60 rule.
        if fallback_mode:
            lexical_recovery_score = min(100.0, text_rank * 1000.0)
            achievement_match = round(max(achievement_match, lexical_recovery_score), 2)
        
        need_match = need_percentage(profile.income, income_ceiling)

        # Hard quality gate requested by product: keep only achievement >= 60.
        if achievement_match < 60.0:
            continue

        valid_scholarships.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "achievement_match_percentage": achievement_match,
            "need_match_percentage": need_match
        })

    # 2. Keep leaderboard views for each dimension
    top_achievement = sorted(
        valid_scholarships, 
        key=lambda x: (x["achievement_match_percentage"], x["need_match_percentage"]),
        reverse=True
    )[:10]
    
    top_need = sorted(
        valid_scholarships, 
        key=lambda x: (x["need_match_percentage"], x["achievement_match_percentage"]),
        reverse=True
    )[:10]

    # 3. Build overall top 10 by combining achievement + need.
    ranked_matches = sorted(
        valid_scholarships,
        key=lambda x: (
            round((x["achievement_match_percentage"] * 0.6) + (x["need_match_percentage"] * 0.4), 2),
            x["achievement_match_percentage"],
            x["need_match_percentage"],
        ),
        reverse=True,
    )
    final_matches = ranked_matches[:FINAL_MATCH_LIMIT]

    # Generate the RAG explanation text based on the top results
    explanation = generate_explanation(client, profile, final_matches)

    return {
        "status": "success",
        "embedding_mode": "fallback" if fallback_mode else "provider",
        "achievement_table": top_achievement,
        "need_table": top_need,
        "final_matches": final_matches,
        "explanation": explanation
    }

@app.post("/api/parse-gradecard")
def parse_gradecard_api(request: GradecardRequest):
    try:
        profile_data = parse_gradecard(client, request.gradecard_text)
        return {
            "status": "success",
            "extracted_profile": profile_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/api/chat")
def chat_agent_api(request: ChatRequest):
    system_instruction = """
    You are a friendly and helpful scholarship advisor. Your goal is to help students find scholarships.
    To do this, you MUST collect 5 specific pieces of information from the user:
    1. GPA (e.g., 3.8)
    2. Family Income (e.g., $65,000)
    3. State of Residence (e.g., California)
    4. Major or intended field of study
    5. Extracurricular activities or hobbies

    If the user has not provided all 5 pieces of information, politely ask them for the missing details one or two at a time. Do not overwhelm them.
    Keep your responses conversational, encouraging, and brief (1-3 sentences max).

    CRITICAL RULE:
    The EXACT moment you have collected all 5 pieces of information, you MUST STOP CHATTING. Do not say "Let me look that up for you." 
    Instead, your entire response must be a raw JSON object (with no markdown blocks) that looks exactly like this:
    {
        "action": "trigger_search",
        "profile": {
            "gpa": 3.8,
            "income": 65000,
            "state": "California",
            "major": "Computer Science",
            "extracurriculars": "Robotics"
        }
    }
    """

    try:
        result = process_chat_message(client, request.messages, system_instruction)
        
        if result.get("intercepted"):
            profile_dict = result["profile"]
            student_profile = StudentProfile(
                gpa=float(profile_dict["gpa"]),
                income=float(profile_dict["income"]),
                state=str(profile_dict["state"]),
                major=str(profile_dict["major"]),
                extracurriculars=str(profile_dict["extracurriculars"])
            )
            scholarship_results = match_scholarships_api(student_profile)
            
            return {
                "status": "success",
                "type": "search_results",
                "data": scholarship_results
            }
            
        return {
            "status": "success",
            "type": "chat_reply",
            "reply": result["reply"]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }