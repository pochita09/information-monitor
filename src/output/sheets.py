import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADERS = ["取得日時", "タイトル", "要約", "カテゴリ", "重要度", "情報源"]
INITIAL_ROWS = 10000


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def _get_or_create_sheet(spreadsheet: gspread.Spreadsheet, tab_name: str) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=INITIAL_ROWS, cols=len(HEADERS))
        ws.append_row(HEADERS)
        return ws


def _safe_text(value: str) -> str:
    """先頭が数式開始文字（= + - @）の場合にシングルクォートを付け、数式インジェクションを防ぐ。"""
    v = str(value)
    if v.startswith(("=", "+", "-", "@")):
        return "'" + v
    return v


def append_articles(sheet_tab: str, articles: list[dict]) -> None:
    """記事をスプレッドシートの先頭（ヘッダーの次）に追記する。"""
    if not articles:
        return

    client = _get_client()
    spreadsheet = client.open_by_key(os.environ["SPREADSHEET_ID"])
    worksheet = _get_or_create_sheet(spreadsheet, sheet_tab)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = []
    for a in articles:
        # URL のダブルクォートを %22 にエンコードして HYPERLINK 数式の構文破壊を防ぐ
        url = a.get("url", "").replace('"', "%22").replace("\n", "").replace("\r", "")
        title_safe = a.get("title", "").replace('"', "'").replace("\n", "").replace("\r", "")
        title_cell = f'=HYPERLINK("{url}","{title_safe}")'
        rows.append([
            now,
            title_cell,
            _safe_text(a.get("summary_ja", "")),
            _safe_text(a.get("category", "")),
            _safe_text(a.get("importance", "")),
            _safe_text(a.get("source", "")),
        ])

    worksheet.insert_rows(rows, row=2, value_input_option="USER_ENTERED")
