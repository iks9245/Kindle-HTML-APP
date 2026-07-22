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


def _build_prompt(title: str, text: str, language: str, secondary_language: str | None = None) -> str:
    text = text[:MAX_SOURCE_CHARS]
    secondary_key = ""
    if secondary_language:
        secondary_key = (
            f'- "summary_secondary": the same summary written in {secondary_language} '
            "(same 2-4 sentence length and format), as one string using \\n for line "
            "breaks.\n"
        )
    keys_word = "three keys" if secondary_language else "two keys"
    return (
        "Read the following article and respond with ONLY a single JSON object "
        "(no markdown code fences, no commentary before or after) with exactly "
        f"these {keys_word}:\n"
        f'- "summary": a 2-4 sentence summary in {language}, plus a couple of '
        "key-point bullets if useful, as one string using \\n for line breaks.\n"
        f"{secondary_key}"
        '- "qa": a list of exactly 3 objects, each with "question" and "answer" '
        f"keys, both written in {language}. Each question should be something a "
        "curious reader would naturally wonder after reading the summary "
        "(background, implications, related context), and each answer should be "
        "1-3 sentences.\n\n"
        f"Title: {title}\n\nArticle:\n{text}"
    )


def _build_quiz_prompt(articles: list, language: str, num_questions: int) -> str:
    blocks = []
    for i, a in enumerate(articles, 1):
        blocks.append(f"{i}. {a['title']}\n{a['summary']}")
    joined = "\n\n".join(blocks)
    return (
        "Below are summaries of news articles a reader saw recently. Write a short "
        f"recall quiz of {num_questions} questions (or fewer if there isn't enough "
        f"material) in {language} that checks whether the reader remembers the key "
        "facts. Respond with ONLY a single JSON object (no markdown code fences, no "
        'commentary) with one key "quiz": a list of objects, each with "question" '
        f'and "answer" keys, both written in {language}. Each question should test '
        "one concrete fact or takeaway, and each answer should be 1-2 self-contained "
        f"sentences.\n\nArticles:\n{joined}"
    )


def _build_brief_prompt(articles: list, language: str) -> str:
    blocks = []
    for i, a in enumerate(articles, 1):
        blocks.append(f"{i}. [{a['source']}] {a['title']}\n{a['summary']}")
    joined = "\n\n".join(blocks)
    return (
        "You are the editor of a daily news digest. Below are today's article "
        f"summaries. Write a single editor's brief of 2-4 sentences in {language} "
        "that gives the reader the big picture — the main threads of the day and, "
        "where it's natural, how stories connect — rather than just listing them. "
        "Respond with ONLY a single JSON object (no markdown code fences, no "
        'commentary) with one key "brief" whose value is that paragraph as a plain '
        f"string.\n\nArticles:\n{joined}"
    )


def _build_deep_read_prompt(title: str, text: str, language: str) -> str:
    text = text[:MAX_SOURCE_CHARS]
    return (
        "Read the following article and write an in-depth 'deep read' companion for a "
        f"curious reader who wants more than a quick summary, written in {language}. "
        "Respond with ONLY a single JSON object (no markdown code fences, no "
        "commentary) with these keys:\n"
        f'- "background": 2-4 sentences of context/background in {language}, as one '
        "string.\n"
        f'- "points": a list of 3-5 key takeaways, each a short sentence in {language}.\n'
        f'- "implications": 2-3 sentences in {language} on why it matters or what may '
        "follow, as one string.\n"
        f'- "glossary": a list of 2-4 objects with "term" and "definition" keys — '
        f"terms, people, or concepts from the article worth knowing — both in {language}."
        f"\n\nTitle: {title}\n\nArticle:\n{text}"
    )


def _loads_lenient(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(text[start : end + 1])


def _parse_response(raw: str) -> dict:
    data = _loads_lenient(raw)
    summary = str(data["summary"]).strip()
    summary_secondary = str(data.get("summary_secondary", "")).strip()
    qa = [
        {"question": str(item["question"]).strip(), "answer": str(item["answer"]).strip()}
        for item in data.get("qa", [])[:3]
    ]
    return {"summary": summary, "summary_secondary": summary_secondary, "qa": qa}


def _complete(prompt: str, conf: dict, max_tokens: int) -> str:
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
        return resp.text

    if provider == "openai":
        client = _get_openai_client(conf.get("openai_base_url"))
        resp = _call_with_retry(
            lambda: client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return resp.choices[0].message.content

    raise ValueError(f"Unknown provider: {provider!r} (expected 'gemini' or 'openai')")


def summarize_article(title: str, text: str, conf: dict) -> dict:
    prompt = _build_prompt(title, text, conf["language"], conf.get("secondary_language"))
    return _parse_response(_complete(prompt, conf, max_tokens=800))


def generate_quiz(articles: list, conf: dict, num_questions: int) -> list:
    prompt = _build_quiz_prompt(articles, conf["language"], num_questions)
    data = _loads_lenient(_complete(prompt, conf, max_tokens=700))
    items = []
    for item in data.get("quiz", [])[:num_questions]:
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question and answer:
            items.append({"question": question, "answer": answer})
    return items


def generate_brief(articles: list, conf: dict) -> str:
    prompt = _build_brief_prompt(articles, conf["language"])
    data = _loads_lenient(_complete(prompt, conf, max_tokens=400))
    return str(data.get("brief", "")).strip()


def generate_deep_read(article: dict, conf: dict) -> dict:
    prompt = _build_deep_read_prompt(article["title"], article.get("full_text", ""), conf["language"])
    data = _loads_lenient(_complete(prompt, conf, max_tokens=1000))
    points = [str(p).strip() for p in data.get("points", []) if str(p).strip()]
    glossary = [
        {"term": str(g.get("term", "")).strip(), "definition": str(g.get("definition", "")).strip()}
        for g in data.get("glossary", [])
        if str(g.get("term", "")).strip() and str(g.get("definition", "")).strip()
    ]
    return {
        "background": str(data.get("background", "")).strip(),
        "points": points,
        "implications": str(data.get("implications", "")).strip(),
        "glossary": glossary,
    }
