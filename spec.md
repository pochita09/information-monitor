# Information-gathering-agent 仕様書

## 概要

AIベンダーの発信（新モデル・新機能・価格改定・研究/論文）をRSSで自動収集し、
AIで選別・要約して、メール通知とスプレッドシート記録の2系統に出力する。
VPS上で1日2〜3回、自動実行する。

## 処理フロー

1. 設定ファイルの各テーマの情報源（RSS）を取得
2. 取得済み記事との差分をとり、新着のみ抽出
3. 新着のタイトル＋概要をAIに渡し、テーマごとの選別ルールで判定
   - 重要でないものは除外
   - 残りにカテゴリ・重要度を付与し、1〜2行に要約
4. 出力（2系統）
   - メール: 1回の実行分をまとめて1通、HTML構造化して送信
   - スプレッドシート: 1行ずつ追記
5. 1日2〜3回、スケジューラ（cron等）で自動実行

## 設計方針（拡張性）

「情報源・選別ルール・使用モデル・テーマ」をすべて設定ファイルに外出しし、
コード本体を変更せず設定編集だけで調整・拡張できる構造にする。

1テーマ = 「情報源リスト + 選別ルール + 出力先」のセット。
新テーマ追加は設定にブロックを足すだけで、コード変更不要。

## 情報源（初期テーマ：AIモデル系）

| 提供元 | フィードURL |
| --- | --- |
| OpenAI News | https://openai.com/news/rss.xml |
| OpenAI Engineering | https://openai.com/news/engineering/rss.xml |
| Google DeepMind Blog | https://deepmind.google/blog/rss.xml |
| Anthropic News | https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml |
| Anthropic Research | https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml |

- 各URLは初回テスト時に取得可否を検証すること。
- テーマは後から追加可能な構造にする（例: 論文系=arXiv、コーディング系=各種ブログ）。

## 選別・要約AI

- 使用モデルは設定ファイルで指定し、切替可能にする（プロバイダ名・モデル名・APIキー参照）。
- 初期設定: Gemini Flash-Lite。
- AIに渡すのはタイトル＋概要のみ（記事全文は渡さない）。
- 選別ルール（プロンプト/キーワード）は設定ファイルに置き、編集だけで調整可能にする。
- テーマごとに判定軸を分ける:
  - プロダクト系（新モデル・新機能・価格改定）: 注目度の高さで判定
  - 研究系（論文・新事実）: 新規の研究成果かで判定

## 出力1: メール

- 送信先は自分のGmail。1回の実行分をまとめて1通。
- 本文はHTMLで構造化し、カテゴリ別に見出しで区切る。
- 本文テンプレートはコードと分離したファイルで持ち、変更可能にする。
- 件名例: `【AI情報】5/30 朝 新着5件（重要度・高2件）`
- 本文構成例（変更可）:
  ```
  ━━━ AIモデル系 ━━━
  ■ <タイトル（元記事リンク）>
    重要度: 高
    要約: 〜〜〜
  ```
- タイトルは元記事へのリンクにする。
- 件名に識別子を付け、受信側のGmailフィルタで専用ラベルへ振り分ける前提。

## 出力2: スプレッドシート

- テーマごとにシート（タブ）を分ける。
- 新しい行は上に追加する。
- 列構成:

| 列 | 内容 |
| --- | --- |
| 取得日時 | 書き出した日時 |
| タイトル | HYPERLINK関数で元記事リンクを埋め込む（クリックで元記事へ） |
| 要約 | 1〜2行 |
| カテゴリ | AIモデル系／論文系 など |
| 重要度 | 高／中／低 |
| 情報源 | OpenAI公式 など |

## インフラ

- 実行環境: Hetzner Cloud CPX11（2vCPU/2GB/40GB）。
- スケジュール: 1日2〜3回（cron等）。
- 状態管理: 取得済み記事の識別子（URL等）を保存し、新着判定に使う。

## 設定ファイルに持つ項目（環境変数 .env）

実際の値は各自が記入。.env はGit管理対象外にすること（.gitignoreに追加）。

```
# Gemini API
GEMINI_API_KEY=
AI_PROVIDER=gemini
AI_MODEL=gemini-flash-lite

# Google スプレッドシート
GOOGLE_APPLICATION_CREDENTIALS=./service_account.json
SPREADSHEET_ID=

# メール送信（Gmail）
MAIL_FROM=
MAIL_TO=
MAIL_APP_PASSWORD=
```

- サービスアカウントのJSONはファイルとして配置し、パスを GOOGLE_APPLICATION_CREDENTIALS に記載。
- Gmail送信にはアプリパスワード（2段階認証下で発行する専用パスワード）を使用する。

## 別管理にする設定（コード外）

