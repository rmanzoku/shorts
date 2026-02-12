# Video Generation Workflow

動画を生成または再合成する: $ARGUMENTS

## Step 1: 生成モード判定

以下を確認して新規生成か再合成かを判断する:

- **新規生成**: 入力テキストが変更された、または中間ファイルが存在しない場合
- **再合成**: 中間ファイル（音声 `.mp3`、画像 `.png`、字幕 `.srt`）が揃っている場合
  - 字幕スタイルや合成パラメータの変更のみなら API コール不要

再合成の場合、中間ファイルのパスを特定する:
- `--keep-temp` で生成した場合はログに出力されたパスを確認
- 一般的な場所: `/var/folders/.../oslo_*/`

## Step 2: 新規生成

入力は `.txt`（平文テキスト）と `.md`（コンテ）の2形式に対応。
`.md` またはコンテ形式のテキストは自動的にコンテパーサーで処理される。

```bash
# テキストファイルから（自動シーン分割）
oslo generate <input.txt> -o <output.mp4> -v --keep-temp

# コンテ（Markdown）から（映像指示付き）
oslo generate <conte.md> -o <output.mp4> -v --keep-temp
```

- API 呼び出し前に確認プロンプトが表示される
- `--keep-temp` を付けて中間ファイルを保持すること（再合成に必要）
- `-v` で進捗を表示

## Step 3: 再合成（API コスト不要）

中間ファイルから直接合成する:

```python
from pathlib import Path
from oslo.text_processor import split_into_scenes
from oslo.subtitles import generate_subtitles, write_srt
from oslo.composer import compose_video
from oslo.config import VideoConfig

tmp = Path("<中間ファイルディレクトリ>")
images = sorted(tmp.glob("scene_*.png"))
audios = sorted(tmp.glob("scene_*.mp3"))

# 字幕を再生成する場合
text = Path("<input.txt or conte.md>").read_text()
# コンテ形式の場合
from oslo.conte import is_conte_format, parse_conte
if is_conte_format(text):
    scenes = parse_conte(text)
else:
    scenes = split_into_scenes(text)
entries = generate_subtitles(scenes, list(audios))
srt_path = write_srt(entries, tmp / "subtitles.srt")

# 合成
compose_video(images, list(audios), srt_path, Path("<output.mp4>"), VideoConfig())
```

## Step 4: 出力確認

生成後に確認すること:
- ファイルサイズとフォーマット: `ls -lh <output.mp4>`
- 字幕が画面内に収まっているか
- 音声と映像の長さが一致しているか
- 語の途中で字幕が切れていないか
