from difflib import SequenceMatcher
from collections import Counter
import re

def analyze_answers(answers):
    # Dummy scoring logic for demonstration
    score = 0
    strengths = []
    improvements = []
    for ans in answers:
        if len(ans) > 50:
            score += 10
            strengths.append("Detailed answer")
        else:
            improvements.append("Expand your answers with more details.")
    score = min(100, score)
    return score, list(set(strengths)), list(set(improvements))

def extract_keywords(text):
    # Simple keyword extraction: words > 3 chars, not common stopwords
    stopwords = set(['the', 'and', 'for', 'with', 'that', 'have', 'this', 'from', 'your', 'are', 'was', 'but', 'not', 'all', 'any', 'can', 'had', 'her', 'his', 'our', 'out', 'has', 'who', 'you', 'use', 'how', 'job', 'will', 'get', 'one', 'now', 'per', 'may', 'she', 'him', 'its', 'let', 'put', 'set', 'too', 'via'])
    words = re.findall(r'\b\w{4,}\b', text.lower())
    keywords = [w for w in words if w not in stopwords]
    return set(keywords)

def match_resume_jd(jd_text, resume_text):
    jd_keywords = extract_keywords(jd_text)
    resume_keywords = extract_keywords(resume_text)
    missing = jd_keywords - resume_keywords
    return list(missing)


def basic_content_filter(text: str) -> tuple[bool, str]:
    """
    Lightweight local filter (non-exhaustive). Returns (ok, reason).
    """
    if not text or not text.strip():
        return False, "Empty content."
    lowered = text.lower()
    banned = [
        "kill yourself",
        "suicide",
        "nigger",
        "rape",
        "porn",
    ]
    if any(b in lowered for b in banned):
        return False, "Blocked content detected."
    return True, ""