- 情報源リスト（テーマごと）
- 選別ルール（テーマごとのプロンプト/キーワード）
- 使用AIモデル
- メール本文テンプレート

これらは .env とは別の設定ファイル（例: config.yaml 等、実装者判断）で管理し、
コードを変更せず編集できるようにする。

---

## 実装記録

### ファイル構成

```
OSINT-agent/
├── .env.example                  # 環境変数テンプレート
├── .gitignore                    # .env / service_account.json / data/ を除外
├── config.yaml                   # テーマ・RSS・選別ルール・AIモデル
├── requirements.txt              # 依存ライブラリ
├── templates/
│   └── email.html                # Jinja2 メール本文テンプレート
├── src/
│   ├── main.py                   # エントリーポイント・全体フロー
│   ├── fetcher.py                # RSS取得・新着抽出
│   ├── state.py                  # last_seen.json の読み書き
│   ├── ai_filter.py              # Gemini API で選別・要約
│   └── output/
│       ├── mailer.py             # Gmail SMTP 送信
│       └── sheets.py             # Google Sheets 追記
└── data/
    └── last_seen.json            # 実行時に自動生成（Git管理外）
```

### 依存ライブラリ

| ライブラリ | 用途 |
| --- | --- |
| feedparser | RSS/Atom パース |
| google-generativeai | Gemini API |
| gspread + google-auth | Google Sheets 操作 |
| jinja2 | メールテンプレート |
| pyyaml | config.yaml 読み込み |
| python-dotenv | .env 読み込み |

### 状態管理の設計

取得済み記事を全件保存する方式ではなく、**フィードURLごとの最終処理日時のみ**を保存する。

```json
{
  "https://openai.com/news/rss.xml": "2026-05-31T06:00:00+00:00",
  "https://deepmind.google/blog/rss.xml": "2026-05-30T18:00:00+00:00"
}
```

- ファイルサイズはフィード数分（現在5行）のまま増えない
- 初回実行時は全既存記事を既読扱いにしてスキップし、2回目以降から通知開始
- 日付を持たないフィードは `datetime.now()` でウォーターマークを初期化し、無限スキップを防ぐ

### AIへの記事送信上限

1回の実行で1テーマあたり最大 **100件** を Gemini に送信する（`MAX_ARTICLES_PER_CALL = 100`）。
100件を超える場合は先頭100件を処理し、残りは次回実行で処理する。
ウォーターマークは **実際に処理した記事の最大日時** から計算する（全件の最大日時ではない）。

### 実行フロー詳細

```
1. config.yaml・.env を読み込む
2. テーマごとにループ:
   a. 各フィードを fetch_feed() で取得（新着のみ抽出）
   b. 100件超なら先頭100件に切り捨て
   c. 切り捨て後の記事からウォーターマークを計算（pending_state に保留）
   d. filter_and_summarize() で Gemini API に選別・要約を依頼
      ※ 失敗時はそのテーマをスキップして継続
3. スプレッドシートに追記（テーマごとに try/except）
4. メール送信（try/except）
5. 両方成功時のみ pending_state を last_seen.json に保存
   ※ 片方でも失敗した場合は保存せず次回再試行
```

### セキュリティ・堅牢性の設計決定

#### セキュリティ

- **Jinja2 autoescape=True**: RSS由来のタイトル・要約をHTMLメールに展開する際、`<script>` 等を自動エスケープ
- **HYPERLINK数式インジェクション対策**:
  - URLの `"` を `%22` にエンコード（数式構文破壊を防止）
  - URLとタイトルから `\n` `\r` を除去（複数行数式を防止）
  - summary / category / importance / source は `_safe_text()` で先頭の `=+-@` を `'` でエスケープ
- **秘密情報**: APIキー・パスワードはすべて `.env` で管理、コードにハードコードしない

#### 堅牢性

- **アトミックなファイル書き込み**: `last_seen.json` への書き込みは一時ファイル経由で `os.replace()` でリネーム。書き込み途中のクラッシュでファイルが壊れない
- **破損ファイルの回復**: `_load()` が `JSONDecodeError` をキャッチし、初回実行として扱って続行
- **状態更新のタイミング**: 配信（メール・シート両方）が成功してから `last_seen.json` を更新。失敗時は次回再試行
- **バッチ更新**: `update_many()` で複数フィードの状態を1回の読み書きで更新（冗長I/O削減）
- **シート行上限**: 新規ワークシートは `rows=10000` で作成（旧: 1000）

### 起動方法

```bash
# 依存インストール
pip install -r requirements.txt

# .env を作成して値を記入
cp .env.example .env

# 初回実行（既存記事をスキップして last_seen.json を初期化）
python src/main.py

# cron 設定例（1日3回）
0 7,12,21 * * * cd /path/to/OSINT-agent && python src/main.py >> logs/run.log 2>&1
```
