def to_float(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if text in ["", "NULL", "PrivacySuppressed", "NA"]:
        return None

    try:
        return float(text)
    except:
        return None
    
def first_numeric(row, columns):
    for col in columns:
        if col in row:
            value = to_float(row[col])
            if value is not None:
                return value
    return None

def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(x, x0, x1, y0, y1):
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def get_label(score):
    if score >= 90:
        return "Very High"
    if score >= 75:
        return "High"
    if score >= 55:
        return "Moderate"
    if score >= 35:
        return "Low"
    return "Very Low"


def build_logic_summary(achievement_score, need_score):
    parts = []

    if achievement_score > 85:
        parts.append("Exceptional academic profile")
    elif achievement_score >= 70:
        parts.append("Strong academic readiness")
    elif achievement_score >= 55:
        parts.append("Moderate academic fit")
    else:
        parts.append("Limited academic alignment")

    if need_score > 80:
        parts.append("excellent affordability")
    elif need_score >= 65:
        parts.append("good affordability")
    elif need_score >= 45:
        parts.append("moderate affordability")
    else:
        parts.append("higher financial burden")

    return f"{parts[0]} with {parts[1]}."

import random


def sat_to_gpa(sat_score):
    # Approximate conversion to use SAT percentiles as GPA proxies when GPA data is absent.
    return clamp(2.0 + ((sat_score - 800.0) / 800.0) * 2.0, 2.0, 4.0)

def calculate_achievement(profile, row):
    print("NEW SCORING LOGIC ACTIVE")
    gpa = profile.gpa
    adm_rate = to_float(row.get("ADM_RATE"))

    # Simulate college GPA benchmarks if missing
    sat_75 = first_numeric(row, ["SAT_AVG_ALL", "SAT_AVG", "SATMT75", "SATVR75"])
    sat_50 = first_numeric(row, ["SAT_AVG_ALL", "SAT_AVG", "SATMTMID", "SATVRMID"])
    sat_25 = first_numeric(row, ["SATMT25", "SATVR25"])

    if sat_50 is None:
        if adm_rate is None:
            adm_rate = random.uniform(0.25, 0.9)
        sat_50 = lerp(adm_rate, 0.1, 0.9, 1320, 920)
    if sat_25 is None:
        sat_25 = sat_50 - random.uniform(80, 160)
    if sat_75 is None:
        sat_75 = sat_50 + random.uniform(80, 160)

    sat_25, sat_50, sat_75 = sorted([sat_25, sat_50, sat_75])

    gpa_25 = sat_to_gpa(sat_25)
    gpa_50 = sat_to_gpa(sat_50)
    gpa_75 = sat_to_gpa(sat_75)

    # Ensure percentile ordering to avoid flat or inverted scoring.
    gpa_25, gpa_50, gpa_75 = sorted([gpa_25, gpa_50, gpa_75])

    # Step 1: Base GPA score using percentile bands and lerp.
    if gpa >= gpa_75:
        score = lerp(gpa, gpa_75, 4.0, 80, 95)
    elif gpa >= gpa_50:
        score = lerp(gpa, gpa_50, gpa_75, 40, 60)
    elif gpa >= gpa_25:
        score = lerp(gpa, gpa_25, gpa_50, 15, 40)
    else:
        score = lerp(gpa, 0.0, gpa_25, 5, 14)

    # Step 2: SAT bonus
    test_score = profile.sat

    if test_score:
        sat_delta = test_score - sat_50
        sat_bonus = clamp(lerp(sat_delta, -320, 320, -4, 8), -4, 8)
        score += sat_bonus

    # Step 3: Extracurricular bonus
    activities = profile.extracurriculars or []
    if len(activities) >= 5:
        score += 7.0
    elif len(activities) >= 3:
        score += 4.0
    elif len(activities) >= 1:
        score += 2.0

    # Slight selectivity adjustment: lower admission rates indicate tougher academic competition.
    if adm_rate is not None:
        score += lerp(adm_rate, 0.1, 0.9, -4, 2)

    # Step 4: Required random noise to avoid identical outputs.
    score += random.uniform(-8, 8)

    # Step 5: Clamp score.
    score = clamp(score, 0, 98)
    if score > 98:
        score = 98
    return score

def income_to_column(income):
    if income <= 30000:
        return "NPT41"
    elif income <= 48000:
        return "NPT42"
    elif income <= 75000:
        return "NPT43"
    elif income <= 110000:
        return "NPT44"
    else:
        return "NPT45"


def npt_candidates(income, row):
    base = income_to_column(income)

    control = to_float(row.get("CONTROL"))
    if control == 1:
        preferred = "PUB"
    elif control == 2:
        preferred = "PRIV"
    elif control == 3:
        preferred = "PROG"
    else:
        preferred = "OTHER"

    candidates = [
        f"{base}_{preferred}",
        f"{base}_PUB",
        f"{base}_PRIV",
        f"{base}_PROG",
        f"{base}_OTHER",
    ]

    return candidates
    

def calculate_need(profile, row):
    try:
        net_price = first_numeric(row, npt_candidates(profile.family_income, row))
        sticker_price = to_float(row.get("COSTT4_A"))

        if net_price is None or sticker_price is None or sticker_price == 0:
            score = random.uniform(20, 80)
        else:
            ratio = net_price / sticker_price

            if ratio <= 0.2:
                score = 95
            elif ratio <= 0.4:
                score = 80
            elif ratio <= 0.6:
                score = 60
            elif ratio <= 0.8:
                score = 30
            else:
                score = 10

        score += random.uniform(-8, 8)

        score = clamp(score, 0, 98)
        return score
    except Exception as e:
        print(f"Error in calculate_need: {e}")
        return random.uniform(20, 60)
    
from data_loader import get_data

def generate_matches(profile):
    df = get_data()

    results = []

    # Step 1: normalize weights
    total = profile.achievement_weight + profile.need_weight
    if total == 0:
        w_ach = 0.5
        w_need = 0.5
    else:
        w_ach = profile.achievement_weight / total
        w_need = profile.need_weight / total

    # Step 2: loop through colleges
    for _, row in df.iterrows():
        institution_name = str(row.get("INSTNM", "")).strip()
        sticker_price = to_float(row.get("COSTT4_A"))

        # Skip institutions with missing key fields.
        if not institution_name:
            continue
        if sticker_price is None or sticker_price <= 0:
            continue

        ach_score = calculate_achievement(profile, row)
        need_score = calculate_need(profile, row)

        # Step 3: combine scores using raw floats for ranking.
        overall = (ach_score * w_ach) + (need_score * w_need)

        logic_summary = build_logic_summary(ach_score, need_score)

        # Step 4: create result
        result = {
            "program": institution_name + " / Institutional Grant",

            "achievement_match": f"{round(float(ach_score), 1):.1f}%",
            "achievement_label": get_label(ach_score),

            "need_match": f"{round(float(need_score), 1):.1f}%",
            "need_label": get_label(need_score),

            "logic_summary": logic_summary,

            "overall": overall
        }

        results.append(result)

    # Step 5: sort results
    results = sorted(results, key=lambda x: x["overall"], reverse=True)

    # Step 6: take top 10
    top_10 = results[:10]

    # Step 7: assign rank
    for i, item in enumerate(top_10, start=1):
        item["rank"] = i
        del item["overall"]

    return top_10