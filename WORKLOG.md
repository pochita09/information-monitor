# WORKLOG

## 2026-08-29 Phase 0（現状診断）

対象リポジトリ: `pochita09/information-monitor`（ローカルパス `monitor-agent/OSINT-agent/`）
方針: 修正は行わず、切り分けのみ。

### 事前バックアップ

```
mkdir -p data/backup_20260829 && cp data/last_seen.json data/articles.json data/backup_20260829/
```
→ 実行前の `articles.json`(177件) / `last_seen.json`(最終 2026-08-14) を保全済み。

### 実施した6項目と結果（実測）

1. ローカル実行 `python src/main.py` → **exit 0 で成功**。38件保存、HTML生成。
   ただし警告 `設定APIを取得できません: HTTP Error 403: Forbidden`。
2. 状態ファイル → 実行前 `articles.json` 177件、`processed_at` は 2026-08-15 の2種のみ。
   `last_seen.json` は 2026-08-14 で停止。実行後は215件・08-28 まで前進。
3. GitHub Actions 直近60回 → **全て success**。しかし全て
   `指定時刻ではないため、今回の定期実行はスキップします` で早期return。
   窓に入った唯一の回(run 32930005419)は **Gemini 404**（`gemini-2.5-flash-lite` is no longer available to new users）で失敗。
4. Pages → `https://pochita09.github.io/information-monitor/` は HTTP 200。
   表示データの最新は **08-15 04:58**（14日前で停止）。
5. Worker → `/feedback` と `/` は 403 `origin is not allowed`（Origin必須の仕様）。
   `/config` は curl では 200。しかし urllib では 403（Cloudflare error 1010）。
6. ソースURL 4本 → **全て HTTP 200・feedparser 正常解析**。ソース側の問題なし。

### 特定した原因（3件）

- **原因A: スケジュール窓と実行頻度の不整合**（最上位）
  `run.times` は JST 07:13/13:17/21:23 の各12分窓（1日36分=2.5%）。
  cron は `*/5` だがGitHubの抑制で実測 30分〜12時間間隔。窓にほぼ当たらない。
  → 直近60回中、窓に入ったのは1回のみ。
- **原因B: Actions側のGeminiキーで `gemini-2.5-flash-lite` が404**
  ローカルキーでは同モデル利用可（models.list で確認済み）。Secretは 2026-08-15 作成。
  → キーの世代差による "new users" 扱いと推測（Secret値は読めないため未確定）。
- **原因C: Cloudflare error 1010 が `Python-urllib` UA をブロック**
  UAを `curl/8.0.1` に変えると同一URLが 200。`fetch_settings` はUA未指定。

### 未解決 / 要判断

- 原因Bの「キーが別物である」ことは Secret 値を読めないため**未確定**。
- Worker KV の `/config` 内容が `ai-models` のソースを openai-news 1本のみに上書きする状態。
  原因Cを直すと有効ソースが4→1に減る副作用がある（要判断）。
- ローカル実行による `data/` `public/` の変更は**未コミット**のまま保持。
