# usage-bridge（日本語）

**AIエージェントに「自分の残り枠」を見せてから、モデルを選ばせるための橋渡し。**

Claude Code / Codex / Antigravity / Grok などは、それぞれセッション・週次の上限とリセット時刻がバラバラです。ところが T3 Code のようなオーケストレータからは、その残量を MCP 経由で読めませんでした。人間が毎回ダッシュボードを確認してモデルを選ぶ、という手間が残っていたのです。

usage-bridge は、Windows トレイ常駐アプリ [OpenTokenUsage](https://www.poweruserz.dev/)（複数AIの枠を一括表示し、ローカルAPIを持つ）の出力を、小さな MCP サーバーとして中継します。経路は [Tailscale](https://tailscale.com/) の tailnet 内だけ。ポート開放はしません。

## 構成

```text
OpenTokenUsage（ローカルAPI 127.0.0.1:6736/v1/usage）
  → usage_bridge.py（Python標準ライブラリのみ、Bearer認証、5分キャッシュ）
  → Tailscale（私設網内のみ）
  → AIエージェントが残量を読んで、使うモデルを自動判断
```

## 導入（Windows）

### 0. 事前準備

- 先に Tailscale へサインインし、`tailscale ip -4` で tailnet IPv4（100.x…）を確認してください。サインイン前に導入すると `127.0.0.1` のみの待ち受けになるので、その場合はサインイン後に導入をやり直してください。
- PowerShell で `python --version`（または `py --version`）が通ることを確認してください。

### 1. ファイルの取得

最新リリースから `usage-bridge-v1.0.0.zip` をダウンロードして展開し、そのフォルダで PowerShell を開いてください。

### 2. インストーラの実行

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

OpenTokenUsage と Tailscale の導入、サーバーの配置（`%USERPROFILE%\usage-bridge`）、トークン生成、tailnet アドレスへの待ち受け設定、スタートアップフォルダへの自動起動登録（管理者権限不要、pythonw で窓なし起動）、ヘルスチェックまで一括で行います。再実行時は古いサーバープロセスを先に止めるので、古い版がポート8787を掴んだままになることはありません。表示されるトークンは金庫など安全な場所に保管し、リポジトリや公開の場には絶対に出さないでください。

### 3. プロバイダの有効化

OpenTokenUsage を一度開き、使うプロバイダ（Claude / Codex / Antigravity / Grok など）を有効化して、サインイン状態を確認してください。

### 4. 動作確認

```powershell
Invoke-RestMethod http://<tailnet IPv4>:8787/health
# → {"ok": true, "service": "usage-bridge"}

$token = Get-Content ~\usage-bridge\token.txt
Invoke-RestMethod http://<tailnet IPv4>:8787/usage -Headers @{ Authorization = "Bearer $token" }
```

エージェント側のマシンからも `/health` が返れば、経路まで完成です。`/usage` で 401 になる場合はトークンの不一致、タイムアウトする場合は PC のスリープ、サーバー未起動、tailnet の不一致を疑ってください。

## 更新

新しいリリースの zip を展開して `install.ps1` を再実行するだけです。`token.txt` は保持され、古いプロセスの停止と自動起動の再登録まで自動で行われます。保存される状態は他にないので、移行作業はありません。

## 削除（アンインストール）

1. サーバープロセスを止めます。

   ```powershell
   Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
     Where-Object { $_.CommandLine -like "*usage_bridge.py*" } |
     ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   ```

2. スタートアップフォルダ（エクスプローラのアドレスバーで `shell:startup`）から `usage-bridge.cmd` を削除します。
3. `%USERPROFILE%\usage-bridge` フォルダを削除します（`token.txt` も一緒に消えます）。
4. エージェント側の設定から、この MCP のエンドポイントを削除します。
5. 必要な場合のみ、OpenTokenUsage と Tailscale を Windows の設定や `winget uninstall` で削除してください。usage-bridge 自体はレジストリ等に何も残しません。

## トラブルシュート

- ヘルスチェックが失敗する → Python が PATH に無い、またはポート8787が使用中。再実行で古いプロセスは止まります。
- 「Tailscale IPv4 not found」と出る → Tailscale 未サインイン。サインイン後に再実行してください。
- エージェントから空の応答が返る → v1.0.0 で修正済み（pythonw 起動時の不具合）。古いコピーが動いていないか確認し、インストーラを再実行してください。
- 「OpenTokenUsage local API unreachable」と出る → OpenTokenUsage が起動していない、またはプロバイダが未有効化です。

## ツール

- `usage_all` — 有効な全プロバイダの使用量スナップショット
- `usage_provider` — 1プロバイダ分（例: `claude` / `codex` / `antigravity` / `grok`）

## 注意

- 8787番ポートをインターネットへ直接公開しないでください。
- トークン未設定だと認証が無効になります。その場合は `127.0.0.1` のみに bind してください。
- 読み取り専用です。書き込み系ツールはありません。
- PCがスリープ中は届きません。OpenTokenUsage のローカルAPI形式はアプリ更新で変わる可能性があります。

詳細は英語版 [README.md](README.md) と [SECURITY.md](SECURITY.md) を参照してください。

## 近いプロジェクトとの違い

残り枠を返す MCP は他にもあります（agent-runway、tokenhud、ai-usage-mcp、tokenmeter-tray など）。ただ、OpenTokenUsage を取得元にするもの、別マシンで動くエージェントが Tailscale 越しに読む前提のものは、調べた範囲では見つかりませんでした。違いは3点です。

1. 取得元 — 各社を自前で叩かず、OpenTokenUsage が集約済みの枠（Antigravity や Grok を含む）を使う
2. 構成 — サインインのある PC とエージェントが別マシンでもよい
3. 目的 — 人間が見るダッシュボードではなく、T3 のモデル選択に渡すこと

## ライセンス

MIT
