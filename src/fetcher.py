import feedparser
from datetime import datetime, timezone


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_feed(source: dict, last_seen: datetime | None) -> tuple[list[dict], datetime | None]:
    """
    RSSフィードを取得し、last_seen より新しい記事を返す。
    初回実行（last_seen=None）は空リストと最新記事日時を返す。

    Returns: (new_articles, newest_date)
    """
    feed = feedparser.parse(source["url"])

    if feed.bozo and not feed.entries:
        print(f"    警告: フィード取得失敗 [{source['name']}] {feed.bozo_exception}")
        return [], last_seen

    newest_date = last_seen
    articles = []

    for entry in feed.entries:
        published = _parse_date(entry)
        if published is None:
            continue

        if newest_date is None or published > newest_date:
            newest_date = published

        if last_seen is None or published <= last_seen:
            continue

        articles.append({
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "source": source["name"],
            "published": published.isoformat(),
        })

    return articles, newest_date
