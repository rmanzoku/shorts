# CLAUDE.md

テキストからショート動画を自動生成する CLI ツール「Oslo」の AI エージェント作業ルール。

## 基本原則

- OpenAI API はコストが発生する。実行前に必ずユーザーに確認する
- 中間ファイル（音声・画像・SRT）が残っていれば再合成で API コールを回避できる
- 日本語テキストの扱いに注意。CJK 検出・助詞ベース分割・文字数推定が必要

## プロジェクト構造

```
contes/               # コンテ（Markdown）— Git 管理、連番命名
  001_soka-gakkai.md
  002_next-topic.md
output/               # 生成物（MP4・中間ファイル）— Git 除外
src/oslo/
  cli.py            # Click CLI エントリポイント
  config.py         # AppConfig / VideoConfig / TTSConfig / ImageGenConfig
  conte.py          # コンテ（Markdown）パーサー
  text_processor.py # テキスト解析・シーン分割・字幕チャンキング・画像プロンプト
  tts.py            # OpenAI TTS クライアント
  image_gen.py      # OpenAI 画像生成クライアント
  subtitles.py      # SRT 字幕生成（CJK 対応・文字数重み付きタイミング）
  composer.py       # MoviePy 動画合成（Ken Burns・crossfade・字幕オーバーレイ）
  pipeline.py       # パイプラインオーケストレーター（コンテ/テキスト両対応）
  utils.py          # リトライデコレーター
```

### コンテ命名規則

`NNN_slug.md`（3桁ゼロ埋め + ハイフン区切りスラッグ）

## コスト意識

- `oslo generate` は API 呼び出し前に確認プロンプトを出す（`--yes` でスキップ）
- 1回の生成: TTS × シーン数 + 画像生成 × シーン数
- 字幕・合成の調整のみなら `--keep-temp` で中間ファイルを保持し、再合成スクリプトで対応

## 日本語テキスト処理の注意点

- `_is_cjk_dominant()`: テキストの 20% 以上が CJK 文字なら日本語扱い
- 字幕分割: 句読点で分割 → 助詞・接続語で自然な位置に再分割（`_find_jp_break`）
- 語の途中切れ防止: `_JP_BREAK_CHARS`（助詞・活用語尾）の後で切る
- カタカナ長音（ー）や小書き文字（ッ、ャ等）の前では切らない
- 短断片（3文字以下）は前のチャンクに統合（上限 22 文字）
- 文字数ベースの読み上げ速度推定: 日本語 350 CPM / 英語 150 WPM

## Codex CLI 利用ルール

コーディング（新規ファイル作成・既存ファイル修正）は `codex exec` に委譲する。MCP は使わない。

- コード実装: `codex exec "<実装指示>"` で生成し、結果をレビューしてからコミット
- レビュー・調査: Claude が直接行う
- テスト実行・lint: Claude が直接行う（`.venv/bin/pytest`, `.venv/bin/ruff`）

## ワークフロー全体像

| # | ステップ | 担当 | Skill |
|---|---------|------|-------|
| 1 | ネタ提供 | 人間 | - |
| 2 | Web調査 + コンテ作成 | AI | `/research` |
| 3 | コンテレビュー | 人間 | - |
| 4 | 動画生成 | AI | `/generate` |
| 5 | 品質レビュー | AI+人間 | `/improve` |
| 6 | アップロード | 人間 | - |

## コンテフォーマット（Markdown）

入力は `.txt`（平文テキスト）と `.md`（コンテ）の2形式に対応。

```markdown
# タイトル

## シーン 1
**映像**: 映像の説明（AI画像生成の指示になる）
**ナレーション**: TTS読み上げ・字幕の元テキスト

## シーン 2
**映像**: ...
**ナレーション**: ...
```

- `**映像**` がない場合はナレーションから自動生成（フォールバック）
- 映像指示にはスタイルプレフィックスと "Do not include any text" が自動付与される

### 台本ガイドライン

- です・ます調、読点2つ以内/文
- 合計90秒以内（約525文字）
- 偏向・扇動的表現の禁止

## 利用可能な Skill

- `/research` — Web調査 + コンテ作成ワークフロー
- `/generate` — 動画生成ワークフロー（コンテ/テキスト両対応、再合成判断含む）
- `/improve` — 生成済み動画のレビューと改善ワークフロー（ステップ5）
- `/precommit` — コミット前検証（テスト・lint・品質チェック）

## 開発コマンド

```bash
.venv/bin/pytest tests/ -v   # テスト実行
.venv/bin/ruff check src/    # lint
.venv/bin/ruff check tests/  # テストの lint
```
