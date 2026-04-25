import os
import psycopg2
from fastapi import FastAPI
from dotenv import load_dotenv
from google import genai

from models import StudentProfile, GradecardRequest, ChatRequest
from scoring import achievement_percentage, need_percentage
from database import get_student_embedding, get_all_eligible_scholarships
from llm_services import generate_explanation, parse_gradecard, process_chat_message

app = FastAPI()

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
        student_embedding = get_student_embedding(
            client,
            profile.major,
            profile.extracurriculars
        )
        
        search_text = f"{profile.major} {profile.extracurriculars}"

        rows = get_all_eligible_scholarships(
            conn,
            student_embedding,
            search_text,
            profile.gpa,
            profile.income,
            profile.state
        )

    valid_scholarships = []

    # 1. Apply threshold filtering BEFORE ranking
    for row in rows:
        distance = float(row[3])
        text_rank = float(row[4])
        income_ceiling = float(row[5]) if row[5] is not None else None
        
        base_achievement = achievement_percentage(distance)
        
        # HYBRID FUSION: Add a bonus up to 20% if exact keywords matched!
        keyword_bonus = min(20.0, text_rank * 100.0)
        achievement_match = round(min(100.0, base_achievement + keyword_bonus), 2)
        
        need_match = need_percentage(profile.income, income_ceiling)

        # NEW STRICT FILTER LOGIC:
        if achievement_match >= 60.0:
            pass  # always keep
        elif 55.0 <= achievement_match < 60.0 and need_match > 80.0:
            pass  # keep ONLY if borderline AND need_match is exceptionally high
        else:
            continue  # Otherwise remove (achievement < 55, or 55-60 with low need)

        valid_scholarships.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "achievement_match_percentage": achievement_match,
            "need_match_percentage": need_match
        })

    # 2. Implement proper dual ranking in Python
    top_achievement = sorted(
        valid_scholarships, 
        key=lambda x: x["achievement_match_percentage"], 
        reverse=True
    )[:10]
    
    top_need = sorted(
        valid_scholarships, 
        key=lambda x: x["need_match_percentage"], 
        reverse=True
    )[:10]

    # 3. Combine both lists using UNION (no duplicates)
    union_results = []
    seen_ids = set()

    for sch in top_achievement + top_need:
        if sch["id"] not in seen_ids:
            seen_ids.add(sch["id"])
            union_results.append(sch)

    # 4. Apply PRIORITY-BASED RANKING on union result
    top_bucket = []
    middle_bucket = []
    bottom_bucket = []

    for sch in union_results:
        ach = sch["achievement_match_percentage"]
        nd = sch["need_match_percentage"]
        
        if ach >= 60.0 and nd >= 70.0:
            top_bucket.append(sch)
        elif ach >= 60.0 or nd >= 70.0:
            middle_bucket.append(sch)
        else:
            bottom_bucket.append(sch)

    def sort_bucket(bucket):
        return sorted(
            bucket, 
            key=lambda x: (x["achievement_match_percentage"], x["need_match_percentage"]), 
            reverse=True
        )

    final_matches = sort_bucket(top_bucket) + sort_bucket(middle_bucket) + sort_bucket(bottom_bucket)

    # Generate the RAG explanation text based on the top results
    explanation = generate_explanation(client, profile, final_matches)

    return {
        "status": "success",
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