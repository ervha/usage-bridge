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

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

OpenTokenUsage と Tailscale の導入、トークン生成、tailnet アドレスへの待ち受け設定、自動起動の登録、ヘルスチェックまで一括で行います。表示されるトークンは金庫など安全な場所に保管し、リポジトリには絶対に入れないでください。

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
