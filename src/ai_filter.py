import json
import os
import re

import google.generativeai as genai

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _build_prompt(articles: list[dict], filter_criteria: str) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        summary = _strip_html(a.get("summary", ""))[:300]
        lines.append(
            f"[{i}]\n"
            f"タイトル: {a['title']}\n"
            f"URL: {a['url']}\n"
            f"概要: {summary}"
        )
    articles_text = "\n\n".join(lines)

    return f"""{filter_criteria}

【記事リスト】
{articles_text}

【出力形式】
JSON のみを返してください（説明文不要）:
{{
  "results": [
    {{"index": 1, "include": true, "category": "新モデル|新機能|価格改定|研究・論文|その他", "importance": "高|中|低", "summary": "1〜2行の日本語要約"}},
    {{"index": 2, "include": false}}
  ]
}}
include が false の場合、category / importance / summary は省略可。
"""


def filter_and_summarize(articles: list[dict], theme: dict, model_name: str) -> list[dict]:
    """Gemini API で記事を選別・要約して返す。"""
    if not articles:
        return []

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config={"response_mime_type": "application/json"},
    )

    prompt = _build_prompt(articles, theme["filter_prompt"])
    response = model.generate_content(prompt)

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as e:
        print(f"    警告: AI応答のJSONパース失敗: {e}")
        return []

    filtered = []
    for item in data.get("results", []):
        if not item.get("include", False):
            continue
        idx = item.get("index", 0) - 1
        if not (0 <= idx < len(articles)):
            continue
        original = articles[idx]
        filtered.append({
            **original,
            "category": item.get("category", "その他"),
            "importance": item.get("importance", "中"),
            "summary_ja": item.get("summary", ""),
        })

    return filtered
