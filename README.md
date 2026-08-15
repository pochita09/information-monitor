# Information Monitor

RSS / Atom の新着記事を Gemini で採点・要約し、静的な Monitor 画面を GitHub Pages へ公開する個人用ツールです。

## できること（Phase 3）

- RSS / Atom の取得、新着判定、安定した記事IDによる重複防止
- Gemini による 1〜10 の採点、日本語要約、タグ生成
- `data/articles.json` と `data/last_seen.json` のアトミック保存
- 閾値以上と未満を分けた Monitor HTML の生成
- GitHub Actions による定期実行、状態のcommit、GitHub Pages公開
- Cloudflare Worker / KV による「良い」「違う」と除外理由の保存・復元

設定保存、評価のGemini採点への反映、Telegramはまだ実装していません。

## 評価API（Phase 3）

Workerは `feedback:{item_id}` に記事ごとの最新評価を保存し、`feedback:index` に最大500件のIDを持ちます。同じ記事を再評価すると、履歴を増やさず最新評価で上書きします。

| Endpoint | 用途 |
| --- | --- |
| `POST /feedback` | 良い／違う（理由付き）を保存・更新 |
| `GET /feedback` | 保存済み評価を一覧取得し、ページ読み込み時に復元 |
| `GET /feedback/:item_id` | 特定記事の評価を取得 |

WorkerはGitHub Pages origin (`https://pochita09.github.io`) と限定したlocalhost開発originだけをCORS許可します。公開Pagesからの書込みを個人用に軽量に運用する設計であり、CORSはユーザー認証ではありません。より強い書込み保護が必要になった場合は、将来のPhaseでCloudflare AccessまたはTurnstileを導入してください。

## ローカル実行

Python 3.12 を推奨します。Geminiキーはコードへ書かず、`GEMINI_API_KEY` 環境変数で渡します。

```powershell
cd C:\Users\nyaaa\Desktop\monitor-agent\OSINT-agent
python -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "Gemini API key"
python src\main.py
```

生成結果は `public/index.html`、状態は `data/last_seen.json` と `data/articles.json` に保存されます。初回に `last_seen.json` が存在しないソースは、過去記事を大量に採点しないため最新日時を初期化して次回から新着を取得します。

### item_id

記事IDは、追跡パラメータとフラグメントを除いたURL、空白・大文字小文字を正規化したタイトル、UTC公開日時の SHA-256 です。これにより同じ記事を次回Geminiへ再送しません。

## GitHubで必要な手作業

以下はコードから自動化できません。

1. このリポジトリをGitHubへpushします。
2. GitHubの **Settings → Secrets and variables → Actions → New repository secret** を開き、名前を `GEMINI_API_KEY` としてGemini APIキーを登録します。
3. **Actions** タブでworkflowの実行を許可します。
4. **Settings → Pages → Build and deployment → Source** を **GitHub Actions** に変更します。
5. **Actions → Update Monitor → Run workflow** から初回手動実行します。
6. 実行後、deploy jobの `page_url`、または **Settings → Pages** に表示されるURLを開きます。

Actionsログは **Actions → Update Monitor → 対象の実行 → build / deploy** から確認できます。ログには取得ソース、Gemini対象件数、保存件数、HTML生成、状態commitの有無が表示されます。APIキーの値は出力しません。

## 定期実行

GitHub ActionsのcronはUTC指定です。以下の日本時間（JST）で実行します。

| JST | UTC cron |
| --- | --- |
| 07:13 | `13 22 * * *`（前日UTC） |
| 13:17 | `17 4 * * *` |
| 21:23 | `23 12 * * *` |

GitHub Actionsのscheduleは厳密な時刻実行ではなく、GitHubの混雑により数分以上遅延することがあります。

## 状態と公開

workflowは同時実行を1本に制限します。Monitor生成が成功した後にだけ、変更された `data/last_seen.json`、`data/articles.json`、`public/` をcommitします。変更がなければ空commitは作りません。

Pages公開はこのworkflow内でartifactを直接deployします。Actionsが作ったcommitをトリガーには使用しないため、commitによる無限再実行は発生しません。GeminiやRSS処理に失敗した場合は、そのソースの既読状態を進めず、次回実行で再試行します。
