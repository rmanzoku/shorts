#!/bin/bash
# setup.sh
# Oslo プロジェクトのセットアップスクリプト
# Python 仮想環境の作成・依存関係インストール・シークレットコピーを行う

set -e

echo "========================="
echo "Oslo - セットアップ"
echo "========================="
echo ""

HAS_ERROR=false

# Python バージョンチェック
echo "Python バージョンを確認中..."
PYTHON_VERSION=$(python3 --version 2>/dev/null || echo "not found")
if [ "$PYTHON_VERSION" = "not found" ]; then
    echo "エラー: Python3 がインストールされていません"
    HAS_ERROR=true
else
    echo "OK: $PYTHON_VERSION"
fi

# ffmpeg チェック
echo ""
echo "ffmpeg を確認中..."
FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -n 1 || echo "not found")
if [ "$FFMPEG_VERSION" = "not found" ]; then
    echo "エラー: ffmpeg がインストールされていません"
    echo "  インストール: brew install ffmpeg"
    HAS_ERROR=true
else
    echo "OK: $FFMPEG_VERSION"
fi

echo ""

if [ "$HAS_ERROR" = true ]; then
    echo "========================="
    echo "セットアップを中断しました"
    echo "========================="
    echo "上記のエラーを解決してから再実行してください"
    exit 1
fi

# シークレットファイルのコピー
echo "シークレットファイルを確認中..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/scripts/copy-secrets.sh" ]; then
    bash "$SCRIPT_DIR/scripts/copy-secrets.sh" || true
else
    echo "scripts/copy-secrets.sh が見つかりません（スキップ）"
fi

# Python 仮想環境のセットアップ
echo ""
echo "Python 仮想環境をセットアップ中..."
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv "$SCRIPT_DIR/.venv"
    echo "仮想環境を作成しました"
else
    echo "仮想環境は既に存在します"
fi

echo ""
echo "依存関係をインストール中..."
"$SCRIPT_DIR/.venv/bin/pip" install -e ".[dev]" --quiet

echo ""
echo "========================="
echo "セットアップ完了!"
echo "========================="
echo ""
echo "使い方:"
echo "  .venv/bin/oslo generate <input> -o <output.mp4> -v --keep-temp"
echo ""
