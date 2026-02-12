#!/bin/bash
# scripts/copy-secrets.sh
# Conductor ワークスペース間でシークレットファイルを同期するスクリプト
#
# メインリポジトリ (conductor/repos/shorts) が
# シークレットファイルの一元管理元として機能する。
# 各 Conductor ワークスペースは git worktree として作成されるが、
# .env 等の gitignore 対象ファイルは worktree に自動コピーされない。
# このスクリプトでメインリポ → ワークスペース間を同期する。
#
# === 管理対象ファイル ===
#
#   .env - 環境変数（OPENAI_API_KEY 等）
#
# Usage:
#   ./scripts/copy-secrets.sh           # メインリポ → ワークスペースにコピー
#   ./scripts/copy-secrets.sh --init    # ワークスペース → メインリポにエクスポート（初回）
#   ./scripts/copy-secrets.sh --force   # 既存ファイルも上書き

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- シークレットファイル一覧 ---
SECRET_FILES=(
  ".env"
)

# --- メインリポジトリのパスを自動検出 ---
detect_main_repo() {
  local git_file="$PROJECT_ROOT/.git"
  if [ -f "$git_file" ]; then
    local gitdir
    gitdir=$(grep '^gitdir: ' "$git_file" | cut -d' ' -f2-)
    if [ -n "$gitdir" ]; then
      if [[ "$gitdir" != /* ]]; then
        gitdir="$(cd "$(dirname "$git_file")/$gitdir" && pwd)"
      fi
      local main_repo
      main_repo="$(cd "$gitdir/../../.." && pwd)"
      echo "$main_repo"
      return 0
    fi
  fi
  return 1
}

# ソースの決定: 環境変数 > 自動検出
if [ -n "${SECRETS_SOURCE:-}" ]; then
  SOURCE="$SECRETS_SOURCE"
elif SOURCE="$(detect_main_repo)"; then
  :
else
  echo "メインリポジトリを検出できません"
  echo "SECRETS_SOURCE 環境変数でソースディレクトリを指定してください"
  exit 1
fi

# メインリポ自体で実行された場合はスキップ
if [ "$SOURCE" = "$PROJECT_ROOT" ]; then
  echo "メインリポジトリ内で実行されています。コピーは不要です。"
  exit 0
fi

# --- 引数パース ---
FORCE=false
INIT_SOURCE=false
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    --init)  INIT_SOURCE=true ;;
    --help|-h)
      echo "Usage: $0 [--init] [--force] [--help]"
      echo ""
      echo "  (引数なし)  メインリポ → ワークスペースにシークレットをコピー"
      echo "  --init      ワークスペース → メインリポにエクスポート（初回ブートストラップ）"
      echo "  --force     既存ファイルを上書き"
      exit 0
      ;;
    *)
      echo "不明なオプション: $arg"
      echo "$0 --help を参照してください"
      exit 1
      ;;
  esac
done

# --- Init モード ---
if [ "$INIT_SOURCE" = true ]; then
  echo "=== シークレットファイルをメインリポにエクスポート ==="
  echo "ソース: $PROJECT_ROOT"
  echo "エクスポート先: $SOURCE"
  echo ""

  copied=0
  for rel_path in "${SECRET_FILES[@]}"; do
    src="$PROJECT_ROOT/$rel_path"
    dst="$SOURCE/$rel_path"
    if [ -f "$src" ]; then
      if [ -f "$dst" ] && [ "$FORCE" != true ]; then
        if diff -q "$src" "$dst" > /dev/null 2>&1; then
          echo "  skip: $rel_path (同一)"
        else
          echo "  warn: $rel_path (異なる。--force --init で上書き可能)"
        fi
      else
        mkdir -p "$(dirname "$dst")"
        cp -p "$src" "$dst"
        echo "  done: $rel_path"
        copied=$((copied + 1))
      fi
    fi
  done

  echo ""
  echo "結果: $copied ファイルをエクスポートしました"
  exit 0
fi

# --- 通常モード: メインリポ → ワークスペースにコピー ---
echo "=== シークレットファイルのコピー ==="
echo "ソース: $SOURCE"
echo "ワークスペース: $PROJECT_ROOT"
echo ""

if [ ! -d "$SOURCE" ]; then
  echo "ソースディレクトリが存在しません: $SOURCE"
  exit 0
fi

copied=0
skipped=0
warned=0

for rel_path in "${SECRET_FILES[@]}"; do
  src="$SOURCE/$rel_path"
  dst="$PROJECT_ROOT/$rel_path"

  if [ ! -f "$src" ]; then
    echo "  skip: $rel_path (メインリポに未配置)"
    skipped=$((skipped + 1))
    continue
  fi

  if [ ! -f "$dst" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -p "$src" "$dst"
    echo "  done: $rel_path"
    copied=$((copied + 1))
  elif [ "$FORCE" = true ]; then
    cp -p "$src" "$dst"
    echo "  done: $rel_path (上書き)"
    copied=$((copied + 1))
  else
    if diff -q "$src" "$dst" > /dev/null 2>&1; then
      echo "  skip: $rel_path (同一)"
    else
      echo "  warn: $rel_path (異なる。--force で上書き可能)"
      warned=$((warned + 1))
    fi
  fi
done

echo ""
echo "結果: コピー=$copied  スキップ=$skipped  警告=$warned"
