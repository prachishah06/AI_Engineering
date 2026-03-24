import streamlit as st
import time
import json
from utils.file_utils import extract_text_from_file, validate_uploaded_file, MAX_FILE_BYTES
from utils.prompt_utils import build_messages, get_openai_response, validate_openai_api_key, try_parse_json
from utils.feedback_utils import analyze_answers, match_resume_jd, basic_content_filter


# --- Improved UI: Sidebar Branding ---
st.set_page_config(page_title="AI Mock Interview", layout="wide")
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/artificial-intelligence.png", width=64)
    st.markdown("# InterviewPrep AI")
    st.markdown("AI-powered interview practice for any role.")
    st.markdown("---")
    st.markdown("**How it works:**\n1. Enter your details\n2. Upload or paste your job description and resume\n3. Choose difficulty & settings\n4. Get personalized questions & feedback!")

st.markdown("<h1 style='text-align:center;'>🧑‍💻 AI Mock Interview</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Let's prepare you for your interview. Fill in your details to get personalized questions.</p>", unsafe_allow_html=True)

st.markdown("---")

# --- Candidate Details (name) ---
st.markdown("### 👤 Candidate Details")
name = st.text_input("Your Name*", max_chars=50, help="Enter your full name.")

st.markdown("---")

# --- Job Description & Resume Section ---
st.markdown("### 📄 Job Description & Resume")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**What's the job description?***")
    jd_use_upload = st.toggle("Upload job description instead of text", value=True)
    jd_text = ""
    jd_file = None
    if jd_use_upload:
        jd_file = st.file_uploader(
            f"Job Description file (PDF/DOCX, ≤{MAX_FILE_BYTES // (1024 * 1024)}MB)*",
            type=["pdf", "docx"],
            key="jd_file",
        )
    else:
        jd_text = st.text_area("Job Description text (max 500 chars)*", max_chars=500, height=140, key="jd_text")
with col2:
    st.markdown("**What's the profile?***")
    resume_use_upload = st.toggle("Upload your resume instead of text", value=True)
    resume_text = ""
    resume_file = None
    if resume_use_upload:
        resume_file = st.file_uploader(
            f"Resume file (PDF/DOCX, ≤{MAX_FILE_BYTES // (1024 * 1024)}MB)*",
            type=["pdf", "docx"],
            key="resume_file",
        )
    else:
        resume_text = st.text_area("Resume/Profile text (max 500 chars)*", max_chars=500, height=140, key="resume_text")

st.markdown("---")

# --- AI model settings (model first, then API key) ---
st.markdown("### 🤖 AI model")
model_list = [
    "gpt-4o-mini-2024-07-18",
    "gpt-4o-mini",
    "codex-mini-latest",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-16k",
    "gpt-4.1-mini",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4.1-nano",
    "gpt-4.1-nano-2025-04-14",
    "text-embedding-ada-002",
    "text-embedding-3-small",
    "text-embedding-3-large",
    "omni-moderation-latest",
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-4o-mini-transcribe",
    "whisper-1",
]

selected_model = st.selectbox(
    "OpenAI Model*",
    model_list,
    index=model_list.index("gpt-4.1-mini"),
    help="Default is gpt-4.1-mini. Changing the model will re-validate your API key for that model.",
    key="selected_model",
)

# --- API Key Field with Validation (masked, validate on change) ---
if "api_key_valid" not in st.session_state:
    st.session_state["api_key_valid"] = None
if "api_key_last_checked" not in st.session_state:
    st.session_state["api_key_last_checked"] = ""
if "api_key_last_checked_model" not in st.session_state:
    st.session_state["api_key_last_checked_model"] = ""


def _validate_key_if_changed(api_key_val: str, model: str) -> None:
    api_key_val = (api_key_val or "").strip()
    if not api_key_val:
        st.session_state["api_key_valid"] = None
        st.session_state["api_key_last_checked"] = ""
        st.session_state["api_key_last_checked_model"] = ""
        return
    if (
        api_key_val == st.session_state.get("api_key_last_checked", "")
        and model == st.session_state.get("api_key_last_checked_model", "")
    ):
        return
    st.session_state["api_key_valid"] = validate_openai_api_key(api_key_val, model=model)
    st.session_state["api_key_last_checked"] = api_key_val
    st.session_state["api_key_last_checked_model"] = model


api_key = st.text_input(
    "OpenAI API Key*",
    type="password",
    help="Paste your OpenAI API key.",
    key="api_key_input",
)
st.caption("Key is validated against the selected model.")

_validate_key_if_changed(api_key, selected_model)

if st.session_state["api_key_valid"] is True:
    st.success("API Key is valid ✓")
elif st.session_state["api_key_valid"] is False:
    st.error("Invalid API Key for this model")

