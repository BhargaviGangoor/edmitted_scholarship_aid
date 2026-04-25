def achievement_percentage(distance: float) -> float:
    similarity = max(0.0, min(1.0, 1.0 - distance))
    return round(similarity * 100.0, 2)

def need_percentage(student_income: float, income_ceiling: float | None) -> float:
    # 1. Base need: the less the student makes, the higher the score (Cap at $150k)
    student_factor = max(0.0, 100.0 * (1.0 - student_income / 150000.0))
    
    # 2. Scholarship need focus:
    if income_ceiling is not None:
        # A lower ceiling means the scholarship strongly targets need.
        scholarship_factor = max(0.0, 100.0 * (1.0 - income_ceiling / 150000.0))
        # Need score is high ONLY IF student has need AND scholarship targets need.
        return round((student_factor * 0.5) + (scholarship_factor * 0.5), 2)
    else:
        # No income limit = not need-based. Penalize the need score heavily.
        return round(student_factor * 0.3, 2)
