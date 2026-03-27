from openai import OpenAI
import json

JUDGE_PROMPT = """
You are an expert evaluator of interview question generation systems.

Evaluate outputs based on:
1. Relevance to job description
2. Personalization using resume
3. Difficulty alignment
4. Clarity

Return STRICT JSON:

{
  "scores": {
    "zero_shot": {"total": 0},
    "few_shot": {"total": 0},
    "chain_of_thought": {"total": 0},
    "role_based": {"total": 0},
    "structured": {"total": 0}
  },
  "best_prompt": "",
  "reason": ""
}
"""

PROMPT_MAP = {
    "Zero-Shot Prompting": "zero_shot",
    "Few-Shot Learning": "few_shot",
    "Chain-of-Thought": "chain_of_thought",
    "Role-Based Prompting": "role_based",
    "Structured Output Prompt": "structured",
}

def judge_outputs(outputs, api_key, model):
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": json.dumps(outputs)}
        ]
    )

    try:
        return json.loads(response.choices[0].message.content)
    except:
        return None
        