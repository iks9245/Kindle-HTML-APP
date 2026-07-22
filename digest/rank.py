def score_article(article: dict, interests: list) -> int:
    if not interests:
        return 0
    haystack = f"{article['title']} {article['summary']}".lower()
    return sum(1 for keyword in interests if keyword.lower() in haystack)
