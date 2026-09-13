"""UI strings for the generated pages.

`language` in config.yaml is free-form — it is fed to the model, so any language
works for the *content*. The page furniture (navigation, headings, the
presentation switcher) is a fixed set of strings that has to be translated here.

Only the language tags listed in STRINGS have a translation; anything else falls
back to English, on the grounds that English navigation around, say, Japanese
summaries is usable while Chinese navigation around them is not. Adding a
language means adding one entry below — no other file needs to change.

Values with {placeholders} are formatted by the caller, so keep the placeholder
names when translating.
"""

STRINGS = {
    "zh": {
        # page titles
        "digest_title": "每日 AI 文摘 {date}",
        "quiz_title": "昨日回顧小考",
        "weekly_title": "本週主題回顧",
        "deepread_title": "每日深讀",
        "archive_title": "文摘存檔",
        # navigation
        "home": "首頁",
        "back_home": "回到首頁",
        "archive": "存檔列表",
        "nav_deepread": "每日深讀",
        "nav_weekly": "本週主題",
        "nav_quiz": "昨日小考",
        "prev_day": "← 前一日",
        "original": "原文網頁",
        # digest page
        "editor_brief": "主編導讀",
        "no_articles": "今日沒有新文章。",
        "full_text": "全文",
        "full_text_minutes": "全文（約 {minutes} 分鐘）",
        # article page
        "prev_page": "← 上一頁",
        "next_page": "下一頁 →",
        "page_of": "第 {page} / {total} 頁",
        "read_minutes": "約 {minutes} 分鐘閱讀",
        "no_full_text": "沒有可離線閱讀的全文內容，請點上方「原文網頁」。",
        "follow_up": "延伸問答",
        # quiz page
        "quiz_from": "回顧 {date} 讀過的內容",
        "quiz_hint": "先想一下答案，再點開題目對照：",
        "quiz_empty": "還沒有可回顧的內容 — 明天再回來，看看你記得多少昨天讀過的東西。",
        # deep read page
        "deep_this": "本篇：",
        "deep_digest": "當天文摘",
        "deep_read_full": "讀全文",
        "deep_background": "脈絡",
        "deep_points": "重點",
        "deep_implications": "影響與延伸",
        "deep_glossary": "小辭典",
        "deep_empty": "今天還沒有深讀內容 — 排程跑過之後就會挑出當天最有份量的一篇，做成延伸導讀。",
        # weekly page
        "weekly_empty": "還沒有本週回顧 — 每週結算日跑過之後，就會把這一週的文章分主題整理成一篇。",
        # archive index
        "archive_empty": "目前還沒有存檔。",
        "archive_deep": "深讀",
        "archive_weekly_heading": "本週主題回顧",
        "archive_week_of": "{date} 那一週",
        # presentation switcher
        "sep": " ｜ ",
        "switch_font": "切換為{font}",
        "families": {"serif": "襯線", "sans": "無襯線"},
        "sizes": {"small": "小", "medium": "中", "large": "大"},
    },
    "en": {
        "digest_title": "Daily AI Digest {date}",
        "quiz_title": "Daily Recall Quiz",
        "weekly_title": "This Week in Themes",
        "deepread_title": "Deep Read of the Day",
        "archive_title": "Digest Archive",
        "home": "Home",
        "back_home": "Back to home",
        "archive": "Archive",
        "nav_deepread": "Deep read",
        "nav_weekly": "This week",
        "nav_quiz": "Recall quiz",
        "prev_day": "← Previous day",
        "original": "Original page",
        "editor_brief": "EDITOR'S BRIEF",
        "no_articles": "No new articles today.",
        "full_text": "Full text",
        "full_text_minutes": "Full text (~{minutes} min)",
        "prev_page": "← Previous",
        "next_page": "Next →",
        "page_of": "Page {page} of {total}",
        "read_minutes": "~{minutes} min read",
        "no_full_text": "No offline full text for this one — use “Original page” above.",
        "follow_up": "Going further",
        "quiz_from": "Recalling what you read on {date}",
        "quiz_hint": "Think of the answer first, then open each question:",
        "quiz_empty": "Nothing to recall yet — come back tomorrow and see how much of today stuck.",
        "deep_this": "On: ",
        "deep_digest": "That day's digest",
        "deep_read_full": "Read the full text",
        "deep_background": "Background",
        "deep_points": "Key points",
        "deep_implications": "Why it matters",
        "deep_glossary": "Glossary",
        "deep_empty": "No deep read yet — the next scheduled run picks the meatiest piece of the day and writes a companion for it.",
        "weekly_empty": "No weekly roundup yet — on the weekly wrap-up day the past week's articles get grouped into themes.",
        "archive_empty": "Nothing archived yet.",
        "archive_deep": "Deep read",
        "archive_weekly_heading": "Weekly roundups",
        "archive_week_of": "Week of {date}",
        "sep": " · ",
        "switch_font": "Switch to {font}",
        "families": {"serif": "serif", "sans": "sans-serif"},
        "sizes": {"small": "S", "medium": "M", "large": "L"},
    },
}

FALLBACK = "en"


def strings_for(language: str) -> dict:
    """UI strings for `language`, falling back to English for untranslated ones.

    Matching is on the part before any region subtag, so "zh-TW", "zh_CN" and
    "zh" all get the Chinese set.
    """
    tag = (language or "").strip().lower().replace("_", "-")
    base = tag.split("-")[0]
    return STRINGS.get(tag) or STRINGS.get(base) or STRINGS[FALLBACK]
