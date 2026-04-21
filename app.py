import os
import psycopg2
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

# import your functions
from main import (
    get_student_embedding,
    rank_scholarships
)

from fastapi import FastAPI

app = FastAPI()

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


@app.get("/")
def home():
    return {"message": "API is working"}

class StudentProfile(BaseModel):
    gpa: float
    income: float   
    state: str
    major: str
    extracurriculars: str

def _achievement_percentage(distance: float) -> float:
    similarity = max(0.0, min(1.0, 1.0 - distance))
    return round(similarity * 100.0, 2)


def _need_percentage(income: float) -> float:
    if income <= 30000:
        return 95.0
    if income <= 50000:
        return 85.0
    if income <= 80000:
        return 70.0
    if income <= 120000:
        return 55.0
    return 40.0


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

        rows = rank_scholarships(
            conn,
            student_embedding,
            profile.gpa,
            profile.income,
            profile.state
        )

    results = []

    for row in rows:
        distance = float(row[3])
        achievement_match_percentage = _achievement_percentage(distance)
        need_match_percentage = _need_percentage(profile.income)

        results.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "achievement_match_percentage": achievement_match_percentage,
            "need_match_percentage": need_match_percentage,
            "overall_match_percentage": round(
                (achievement_match_percentage * 0.8) + (need_match_percentage * 0.2),
                2
            )
        })

    return {
    "status": "success",
    "count": len(results[:10]),
    "matches": results[:10]
}