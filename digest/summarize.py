import json
import os
import time

MAX_SOURCE_CHARS = 6000

_RETRY_ATTEMPTS = 4
_RETRY_BASE_DELAY = 20  # seconds; doubles each retry to ride out rate limits

_gemini_client = None
_openai_client = None


def _call_with_retry(fn):
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return fn()
        except Exception:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY * (2**attempt))


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _gemini_client


def _get_openai_client(base_url: str | None):
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url or None)
    return _openai_client


def _build_prompt(title: str, text: str, language: str) -> str:
    text = text[:MAX_SOURCE_CHARS]
    return (
        "Read the following article and respond with ONLY a single JSON object "
        "(no markdown code fences, no commentary before or after) with exactly "
        "these two keys:\n"
        f'- "summary": a 2-4 sentence summary in {language}, plus a couple of '
        "key-point bullets if useful, as one string using \\n for line breaks.\n"
        '- "qa": a list of exactly 3 objects, each with "question" and "answer" '
        f"keys, both written in {language}. Each question should be something a "
        "curious reader would naturally wonder after reading the summary "
        "(background, implications, related context), and each answer should be "
        "1-3 sentences.\n\n"
        f"Title: {title}\n\nArticle:\n{text}"
    )


def _parse_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise
        data = json.loads(text[start : end + 1])

    summary = str(data["summary"]).strip()
    qa = [
        {"question": str(item["question"]).strip(), "answer": str(item["answer"]).strip()}
        for item in data.get("qa", [])[:3]
    ]
    return {"summary": summary, "qa": qa}


def summarize_article(title: str, text: str, conf: dict) -> dict:
    prompt = _build_prompt(title, text, conf["language"])
    provider = conf["provider"]
    model = conf["model"]

    if provider == "gemini":
        client = _get_gemini_client()
        resp = _call_with_retry(
            lambda: client.models.generate_content(
                model=model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
        )
        return _parse_response(resp.text)

    if provider == "openai":
        client = _get_openai_client(conf.get("openai_base_url"))
        resp = _call_with_retry(
            lambda: client.chat.completions.create(
                model=model,
                max_tokens=800,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return _parse_response(resp.choices[0].message.content)

    raise ValueError(f"Unknown provider: {provider!r} (expected 'gemini' or 'openai')")
