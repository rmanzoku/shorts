# Pre-commit Verification

コミット前の検証を実行する。

## Step 1: テスト実行

```bash
.venv/bin/pytest tests/ -v
```

全テストがパスすることを確認。失敗がある場合はコミットしない。

## Step 2: Lint

```bash
.venv/bin/ruff check src/ tests/
```

## Step 3: 品質チェック

変更ファイルに対して以下を確認:

- [ ] OpenAI API キーがハードコードされていない
- [ ] `.env` や認証情報がコミット対象に含まれていない
- [ ] 画像プロンプトに「Do not include any text」が含まれている（AI 画像の文字化け防止）
- [ ] CJK テキスト分割で語の途中切れが起きていない
- [ ] 字幕の最大文字数（22 文字）を超えていない
- [ ] 字幕の最低表示時間（1.0 秒）が守られている

## Step 4: diff 確認

```bash
git diff --stat
git diff
```

意図しない変更が含まれていないか確認する。

## Step 5: レポート

全チェックがパスしたら「コミット可能」と報告する。
違反がある場合はファイルパスと内容を報告する。
