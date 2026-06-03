import sys
from datetime import datetime, timezone
from pathlib import Path

# src/ をパスに追加して output.mailer 等のサブパッケージを import できるようにする
sys.path.insert(0, str(Path(__file__).parent))

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

from ai_filter import filter_and_summarize
from fetcher import fetch_feed
from output.mailer import send_email
from output.sheets import append_articles
from state import get_last_seen, update_last_seen, update_many

MAX_ARTICLES_PER_CALL = 100  # 1回の実行でAIに渡す記事数の上限


def load_config() -> dict:
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    config = load_config()
    model_name = config["ai"]["model"]

    theme_results = []
    # 配信後にまとめて保存する状態更新（fix #1: 状態更新を配信後に移動）
    pending_state: dict[str, datetime] = {}

    for theme in config["themes"]:
        print(f"\n[テーマ] {theme['name']}")
        all_new_articles = []

        for source in theme["sources"]:
            last_seen = get_last_seen(source["url"])
            is_first_run = last_seen is None

            articles, newest_date = fetch_feed(source, last_seen)

            if is_first_run:
                # 初回実行: ウォーターマークを即時保存（配信する記事がないため安全）
                # newest_date が None のフィード（日付なし）も now で初期化して無限スキップを防ぐ（fix #6）
                watermark = newest_date or datetime.now(timezone.utc)
                update_last_seen(source["url"], watermark)
                print(f"  [{source['name']}] 初回実行: 既存記事をスキップしました")
                continue

            print(f"  [{source['name']}] 新着: {len(articles)}件")
            for a in articles:
                a["_feed_url"] = source["url"]  # ウォーターマーク計算用（内部フィールド）
            all_new_articles.extend(articles)

        if not all_new_articles:
            print("  通知対象の新着記事なし")
            continue

        # 上限を超える場合は先頭 MAX_ARTICLES_PER_CALL 件に切り捨て
        if len(all_new_articles) > MAX_ARTICLES_PER_CALL:
            print(f"    警告: 記事数が上限を超えるため先頭 {MAX_ARTICLES_PER_CALL} 件に制限します（合計 {len(all_new_articles)} 件）")
            all_new_articles = all_new_articles[:MAX_ARTICLES_PER_CALL]

        # 切り捨て後の記事からウォーターマークを計算（処理範囲と記録を一致させる）
        for a in all_new_articles:
            feed_url = a.get("_feed_url", "")
            if not feed_url:
                continue
            pub = datetime.fromisoformat(a["published"])
            if feed_url not in pending_state or pub > pending_state[feed_url]:
                pending_state[feed_url] = pub

        print(f"  選別中... ({len(all_new_articles)}件 → Gemini {model_name})")
        try:
            filtered = filter_and_summarize(all_new_articles, theme, model_name)
        except Exception as e:
            print(f"  警告: AI選別失敗 [{theme['name']}]: {e} — このテーマをスキップします")
            continue
        print(f"  選別結果: {len(filtered)}件")

        if filtered:
            theme_results.append({
                "theme_name": theme["name"],
                "sheet_tab": theme["sheet_tab"],
                "articles": filtered,
            })

    if not theme_results:
        print("\n通知対象の記事がありませんでした。終了します。")
        return

    # スプレッドシート追記（失敗してもメール送信は継続する, fix #4）
    sheets_ok = True
    print("\nスプレッドシートに追記中...")
    for result in theme_results:
        try:
            append_articles(result["sheet_tab"], result["articles"])
            print(f"  [{result['theme_name']}] {len(result['articles'])}件 追記完了")
        except Exception as e:
            sheets_ok = False
            print(f"  警告: スプレッドシート追記失敗 [{result['theme_name']}]: {e}")

    # メール送信
    email_ok = True
    print("メール送信中...")
    try:
        send_email(theme_results)
    except Exception as e:
        email_ok = False
        print(f"  警告: メール送信失敗: {e}")

    # 両方の出力が成功したときのみ状態を保存（片方失敗は次回再試行）
    if sheets_ok and email_ok:
        update_many(pending_state)
    else:
        print("  警告: 出力が一部失敗したため状態を保存しません。次回実行時に再試行します。")

    total = sum(len(r["articles"]) for r in theme_results)
    print(f"\n完了: {total}件を処理しました。")


if __name__ == "__main__":
    main()
