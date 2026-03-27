import streamlit as st
import time
import json
import hashlib
import streamlit.components.v1 as components
from utils.file_utils import extract_text_from_file, validate_uploaded_file, MAX_FILE_BYTES
from utils.prompt_utils import build_messages, get_openai_response, validate_openai_api_key, try_parse_json
from utils.feedback_utils import analyze_answers, basic_content_filter
from utils.judge_utils import judge_outputs, PROMPT_MAP


# --- Improved UI: Sidebar Branding ---
st.set_page_config(page_title="AI Mock Interview", layout="wide")
st.markdown(
    """
<style>
    .stApp {
        background:
            radial-gradient(circle at 10% 10%, #eef4ff 0%, transparent 30%),
            radial-gradient(circle at 90% 20%, #e9f8f3 0%, transparent 35%),
            linear-gradient(180deg, #f8faff 0%, #f2f6ff 100%);
    }
    .block-container {
        max-width: 980px;
        margin: 0 auto;
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }
    .section-card {
        background: #ffffff;
        border: 1px solid #dbe4ff;
        border-radius: 12px;
        padding: 14px 16px 10px 16px;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(28, 52, 123, 0.06);
    }
    .section-title {
        font-weight: 700;
        color: #1f3b87;
        margin-bottom: 0.3rem;
    }
    .section-subtitle {
        color: #4b5b88;
        font-size: 0.93rem;
        margin-bottom: 0.6rem;
    }
    .stButton>button {
        background: #1f6feb;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 0.45rem 0.85rem;
        font-weight: 600;
    }
    .stButton>button:hover {
        background: #1559c0;
    }
    .compact-row .stButton>button {
        width: 100%;
    }
    div[data-testid="stAlert"] {
        border-radius: 10px;
    }
</style>
""",
    unsafe_allow_html=True,
)
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/artificial-intelligence.png", width=64)
    st.markdown("# InterviewPrep AI")
    st.markdown("AI-powered interview practice for any role.")
    st.markdown("---")
    st.markdown("**How it works:**\n1. Enter your details\n2. Upload or paste your job description and resume\n3. Choose difficulty & settings\n4. Get personalized questions & feedback!")

st.markdown("<h1 style='text-align:center; color:#1d3269;'>AI Mock Interview</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; color:#4a5b8a;'>Practice role-focused technical and personality interviews with instant AI feedback.</p>",
    unsafe_allow_html=True,
)

# One-click full reset (helpful for refresh/rerun scenarios)
def _reset_app_state() -> None:
    defaults = {
        "candidate_name": "",
        "api_key_input": "",
        "selected_model": "gpt-4.1-mini",
        "jd_use_upload": False,
        "resume_use_upload": False,
        "difficulty_level": "Beginner",
        "advanced_settings_toggle": False,
        "question_category": "Technical Questions",
        "api_key_valid": None,
        "api_key_hash_last_checked": "",
        "api_key_last_checked_model": "",
    }
    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)
    for key, value in defaults.items():
        st.session_state[key] = value
    st.rerun()

top_c1, top_c2 = st.columns([4, 1])
with top_c2:
    if st.button("Reset App", key="reset_app_top"):
        _reset_app_state()

st.markdown("---")

# --- Candidate Details (name) ---
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Candidate Details</div>", unsafe_allow_html=True)
st.markdown("<div class='section-subtitle'>Enter your basic profile information.</div>", unsafe_allow_html=True)
name = st.text_input("Your Name*", max_chars=50, help="Enter your full name.", key="candidate_name")
st.markdown("</div>", unsafe_allow_html=True)

