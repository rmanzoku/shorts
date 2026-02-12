# Oslo

テキストファイルからAIナレーション・AI画像・自動字幕付きのショート動画を生成するCLIツール。

## 特徴

- テキストファイルまたは Markdown コンテから縦型ショート動画（9:16, 1080x1920）を自動生成
- OpenAI TTS（gpt-4o-mini-tts）によるナレーション
- OpenAI 画像生成（gpt-image-1）による背景画像
- 音声タイミングに基づく自動字幕（CJK 対応・助詞ベース分割）
- Ken Burns（ズーム）効果とクロスフェードトランジション
- 半透明背景付き字幕で視認性確保
- API 呼び出し前の確認プロンプト（コスト管理）

## セットアップ

### 前提条件

- Python 3.11以上
- FFmpeg
- OpenAI APIキー

### インストール

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 環境変数

```bash
cp .env.example .env
# .env を編集して OPENAI_API_KEY を設定
```

## ディレクトリ構成

```
contes/           # コンテ（Markdown）— Git 管理
  001_topic.md
  002_topic.md
output/           # 生成物（MP4・中間ファイル）— Git 除外
src/oslo/         # ソースコード
tests/            # テスト
```

## 使い方

### テキストファイルから生成

```bash
# 基本的な使い方（API 呼び出し前に確認あり）
oslo generate input.txt

# 出力先とオプションを指定
oslo generate input.txt -o output.mp4 --voice coral --speed 1.1

# 詳細ログ・中間ファイル保持（再合成に便利）
oslo generate input.txt -v --keep-temp

# 確認スキップ（CI/自動化向け）
oslo generate input.txt --yes

# 最大60秒、高画質
oslo generate input.txt --max-duration 60 --image-quality high
```

### コンテ（Markdown）から生成

映像指示付きのコンテファイルから生成できます。

```bash
oslo generate contes/001_topic.md -o output/001_topic.mp4 -v --keep-temp
```

コンテフォーマット:

```markdown
# タイトル

## シーン 1
**映像**: 国会議事堂の外観、夕暮れ時の荘厳な雰囲気
**ナレーション**: 中道勢力の結集を掲げて...

## シーン 2
**映像**: 選挙の投票箱と開票作業のイメージ
**ナレーション**: 公明党の支持母体である創価学会は...
```

- `**映像**` で各シーンの画像生成指示を記述
- `**ナレーション**` でTTS読み上げ・字幕の元テキストを記述
- `**映像**` がない場合はナレーションから自動生成

### オプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `-o, --output` | 出力ファイルパス | `<入力名>.mp4` |
| `--voice` | TTS音声（alloy, coral, nova, etc.） | `nova` |
| `--speed` | TTS速度（0.25-4.0） | `1.0` |
| `--max-duration` | 最大動画長（秒） | `90` |
| `--image-quality` | 画像品質（low/medium/high） | `medium` |
| `--keep-temp` | 中間ファイルを保持 | `false` |
| `-v, --verbose` | 詳細ログ出力 | `false` |
| `-y, --yes` | 確認プロンプトをスキップ | `false` |

## 処理フロー

```
テキスト(.txt) or コンテ(.md)
  → テキスト解析・シーン分割 / コンテパース
  → [確認] API 呼び出し前にユーザー確認
  → OpenAI TTS でナレーション音声生成
  → OpenAI gpt-image-1 で背景画像生成
  → 音声タイミング + 文字数重み付きで字幕（SRT）生成
  → MoviePy で動画合成（Ken Burns + crossfade + 半透明背景字幕）
  → MP4出力（H.264 + AAC）
```

## 字幕の特徴

- 日本語テキストは助詞・接続語の位置で自然に分割（語の途中切れ防止）
- 半透明黒背景付きで視認性を確保
- 文字数に比例した表示時間配分（最低 1.0 秒保証）
- カタカナ長音（ー）や小書き文字の前では分割しない

## 開発

```bash
pip install -e ".[dev]"
pytest
ruff check src/ tests/
```
