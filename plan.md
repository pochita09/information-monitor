# Phase 1（復旧）修正計画

作成日: 2026-08-29
目的: **改造前の元の仕様のまま**、Actionsで1回実行してPagesが更新される状態に戻す。
前提: Phase 0 の診断で原因A（スケジュール窓）・原因B（Geminiモデル404）・原因C（Cloudflare 1010）を特定済み。

---

## 0. 計画立案中に判明した追加事項

指示された方針をそのまま実行できない箇所が1つある。

**Workerの `validateConfig` が二重定義されている**（`worker/src/index.js` 7行目と13行目）。
13行目の再代入が有効で、緩い検証しか行われていない。実測:

```
1. 標準ソース1本のみ -> errors: なし(通過)
2. 任意トピックzzzz  -> errors: なし(通過)
```

- これがKVに `genre` / `zzzz` が入り `ai-models` が1ソースに削られた**発生源**。KVを掃除しても設定画面から再発する。
- さらに両方の版とも `run.times` を必須にしているため、**設定画面から実行時刻の項目を消すと保存が400になる**。

→ 方針「動かない設定を残さない」を満たすには Worker の修正と再デプロイが避けられない。
→ 本計画では **13行目の重複定義を削除して7行目版に一本化**し、あわせて `run.times` 必須を解除する。

### 本計画で対象外とするもの（理由付き）

- 7行目版でもトピックIDは `[a-z0-9-]{1,40}` なら何でも通る（`zzzz` 自体は防げない）。
  → 変更4により Python 側が未知トピックを無視するため実害なし。Phase 2 の新Workerで整理する。
- `spec.md` / `README.md` の記述更新。Phase 1 の完了条件に含まれないため Phase 2 で行う。

---

## 1. 変更対象と内容

### 原因A（スケジュール）

| # | ファイル | 変更内容 |
|---|---|---|
| A1 | `.github/workflows/monitor.yml` | cron を `*/5 * * * *` → `0 4,12,22 * * *` に変更（JST 13:00 / 21:00 / 翌07:00）。`MONITOR_SCHEDULED` env を削除 |
| A2 | `src/main.py` | `schedule` の import と `MONITOR_SCHEDULED` ゲート（34-39行）、`complete_slot`（140-141行）を削除。**起動したら必ず処理する** |
| A3 | `src/schedule.py` | ファイル削除（12分窓判定の撤廃） |
| A4 | `config.yaml` | `run.times` を削除 |
| A5 | `templates/monitor.html` | 「取得する時刻」UI（`runTimes` / `runTimeInput` / `addTimeBtn`）と `renderTimes()` / 追加・削除ハンドラを削除 |
| A6 | `worker/src/index.js` | `validateConfig` から `run.times` 必須チェックを削除。`DEFAULT_CONFIG.run` からも `times` を削除 |

JST→UTC 変換の根拠: JST 07:00 = UTC 22:00(前日) / 13:00 = UTC 04:00 / 21:00 = UTC 12:00。

### 原因C（Cloudflare 1010）と KV — **順番を守る**

| # | 対象 | 変更内容 |
|---|---|---|
| C1 | Cloudflare KV | `config:global` キーを削除（`genre` / `zzzz` / 汚染された `ai-models` を一括で消す）。`npx wrangler kv key delete` を使用 |
| C2 | `worker/src/index.js` | 13行目の `validateConfig` 再代入を削除し7行目版に一本化。**C1 の後に実施**し、再デプロイ |
| C3 | `src/runtime_config.py` | `fetch_settings` の `Request` に通常の User-Agent を付与（403 の直接原因） |
| C4 | `src/runtime_config.py` | `theme["sources"] = restored` の丸ごと置換を廃止。**config.yaml をソース一覧の正**とし、KV は `enabled` のみ反映。KVに無いソースはON、config.yamlに無いソースは無視 |
| C5 | `src/runtime_config.py` | `settings_payload` / `apply_settings` から `run.times` の受け渡しを削除（A4/A6と整合） |

**実施順序: C1 → C2 → C3以降。** C3を先に入れると、汚染されたKVが読み込まれてソースが1本に落ちるため。

### 原因B（Geminiモデル）

| # | ファイル | 変更内容 |
|---|---|---|
| B1 | `config.yaml` | `ai.model` を `gemini-2.5-flash-lite` → `gemini-3.5-flash-lite` に変更 |
| B2 | 手作業（ユーザー） | ローカル `.env` と GitHub Secret の `GEMINI_API_KEY` を同一の値に統一。手順は別途提示する |

B1の根拠は Actions のエラーメッセージが指定した移行先。
**ローカルキーでの確認は根拠にしない**（キー差が原因のため）。検証は Actions 手動実行で行う。

---

## 2. テスト（実装前に用意する）

| # | ファイル | 内容 |
|---|---|---|
| T1 | `tests/test_schedule.py` | 削除（対象コードが無くなるため） |
| T2 | `tests/test_workflow.py` | `cron: "0 4,12,22 * * *"` を含むこと、`MONITOR_SCHEDULED` を**含まない**ことを検証 |
| T3 | `tests/test_runtime_config.py`（新規） | ①KVにソースが1本しか無くても config.yaml の4本が残る ②KVの `enabled:false` が反映される ③config.yaml に無いソースがKVにあっても無視される ④`run.times` を送られても無視される |
| T4 | `worker/test/worker.test.js` | `run.times` 無しで検証を通ること、標準ソース欠損を**拒否**すること |

`tests/test_phase1.py` は既存のまま回帰確認に使う。

---

## 3. 検証手順（指示書 Phase 1 の順序）

各段階で実行ログを残す。**1が通らないうちに2へ進まない。**

1. **ユニットテスト** — `python -m unittest discover tests` / `cd worker && npm test`
2. **ソース1本のみ有効** — config.yaml で3本を `enabled: false` にし `python src/main.py`
3. **全ソース有効** — `enabled` を戻して `python src/main.py`
4. **Actions 手動実行** — commit & push 後 `gh workflow run` → ログで Gemini 成功を確認
5. **Pages 反映** — 公開URLの表示データ日付が当日になることを確認

### 検証上の制約（明記しておく）

ローカルの `data/` は既に 08-28 まで進んでいるため、手順2・3では**新着0件になる可能性が高い**。
その場合ローカルで確認できるのは「設定取得200 → ソース取得 → HTML生成」までで、
**Gemini採点の実証は手順4（Actions）でのみ可能**。これは原因Bがキー依存であることとも整合する。
新着0件だった場合はその旨をログとともに報告する。

---

## 4. リスクと未確定事項

- **Worker 再デプロイ**は公開中サービスへの変更。実行前に差分を提示して確認を取る。
- 原因Bは**キー統一（B2）が済むまで解消しない可能性がある**。B1だけで直るかは Actions 実行まで不明。
- `data/` `public/` に未コミットの変更あり（Phase 0 のローカル実行分）。手順4の push に含める。
- `spec.md` に作業前からの未コミット変更あり。今回は触らない。

---

## 5. 停止ポイント

指示通り、**Actions 手動実行が成功して Pages が更新された時点で停止**して報告する。
途中で計画から外れる必要が出た場合も、その時点で停止して判断を求める。
