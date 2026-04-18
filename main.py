from fastapi import FastAPI
from scoring import generate_matches
from models import StudentProfile, MatchResult

app = FastAPI()
@app.get("/")
def home():
    return {"message": "Engine is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/test-student")
def test_student(profile: StudentProfile):
    return profile

@app.post("/match-scholarships", response_model=list[MatchResult])
def match_scholarships(profile: StudentProfile):
    return generate_matches(profile)