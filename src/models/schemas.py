from pydantic import BaseModel

class StudentProfile(BaseModel):
    gpa: float
    income: float   
    state: str
    major: str
    extracurriculars: str

class GradecardRequest(BaseModel):
    gradecard_text: str

class ChatMessage(BaseModel):
    role: str  # "user" or "model"
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