st.markdown("---")

# --- Interview Settings ---
st.markdown("### ⚙️ Interview Settings")
difficulty = st.selectbox("Select Difficulty Level*", ["Beginner", "Intermediate", "Advanced"], help="Choose your practice level.")


# --- Advanced Settings Toggle ---
advanced_settings = st.toggle("Advanced settings", value=False)

# Defaults required by spec
prompt_technique = "Role-Based Prompting"
temperature = 0.7
top_p = 0.9
freq_penalty = 0.3
pres_penalty = 0.3

if advanced_settings:
    st.markdown("#### 🧩 System prompt technique*")
    prompt_technique = st.selectbox(
        "Select a prompt technique*",
        [
            "Role-Based Prompting",
            "Zero-Shot Prompting",
            "Few-Shot Learning",
            "Chain-of-Thought",
            "Structured Output Prompt",
        ],
        index=0,
        help="Compulsory when advanced settings are enabled.",
    )

    st.markdown("#### 🤖 OpenAI settings")
    # Model is selected above; keep other settings here
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7)
    top_p = st.slider("Top-p", 0.0, 1.0, 0.9)
    freq_penalty = st.slider("frequency_penalty", 0.0, 1.0, 0.3)
    pres_penalty = st.slider("presence_penalty", 0.0, 1.0, 0.3)


# --- Start Interview Button ---
st.markdown("<div style='text-align:center; margin-top:2em;'>", unsafe_allow_html=True)
start_btn = st.button("🚀 Start Interview", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)


def _rate_limited(user_id: str, *, limit: int = 5, window_seconds: int = 60) -> tuple[bool, str]:
    now = time.time()
    if "rate_limit" not in st.session_state:
        st.session_state["rate_limit"] = {}
    bucket = st.session_state["rate_limit"].get(user_id, [])
    bucket = [t for t in bucket if now - t < window_seconds]
    if len(bucket) >= limit:
        retry_in = int(window_seconds - (now - min(bucket)))
        st.session_state["rate_limit"][user_id] = bucket
        return True, f"Rate limit exceeded: max {limit} requests/min. Try again in ~{retry_in}s."
    bucket.append(now)
    st.session_state["rate_limit"][user_id] = bucket
    return False, ""


def _get_text_inputs() -> tuple[str, str]:
    if jd_use_upload:
        ok, msg = validate_uploaded_file(jd_file)
        if not ok:
            raise ValueError(f"Job description: {msg}")
        jd_val = extract_text_from_file(jd_file)
    else:
        jd_val = (jd_text or "").strip()

    if resume_use_upload:
        ok, msg = validate_uploaded_file(resume_file)
        if not ok:
            raise ValueError(f"Resume: {msg}")
        resume_val = extract_text_from_file(resume_file)
    else:
        resume_val = (resume_text or "").strip()

    return jd_val, resume_val


def _generate_questions(*, jd_val: str, resume_val: str) -> list[str]:
    messages = build_messages(
        jd_val,
        resume_val,
        difficulty=difficulty,
        prompt_technique=prompt_technique,
        num_questions=10,
    )
    raw = get_openai_response(
        messages=messages,
        api_key=api_key,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=freq_penalty,
        presence_penalty=pres_penalty,
        model=selected_model,
    )
    if prompt_technique == "Structured Output Prompt":
        parsed = try_parse_json(raw)
        if isinstance(parsed, dict):
            items: list[str] = []
            for key in ["technical", "behavioral_star", "role_specific", "personality"]:
                for obj in parsed.get(key, []) or []:
                    q = (obj or {}).get("question")
                    if q:
                        items.append(str(q).strip())
            return [q for q in items if q]
    # fallback: numbered list parsing
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    cleaned: list[str] = []
    for ln in lines:
        cleaned.append(ln.lstrip("0123456789.:- ").strip())
    return [q for q in cleaned if q]


def _ai_feedback(*, questions: list[str], answers: list[str], jd_val: str, resume_val: str) -> dict:
    system = (
        "You are a strict but helpful interview evaluator. "
        "Score the candidate based on clarity, relevance to the role, correctness (when applicable), and STAR structure for behavioral answers. "
        "Do not be offensive. Keep it relevant."
    )
    user = {
        "job_description": jd_val,
        "resume": resume_val,
        "qa": [{"q": q, "a": a} for q, a in zip(questions, answers)],
        "required_output_json_schema": {
            "overall_score_0_100": "number",
            "strengths": ["string"],
            "areas_for_improvement": ["string"],
        },
    }
    raw = get_openai_response(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        api_key=api_key,
        temperature=0.3,
        top_p=0.9,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        model=selected_model,
    )
    parsed = try_parse_json(raw)
    if isinstance(parsed, dict):
        return parsed
    return {}


