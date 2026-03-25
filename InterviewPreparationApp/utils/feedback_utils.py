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

    # Offensive / disallowed themes (basic string/regex checks).
    offensive_terms = [
        # self-harm / violence
        "kill yourself",
        "suicide",
        "self-harm",
        # sexual / porn
        "porn",
        "nudes",
        "nude ",
        "explicit sex",
        # slurs / hate
        "nigger",
        "faggot",
        "queer ",
        "kike",
        # violence instructions / threats
        "how to kill",
        "bomb",
        "make a bomb",
        "shooting",
        "weapon",
        # harassment
        "hate you",
        "go die",
    ]
    if any(term in lowered for term in offensive_terms):
        return False, "Blocked content detected."

    # Prompt-injection / jailbreak patterns (treat as unsafe user input).
    injection_patterns = [
        r"ignore (all|previous|any) instructions",
        r"override (the )?(system|developer) prompt",
        r"system prompt",
        r"developer message",
        r"assistant role",
        r"jailbreak",
        r"prompt injection",
        r"disregard (the )?above",
        r"act as an ai",
        r"reveal (the )?(system|developer) prompt",
    ]
    for pat in injection_patterns:
        if re.search(pat, lowered, flags=re.IGNORECASE):
            return False, "Unsafe prompt injection detected."

    # Additional irrelevant-content heuristic: block if it looks like instruction-tampering.
    tamper_hints = [
        "as a system",
        "as a developer",
        "you are now",
        "respond exactly",
        "without obeying",
    ]
    if any(h in lowered for h in tamper_hints) and ("resume" in lowered or "job description" in lowered or "answer" in lowered):
        return False, "Unsafe or irrelevant instruction detected."

    return True, ""