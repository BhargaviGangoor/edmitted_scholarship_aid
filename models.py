from pydantic import BaseModel,Field
from typing import List,Optional
#BaseModel is for structured data
#Field is for adding rules
#optional for missing values


class StudentProfile(BaseModel):
    gpa: float = Field(default=None, ge=0.0, le=4.0)
    sat:Optional[int] =Field(default=None,ge=400,le=1600)
    act:Optional[int]=Field(default=None,ge=1,le=36)

    extracurriculars: List[str] = []
    family_income:int=Field(...,ge=0)
    achievement_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    need_weight: float = Field(default=0.5, ge=0.0, le=1.0)

class MatchResult(BaseModel):
    rank: int

    program: str

    achievement_match: str
    achievement_label: str

    need_match: str
    need_label: str

    logic_summary: str