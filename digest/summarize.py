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
        f"Summarize the following article for a daily e-reader digest. "
        f"Write the summary in {language}, as 2-4 short sentences plus, if useful, "
        f"a couple of key-point bullets. No preamble, no markdown headings, "
        f"just the summary text.\n\n"
        f"Title: {title}\n\nArticle:\n{text}"
    )


def summarize_article(title: str, text: str, conf: dict) -> str:
    prompt = _build_prompt(title, text, conf["language"])
    provider = conf["provider"]
    model = conf["model"]

    if provider == "gemini":
        client = _get_gemini_client()
        resp = _call_with_retry(
            lambda: client.models.generate_content(model=model, contents=prompt)
        )
        return resp.text.strip()

    if provider == "openai":
        client = _get_openai_client(conf.get("openai_base_url"))
        resp = _call_with_retry(
            lambda: client.chat.completions.create(
                model=model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return resp.choices[0].message.content.strip()

    raise ValueError(f"Unknown provider: {provider!r} (expected 'gemini' or 'openai')")
