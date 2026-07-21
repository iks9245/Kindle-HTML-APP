import anthropic

MAX_SOURCE_CHARS = 6000

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def summarize_article(title: str, text: str, language: str, model: str) -> str:
    text = text[:MAX_SOURCE_CHARS]
    prompt = (
        f"Summarize the following article for a daily e-reader digest. "
        f"Write the summary in {language}, as 2-4 short sentences plus, if useful, "
        f"a couple of key-point bullets. No preamble, no markdown headings, "
        f"just the summary text.\n\n"
        f"Title: {title}\n\nArticle:\n{text}"
    )
    resp = _get_client().messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