if start_btn:
    # validation
    if not name or not api_key:
        st.error("Name and OpenAI API Key are compulsory.")
    elif st.session_state.get("api_key_valid") is not True:
        st.error("Invalid API Key. Please check and try again.")
    else:
        with st.spinner("Processing inputs and generating questions..."):
            try:
                jd_text_val, resume_text_val = _get_text_inputs()
            except Exception as e:
                st.error(str(e))
                st.stop()

            ok_jd, reason_jd = basic_content_filter(jd_text_val)
            ok_res, reason_res = basic_content_filter(resume_text_val)
            if not ok_jd:
                st.error(f"Job description blocked: {reason_jd}")
                st.stop()
            if not ok_res:
                st.error(f"Resume/Profile blocked: {reason_res}")
                st.stop()

            limited, msg = _rate_limited(name.strip().lower() or "anonymous")
            if limited:
                st.error(msg)
                st.stop()

            questions = _generate_questions(jd_val=jd_text_val, resume_val=resume_text_val)
            if not questions:
                st.error("Could not generate questions. Try switching prompt technique or simplifying inputs.")
                st.stop()

        st.session_state['questions'] = questions
        st.session_state['answers'] = []
        st.session_state['jd_text'] = jd_text_val
        st.session_state['resume_text'] = resume_text_val
        st.session_state['step'] = 0
        st.experimental_rerun()

# --- Question/Answer Loop ---
if 'questions' in st.session_state and 'step' in st.session_state:
    questions = st.session_state['questions']
    step = st.session_state['step']
    answers = st.session_state.get('answers', [])
    st.header(f"Question {step+1} of {len(questions)}")
    st.write(questions[step])
    user_answer = st.text_area("Your Answer", key=f"answer_{step}")
    if st.button("Next"):
        if not user_answer.strip():
            st.warning("Please provide an answer before proceeding.")
        else:
            ok_ans, reason_ans = basic_content_filter(user_answer)
            if not ok_ans:
                st.error(f"Answer blocked: {reason_ans}")
                st.stop()
            answers.append(user_answer.strip())
            st.session_state['answers'] = answers
            if step + 1 < len(questions):
                st.session_state['step'] += 1
                st.experimental_rerun()
            else:
                # All questions answered, show feedback
                limited, msg = _rate_limited(name.strip().lower() or "anonymous")
                if limited:
                    st.error(msg)
                    st.stop()

                score, strengths, improvements = analyze_answers(answers)
                ai_fb = _ai_feedback(
                    questions=questions,
                    answers=answers,
                    jd_val=st.session_state["jd_text"],
                    resume_val=st.session_state["resume_text"],
                )
                if isinstance(ai_fb, dict) and ai_fb.get("overall_score_0_100") is not None:
                    try:
                        score = int(float(ai_fb.get("overall_score_0_100")))
                    except Exception:
                        pass
                    strengths = ai_fb.get("strengths") or strengths
                    improvements = ai_fb.get("areas_for_improvement") or improvements
                missing_keywords = match_resume_jd(st.session_state['jd_text'], st.session_state['resume_text'])
                st.session_state['score'] = score
                st.session_state['strengths'] = strengths
                st.session_state['improvements'] = improvements
                st.session_state['missing_keywords'] = missing_keywords
                st.session_state.pop('questions')
                st.session_state.pop('step')
                st.experimental_rerun()

# --- Feedback/Results ---
if 'score' in st.session_state:
    st.header("Interview Review")
    st.subheader(f"{name}")
    st.markdown(f"### Overall Performance Score\n**{st.session_state['score']}/100**")
    if st.session_state['score'] >= 70:
        st.success("Great job! You're well prepared.")
    elif st.session_state['score'] >= 40:
        st.info("Decent attempt. Review the feedback below.")
    else:
        st.warning("Needs improvement. See areas below.")
    st.markdown("---")
    st.markdown("#### Strengths")
    for s in st.session_state['strengths']:
        st.markdown(f"- {s}")
    st.markdown("#### Areas for Improvement")
    for i in st.session_state['improvements']:
        st.markdown(f"- {i}")
    st.markdown("#### Resume–JD Matching Insights")
    if st.session_state['missing_keywords']:
        missing = st.session_state['missing_keywords'][:40]
        st.error(f"Skill gaps / Missing keywords (sample): {', '.join(missing)}")
    else:
        st.success("No major skill gaps detected!")
    if st.button("Restart Interview"):
        for k in ['score', 'strengths', 'improvements', 'missing_keywords', 'answers', 'jd_text', 'resume_text']:
            if k in st.session_state:
                st.session_state.pop(k)
        st.experimental_rerun()
