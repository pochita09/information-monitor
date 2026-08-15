# Information Monitor 引き継ぎメモ

更新日: 2026-08-15

## 現在の本番

- 公開URL: https://pochita09.github.io/information-monitor/
- GitHub: `pochita09/information-monitor`
- ブランチ: `main`
- 最新の状態更新コミット: `ccb05b5 chore: update monitor state`
- v3 UI移植コミット: `190469e fix: transplant v3 monitor mock structure`
- v3デプロイWorkflow: https://github.com/pochita09/information-monitor/actions/runs/31880515243 （成功）

## 実装済み機能

- RSS / Atom取得、既読・アーカイブ管理、Gemini採点・要約・タグ生成
- `data/articles.json` の記事アーカイブと安定した `item_id`
- GitHub Actionsによる定期実行とGitHub Pages公開
- Cloudflare Worker + KVによる「良い」「違う」「違う理由」の保存・復元
- コピー、topic切替、閾値未満の折りたたみ、設定画面への切替
- Geminiの新着処理時に `title_ja`（短い日本語見出し）を生成・保存する実装

## v3 UI

UIの正本はユーザーが指定した次のファイルです。

`C:\Users\nyaaa\Desktop\monitor-agent\mock\information-monitor-ui-mock-v3 (1).html`

GitHub Actionsでも同じCSSを利用できるよう、その正本のCSSをリポジトリへ同梱しています。

- `mock/information-monitor-ui-mock-v3.html`
- `src/renderer.py` の `MOCK_FILE` がこのファイルを参照
- `templates/monitor.html` はv3の以下の構造で実データを描画
  - `.shell`, `.topbar`, `.topics-wrap`, `.status`
  - `.feed`, `.card`, `.article`, `.scorebox`

表示仕様:

- PC: 記事本文の右に幅88pxの縦スコア
- モバイル（700px以下）: カード上部に横スコア
- タイトル: PC 22px / モバイル 19px
- 要約: 15.5px
- topic pillは横スクロール

## 日本語タイトルの注意

`src/ai_filter.py` はGemini応答の `title_ja` を保存します。テンプレートは以下の順で表示します。

1. `title_ja`
2. 英語原題 `title`
3. `summary_ja`

ただし既存の `data/articles.json` 177件には `title_ja` が存在しません。そのため、現時点の本番では原題のみをフォールバック表示します。新着記事がGemini処理されると日本語タイトルと原題の2段表示になります。

既存記事へのタイトル補完は未実施です。実施する場合は、RSSやスコアを変更せず、未設定の `title_ja` だけをGeminiで補完する一度限りのバックフィルとして設計・実行してください。

## 検証済み

- `python -m unittest discover -s tests -v`: 6件成功
- `node --test worker/test/worker.test.js`: 4件成功
- 生成済み `public/index.html` のJavaScript構文: 成功
- ローカル実レンダリング:
  - 390px: 上部横スコア、topic横スクロール、15.5px要約
  - 1000px: `1fr + 88px`、右側スコア、22pxタイトル
- 本番Pages:
  - feedback状態の復元成功
  - JavaScriptコンソールエラーなし

## 作業時の注意

- `spec.md` はユーザーの未コミット変更。勝手にstage/commitしない。
- `.claude/` は未追跡のローカルファイル。勝手にcommitしない。
- 定期Workflowが `data/` と `public/index.html` の状態コミットを作るため、push前にmainが進む場合がある。
  - 非fast-forward時は `git pull --rebase --autostash origin main`
  - `public/index.html` が競合した場合は、最新アーカイブから `render_monitor(...)` を再生成して解消する。
- Cloudflare Worker/KVやfeedback APIをUI変更だけで触らない。
- Phase 4以降（設定保存・学習反映）へは、ユーザーの明示指示なしに進まない。
