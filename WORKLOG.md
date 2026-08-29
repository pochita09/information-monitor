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

## 2026-08-29 Phase 1（復旧）

方針: 原因A/B/Cを個別に修正し、指示された順序（ソース1本→全ソース→Actions手動実行→Pages確認）で検証。

### 実施内容

1. **KV掃除**: `config:global` をバックアップ後に削除（`genre`/`zzzz`/汚染された`ai-models`を一掃）。評価データ2件は保持。
2. **Worker修正**: `worker/src/index.js` の `validateConfig` 二重定義（緩い方が実効していた）を解消し1本化。`run.times` 必須チェックを削除。Worker再デプロイ実施（Version ID `5fc81a3c`）。
3. **原因C修正**: `runtime_config.fetch_settings` に User-Agent を付与（Cloudflare error 1010対策）。`apply_settings` を「config.yamlがソース一覧の正、KVはON/OFFのみ」方式に変更（`theme["sources"] = restored` の丸ごと置換を廃止）。
4. **原因A修正**: cron を `*/5 * * * *` → `0 4,12,22 * * *`（JST 13:00/21:00/翌07:00）に変更。`src/schedule.py` 削除、`main.py` の `MONITOR_SCHEDULED` ゲートを撤廃。設定画面の実行時刻UIを削除。
5. **原因B修正**: `config.yaml` の `ai.model` を `gemini-2.5-flash-lite` → `gemini-3.5-flash-lite` に変更。
6. テスト先行作成: `tests/test_runtime_config.py`（新規10件）、`tests/test_workflow.py` 更新、`worker/test/worker.test.js` 更新（標準ソース欠損の拒否を追加）。実装前に失敗することを確認済み。

### 検証結果（実測）

- ユニットテスト: Python 17/17 OK、Worker 10/10 pass。
- ローカル実行（手順2: ソース1本のみ→手順3: 全ソース）: 両方 exit 0、警告なし。新着0件（`data/`が既に08-28まで進んでいたため。想定内）。
- Actions手動実行 1回目（run `33256902399`）: 全ジョブ成功。「指定時刻ではないためスキップ」「設定APIを取得できません」いずれも**出ない**ことを確認。ただし新着0件のためGemini呼び出し自体が発生せず、原因Bは未検証のまま。
- **原因B検証のためのプローブ**: Anthropic Researchの直近2件を一時的に未処理へ戻し（`last_seen`を08-24へ、該当2件を`articles.json`から除去）、Actions再実行（run `33257644993`）。
  ```
  [Anthropic Research] 取得: 2件 / Gemini対象の新着: 2件
  Gemini採点中... (2件 → gemini-3.5-flash-lite)
  Gemini成功: 2件
  状態更新: 1ソース
  完了: 保存 2件
  ```
  404は発生せず。**原因B解消を実測で確認**。
- 状態更新コミット `92932a2` が実際に作られたことを確認（`git log origin/main`）。
- Pages (`https://pochita09.github.io/information-monitor/`) の表示データ最新が `08-29 14:27`（プローブ実行の処理時刻）に更新されたことを確認。再採点された記事の内容も反映済み。

### 事後処理

Actions本番実行（本番Secretキー、`gemini-3.5-flash-lite`）が生成した状態（215件、`last_seen`は自動的に08-28へ復帰）をそのまま正とし、追加の巻き戻しは行わなかった。理由: 書き戻すとPages更新の証拠を自ら消し、本番パイプラインの成果（新モデルでの再採点）を古い結果に戻すことになるため。プローブ前バックアップは `data/backup_20260829_post_actions/`（git未追跡）に保持。

### Phase 1完了条件との照合

指示された5項目を全てログ・実データで確認:
1. 「指定時刻ではないためスキップ」が出ない → ✅
2. Gemini採点が404にならず成功 → ✅（プローブで実証）
3. 「設定APIを取得できません」が出ない → ✅
4. 状態更新コミットが実際に作られる → ✅（`92932a2`）
5. Pages表示データが当日に更新 → ✅（`08-29 14:27`）

### 未解決 / 引き続き手作業が必要な事項

- **B2未実施**: ローカル `.env` と GitHub Secret の `GEMINI_API_KEY` は依然として別々の値。統一の手順は次の報告で提示する。
- `spec.md` は作業前からの未コミット変更が残ったまま（今回のスコープ外、触っていない）。