# --- Job Description & Resume Section ---
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Job Description and Resume</div>", unsafe_allow_html=True)
st.markdown("<div class='section-subtitle'>Upload PDF/DOCX files or paste text for both sections.</div>", unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Job Description***")
    jd_use_upload = st.toggle("Upload job description instead of text", value=False, key="jd_use_upload")
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
    st.markdown("**Profile / Resume***")
    resume_use_upload = st.toggle("Upload your resume instead of text", value=False, key="resume_use_upload")
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
st.markdown("</div>", unsafe_allow_html=True)

# --- AI model settings (model first, then API key) ---
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>AI Model and API</div>", unsafe_allow_html=True)
st.markdown("<div class='section-subtitle'>Choose model access and validate your API key.</div>", unsafe_allow_html=True)
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

# Separate model for judge (stronger model)
judge_model = "gpt-4o"  # more reliable for evaluation

# --- API Key Field with Validation (masked, validate on change) ---
if "api_key_valid" not in st.session_state:
    st.session_state["api_key_valid"] = None
if "api_key_hash_last_checked" not in st.session_state:
    st.session_state["api_key_hash_last_checked"] = ""
if "api_key_last_checked_model" not in st.session_state:
    st.session_state["api_key_last_checked_model"] = ""


def _validate_key_if_changed(api_key_val: str, model: str) -> None:
    api_key_val = (api_key_val or "").strip()
    if not api_key_val:
        st.session_state["api_key_valid"] = None
        st.session_state["api_key_hash_last_checked"] = ""
        st.session_state["api_key_last_checked_model"] = ""
        return

    api_key_hash = hashlib.sha256(api_key_val.encode("utf-8")).hexdigest()
    if (
        api_key_hash == st.session_state.get("api_key_hash_last_checked", "")
        and model == st.session_state.get("api_key_last_checked_model", "")
    ):
        return
    st.session_state["api_key_valid"] = validate_openai_api_key(api_key_val, model=model)
    st.session_state["api_key_hash_last_checked"] = api_key_hash
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
    st.success("API key is valid for selected model.")
elif st.session_state["api_key_valid"] is False:
    st.error("Invalid API key for this model.")
st.markdown("</div>", unsafe_allow_html=True)

# --- Interview Settings ---
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Interview Settings</div>", unsafe_allow_html=True)
st.markdown("<div class='section-subtitle'>Select difficulty and optional advanced controls.</div>", unsafe_allow_html=True)
difficulty = st.selectbox(
    "Select Difficulty Level*",
    ["Beginner", "Intermediate", "Advanced"],
    help="Choose your practice level.",
    key="difficulty_level",
)
use_judge = st.toggle("Auto-select best prompt (LLM Judge)", value=True)

st.caption(f"Mode: {'Auto (LLM Judge)' if use_judge else 'Manual'}")

# --- Advanced Settings Toggle ---
advanced_settings = st.toggle("Advanced settings", value=False, key="advanced_settings_toggle")

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
st.markdown("</div>", unsafe_allow_html=True)


# --- Start Interview Button ---
st.markdown("<div style='text-align:center; margin-top:2em;'>", unsafe_allow_html=True)
start_btn = st.button("Start Interview", use_container_width=True)
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


def _generate_questions(*, jd_val: str, resume_val: str) -> dict[str, list[str]]:
    # Centralized prompt-building:
    # - ensures prompt injection guard is present
    # - ensures the selected prompt technique changes the system message
    # - ensures output is deterministic JSON for reliable parsing
    messages = build_messages(
        jd_text=jd_val,
        resume_text=resume_val,
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

    parsed = try_parse_json(raw)
    if not isinstance(parsed, dict):
        # Best-effort: extract the first JSON object from the model response.
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = try_parse_json(raw[start : end + 1])
    out = {"technical": [], "personality": []}
    if isinstance(parsed, dict):
        tech = parsed.get("technical") or []
        pers = parsed.get("personality") or []
        if isinstance(tech, list):
            out["technical"] = [str(x).strip() for x in tech if str(x).strip()][:10]
        if isinstance(pers, list):
            out["personality"] = [str(x).strip() for x in pers if str(x).strip()][:10]

    return out


def _generate_questions_with_judge(jd_val, resume_val):
    prompt_types = [
        "Zero-Shot Prompting",
        "Few-Shot Learning",
        "Chain-of-Thought",
        "Role-Based Prompting",
        "Structured Output Prompt",
    ]

    outputs = {}

    for pt in prompt_types:
        messages = build_messages(
            jd_text=jd_val,
            resume_text=resume_val,
            difficulty=difficulty,
            prompt_technique=pt,
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

        parsed = try_parse_json(raw)
        if isinstance(parsed, dict):
            outputs[PROMPT_MAP[pt]] = parsed

    if not outputs:
        return {"technical": [], "personality": []}

    judge_result = judge_outputs(outputs, api_key, judge_model)

    if judge_result and "best_prompt" in judge_result:
        best = judge_result["best_prompt"]
        st.success(f"Best Prompt Selected: {best}")
        return outputs.get(best, list(outputs.values())[0])

    return list(outputs.values())[0]

def _finalize_interview(name: str) -> None:
    responses = st.session_state.get("responses", {"technical": [], "personality": []})
    questions_map = st.session_state.get("question_bank", {"technical": [], "personality": []})
    questions = (questions_map.get("technical") or []) + (questions_map.get("personality") or [])
    answers = (responses.get("technical") or []) + (responses.get("personality") or [])

    total_questions = len(questions)
    substantive_count = sum(1 for a in answers if (a or "").strip())
    # Questions without a real answer (never reached, skipped empty, or still pending)
    unanswered_count = total_questions - substantive_count

    limited, msg = _rate_limited(name.strip().lower() or "anonymous")
    if limited:
        st.error(msg)
        st.stop()

    if substantive_count == 0:
        # Do not call the model for "interview performance" — it would hallucinate from JD/resume alone.
        st.session_state["performance_applicable"] = False
        st.session_state["score"] = 0
        st.session_state["strengths"] = [
            "No written answers were submitted, so interview performance was not evaluated.",
        ]
        st.session_state["improvements"] = [
            "Use Submit & Next or Skip on each question to record an attempt, or answer fully for real scoring.",
        ]
    else:
        st.session_state["performance_applicable"] = True
        answered_only = [a for a in answers if a.strip()]
        score, strengths, improvements = analyze_answers(answered_only)
        ai_fb = _ai_feedback(
            questions=questions,
            answers=answers,
            jd_val=st.session_state["jd_source_text"],
            resume_val=st.session_state["resume_source_text"],
        )
        if isinstance(ai_fb, dict) and ai_fb.get("overall_score_0_100") is not None:
            try:
                score = int(float(ai_fb.get("overall_score_0_100")))
            except Exception:
                pass
            strengths = ai_fb.get("strengths") or strengths
            improvements = ai_fb.get("areas_for_improvement") or improvements
        st.session_state["score"] = score
        st.session_state["strengths"] = strengths
        st.session_state["improvements"] = improvements


    st.session_state["unanswered_count"] = unanswered_count
    st.session_state.pop("question_bank", None)
    st.session_state.pop("progress", None)
    st.session_state.pop("responses", None)
    st.rerun()


def _ai_feedback(*, questions: list[str], answers: list[str], jd_val: str, resume_val: str) -> dict:
    padded_answers = list(answers)
    while len(padded_answers) < len(questions):
        padded_answers.append("")
    system = (
        "You are a strict interview evaluator. "
        "Derive overall_score_0_100, strengths, and areas_for_improvement ONLY from the candidate's non-empty answers in qa. "
        "Treat empty answers as not evaluated — do not infer interview performance from the job description or resume. "
        "Do not list strengths that are not clearly demonstrated in those answers. "
        "Be concise. Do not be offensive."
    )
    user = {
        "context_job_description": jd_val,
        "context_resume": resume_val,
        "note": "JD and resume are context only; do not score from them directly.",
        "qa": [{"q": q, "a": a} for q, a in zip(questions, padded_answers)],
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

            #question_bank = _generate_questions(jd_val=jd_text_val, resume_val=resume_text_val)
            if use_judge:
                question_bank = _generate_questions_with_judge(jd_text_val, resume_text_val)
            else:
                question_bank = _generate_questions(jd_val=jd_text_val, resume_val=resume_text_val)
            
            if not question_bank.get("technical") or not question_bank.get("personality"):
                st.error("Could not generate questions. Try switching prompt technique or simplifying inputs.")
                st.stop()

        # Ensure exactly 10 each (fallback fill if model returns fewer)
        tech = (question_bank.get("technical") or [])[:10]
        pers = (question_bank.get("personality") or [])[:10]
        if len(tech) < 10:
            tech += [f"Technical question placeholder {i+1}" for i in range(len(tech), 10)]
        if len(pers) < 10:
            pers += [f"Personality question placeholder {i+1}" for i in range(len(pers), 10)]

        st.session_state["question_bank"] = {"technical": tech, "personality": pers}
        st.session_state["progress"] = {"technical": 0, "personality": 0}
        st.session_state["responses"] = {"technical": [], "personality": []}
        st.session_state['jd_source_text'] = jd_text_val
        st.session_state['resume_source_text'] = resume_text_val
        st.rerun()

# --- Question/Answer Loop ---
if "question_bank" in st.session_state and "progress" in st.session_state and "responses" in st.session_state:
    qbank = st.session_state["question_bank"]
    progress = st.session_state["progress"]
    responses = st.session_state["responses"]

    category_label = st.selectbox(
        "Select question category",
        ["Technical Questions", "Personality Tests"],
        key="question_category",
    )
    cat = "technical" if category_label == "Technical Questions" else "personality"
    idx = progress.get(cat, 0)
    total_attempted = progress.get("technical", 0) + progress.get("personality", 0)

    m1, m2 = st.columns(2)
    with m1:
        st.metric("Overall Progress", f"{total_attempted}/20")
        st.progress(total_attempted / 20)
    with m2:
        st.metric(f"{category_label} Progress", f"{idx}/10")
        st.progress(idx / 10)

    if idx >= 10:
        st.info(f"All 10 {category_label.lower()} are already completed. Switch category or end interview.")
        if st.button("End Interview", key=f"end_interview_done_{cat}"):
            _finalize_interview(name)
    else:
        st.header(f"{category_label} - Question {idx + 1} of 10")
        st.write(qbank[cat][idx])
        answer_key = f"answer_{cat}_{idx}"
        # Speech-to-text (Web Speech API) helper for this specific Streamlit textarea.
        # We attempt to populate the target textarea using its DOM id that includes the widget key.
        # If the browser doesn't support speech recognition, the mic button is disabled.
        answer_label = f"Your Answer (optional) [{category_label} {idx+1}/10]"
        answer_label_js = json.dumps(answer_label)
        a_col, mic_col = st.columns([10, 1])
        with a_col:
            user_answer = st.text_area(answer_label, key=answer_key)

        mic_btn_id = f"stt_mic_{answer_key}".replace("-", "_")
        stt_html = f"""
<div style="display:flex; align-items:flex-start; justify-content:center;">
  <button id="{mic_btn_id}" type="button"
    style="width:38px; height:38px; border-radius:12px; border:1px solid rgba(31,111,235,0.25);
           background:#f0f5ff; cursor:pointer; display:flex; align-items:center; justify-content:center;"
    title="Click to speak. Click again to stop.">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" stroke="#1f6feb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M19 11a7 7 0 0 1-14 0" stroke="#1f6feb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M12 18v2" stroke="#1f6feb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M9 20h6" stroke="#1f6feb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M4 21c2-1 4-3 6-6" stroke="#1f6feb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.35"/>
      <path d="M20 21c-2-1-4-3-6-6" stroke="#1f6feb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.35"/>
    </svg>
  </button>
</div>
<div id="{mic_btn_id}_status" style="text-align:center; font-size:10px; color:#4b5b88; margin-top:2px; height:12px;"></div>
<script>
(function() {{
  const btn = document.getElementById("{mic_btn_id}");
  const statusEl = document.getElementById("{mic_btn_id}_status");
  const targetKey = "{answer_key}";
  const ariaLabel = {answer_label_js};
  let recognition = null;
  let isRecording = false;
  let finalTranscript = '';

  function escapeCss(s) {{
    return s.replace(/([ #;?%&,.+*~':"!^$[\]()=>|\\/\\\\@])/g, '\\\\$1');
  }}

  function getTextarea() {{
    // Try common possibilities: direct id match, partial id match, aria-label match.
    const parentDoc = window.parent.document;
    let el = parentDoc.getElementById(targetKey);
    if (el && el.tagName && el.tagName.toLowerCase() === 'textarea') return el;
    try {{
      el = parentDoc.querySelector('textarea[aria-label=\"' + ariaLabel + '\"]');
      if (el) return el;
    }} catch(e) {{}}
    try {{
      const esc = (typeof CSS !== 'undefined' && CSS.escape) ? CSS.escape(targetKey) : escapeCss(targetKey);
      el = parentDoc.querySelector('textarea[id*=\"' + esc + '\"]');
      if (el) return el;
    }} catch(e) {{}}

    // Fallback: match textarea whose id contains the widget key substring.
    const all = parentDoc.querySelectorAll('textarea');
    for (let i=0; i<all.length; i++) {{
      const id = all[i].getAttribute('id') || '';
      if (id.includes(targetKey)) return all[i];
    }}
    return null;
  }}

  function setTextareaValue(text) {{
    const ta = getTextarea();
    if (!ta) {{
      if (statusEl) statusEl.innerText = 'Textarea not found';
      return;
    }}
    // React/Streamlit listens to input/change; dispatch a stronger set of events
    // Use native value setter to avoid React/Streamlit value tracking issues.
    const proto = Object.getPrototypeOf(ta);
    const valueDesc = Object.getOwnPropertyDescriptor(proto, 'value')
      || Object.getOwnPropertyDescriptor(Object.getPrototypeOf(proto), 'value');
    if (valueDesc && valueDesc.set) {{
      valueDesc.set.call(ta, text);
    }} else {{
      ta.value = text;
    }}
    ta.setAttribute('value', text);
    ta.focus();
    try {{
      ta.dispatchEvent(new InputEvent('input', {{
        bubbles: true,
        composed: true,
        inputType: 'insertText',
        data: text
      }}));
    }} catch (e) {{
      ta.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
    }}
    ta.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
    ta.dispatchEvent(new Event('blur', {{ bubbles: true, composed: true }}));
    ta.blur();
    // Extra events to help Streamlit's widget change-detection catch it.
    try {{
      ta.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true, composed: true, key: 'SpeechInput' }}));
      ta.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, composed: true, key: 'SpeechInput' }}));
    }} catch (e) {{}}
    // Re-dispatch on next frame (helps when users click immediately after stopping).
    try {{
      window.requestAnimationFrame(() => {{
        try {{
          ta.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
          ta.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
        }} catch(e) {{}}
      }});
    }} catch(e) {{}}
  }}

  function setButtonRecording(on) {{
    if (!btn) return;
    isRecording = on;
    btn.style.background = on ? '#fee2e2' : '#f0f5ff';
    btn.style.borderColor = on ? 'rgba(239,68,68,0.6)' : 'rgba(31,111,235,0.25)';
    if (statusEl) statusEl.innerText = on ? 'Listening…' : '';
    const svgPaths = btn.querySelectorAll('path');
    // Change stroke colors while recording.
    svgPaths.forEach(p => {{
      p.setAttribute('stroke', on ? '#ef4444' : '#1f6feb');
    }});
  }}

  function startRec() {{
    // Web Speech API is not always available on the iframe window; check parent too.
    const SR =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition ||
      window.parent.SpeechRecognition ||
      window.parent.webkitSpeechRecognition;
    if (!SR) {{
      btn && (btn.disabled = true);
      if (statusEl) statusEl.innerText = 'SpeechRecognition not supported';
      return;
    }}

    finalTranscript = '';
    recognition = new SR();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    recognition.onresult = (event) => {{
      let interim = '';
      let anyFinal = '';
      for (let i = 0; i < event.results.length; i++) {{
        interim += event.results[i][0].transcript;
        if (event.results[i].isFinal) {{
          anyFinal += event.results[i][0].transcript;
        }}
      }}
      if (anyFinal.trim()) {{
        finalTranscript = anyFinal;
        setTextareaValue(finalTranscript.trim());
        if (statusEl) statusEl.innerText = 'Captured ✔';
      }} else {{
        // Live update in the textbox (felt nicer for users).
        setTextareaValue(interim.trim());
        if (statusEl) statusEl.innerText = 'Listening…';
      }}
    }};

    recognition.onstart = () => {{
      setButtonRecording(true);
    }};

    recognition.onend = () => {{
      setButtonRecording(false);
      // Ensure final value is set (last interim is usually final).
      if (finalTranscript && finalTranscript.trim()) {{
        setTextareaValue(finalTranscript.trim());
      }}
    }};

    recognition.onerror = (event) => {{
      setButtonRecording(false);
      if (statusEl) statusEl.innerText = 'Mic error: ' + (event && event.error ? event.error : 'unknown');
    }};

    try {{
      if (statusEl) statusEl.innerText = 'Requesting microphone…';
    recognition.start();
      setButtonRecording(true);
    }} catch (e) {{
      setButtonRecording(false);
      if (statusEl) statusEl.innerText = 'Mic start failed';
    }}
  }}

  function stopRec() {{
    try {{
      recognition && recognition.stop();
    }} catch(e) {{}}
    setButtonRecording(false);
    if (finalTranscript && finalTranscript.trim()) {{
      setTextareaValue(finalTranscript.trim());
      // Nudge Streamlit's listeners a moment later (covers immediate Submit click).
      try {{
        const ta = getTextarea();
        window.setTimeout(() => {{
          if (!ta) return;
          try {{
            ta.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true }}));
            ta.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
          }} catch(e) {{}}
        }}, 120);
      }} catch(e) {{}}
    }}
  }}

  if (btn) {{
    btn.addEventListener('click', () => {{
      if (!isRecording) startRec();
      else stopRec();
    }});
  }}
}})();
</script>
"""
        with mic_col:
            components.html(stt_html, height=84)

        st.markdown("<div class='compact-row'>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.5, 1.1, 1.1], gap="small")
        with c1:
            submit_next = st.button("Submit & Next")
        with c2:
            skip_btn = st.button("Skip Question")
        with c3:
            end_btn = st.button("End Interview", key=f"end_interview_{cat}_{idx}")
        st.markdown("</div>", unsafe_allow_html=True)

        if submit_next:
            if user_answer.strip():
                ok_ans, reason_ans = basic_content_filter(user_answer)
                if not ok_ans:
                    st.error(f"Answer blocked: {reason_ans}")
                    st.stop()
            responses[cat].append(user_answer.strip())
            progress[cat] = min(10, idx + 1)
            st.session_state["responses"] = responses
            st.session_state["progress"] = progress
            if progress.get("technical", 0) + progress.get("personality", 0) >= 20:
                _finalize_interview(name)
            st.rerun()

        if skip_btn:
            responses[cat].append("")
            progress[cat] = min(10, idx + 1)
            st.session_state["responses"] = responses
            st.session_state["progress"] = progress
            if progress.get("technical", 0) + progress.get("personality", 0) >= 20:
                _finalize_interview(name)
            st.rerun()
        
        if end_btn:
            _finalize_interview(name)

# --- Feedback/Results ---
if 'score' in st.session_state:
    st.header("Interview Review")
    st.subheader(f"{name}")
    if st.session_state.get("performance_applicable", True):
        st.markdown(f"### Overall Performance Score\n**{st.session_state['score']}/100**")
        if st.session_state['score'] >= 70:
            st.success("Great job! You're well prepared.")
        elif st.session_state['score'] >= 40:
            st.info("Decent attempt. Review the feedback below.")
        else:
            st.warning("Needs improvement. See areas below.")
    else:
        st.info(
            "**Performance score:** Not generated — you ended the interview before submitting any answers. "
            "Resume–JD matching below still reflects your documents."
        )
    st.markdown("---")
    st.markdown("#### Strengths")
    for s in st.session_state['strengths']:
        st.markdown(f"- {s}")
    st.markdown("#### Areas for Improvement")
    for i in st.session_state['improvements']:
        st.markdown(f"- {i}")
    else:
        st.success("No major skill gaps detected!")
    st.markdown(f"#### Unanswered Questions\n**{st.session_state.get('unanswered_count', 0)}**")
    if st.button("Restart Interview"):
        for k in [
            'score',
            'strengths',
            'improvements',
            'jd_source_text',
            'resume_source_text',
            'unanswered_count',
            'performance_applicable',
            'question_bank',
            'progress',
            'responses',
        ]:
            if k in st.session_state:
                st.session_state.pop(k)
        st.rerun()
