# claude-code-instinct - 独立プロジェクト計画

## 概要

Everything Claude Code リポジトリから「Instinct-Based Learning」を独立プロジェクトとして切り出し、`~/.claude` にインストール/アンインストール可能にする。

## プロジェクト構造

```
claude-code-instinct/
├── README.md
├── install.sh
├── uninstall.sh
├── pyproject.toml              # Python プロジェクト設定 (mypy, pytest, etc.)
├── src/
│   └── instincts/
│       ├── __init__.py
│       ├── config.py           # 設定・パス定義
│       ├── observer.py         # 観測ロジック（pre/post 共通）
│       └── cli.py              # CLI ロジック (status, evolve)
├── tests/
│   ├── __init__.py
│   ├── test_observer.py
│   └── test_cli.py
└── .claude/
    ├── instincts/
    │   ├── bin/
    │   │   ├── observe_pre.py      # フックエントリーポイント (pre)
    │   │   ├── observe_post.py     # フックエントリーポイント (post)
    │   │   └── instinct_cli.py     # CLI エントリーポイント
    │   └── agents/
    │       └── observer.md
    └── commands/
        ├── instinct-status.md
        └── evolve.md
```

## Python パッケージ構成

### src/instincts/config.py
```python
from pathlib import Path

INSTINCTS_DIR = Path.home() / ".claude" / "instincts"
OBSERVATIONS_FILE = INSTINCTS_DIR / "observations.jsonl"
PERSONAL_DIR = INSTINCTS_DIR / "personal"
# etc.
```

### src/instincts/observer.py
```python
def observe_pre(hook_data: dict) -> None:
    """PreToolUse フック処理"""
    ...

def observe_post(hook_data: dict) -> None:
    """PostToolUse フック処理"""
    ...
```

### .claude/instincts/bin/observe_pre.py
```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parents[4] / "src"))

from instincts.observer import observe_pre
# ...
```

## インストール後の状態

```
~/.claude/
├── settings.json               # フック設定を追加
├── instincts/                  # データディレクトリ（実体）
│   ├── bin/ -> [repo]/.claude/instincts/bin/       # シンボリックリンク
│   ├── agents/ -> [repo]/.claude/instincts/agents/ # シンボリックリンク
│   ├── observations.jsonl      # データ（実体）
│   ├── observations.archive/   # データ（実体）
│   └── personal/               # 学習された instinct（実体）
├── commands/
│   ├── instinct-status.md -> [repo]/.claude/commands/instinct-status.md
│   └── evolve.md -> [repo]/.claude/commands/evolve.md
```

## settings.json フック設定

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "~/.claude/instincts/bin/observe_pre.py"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "~/.claude/instincts/bin/observe_post.py"
      }]
    }]
  }
}
```

---

## 受け入れ基準 (EARS形式)

### AC1: インストール成功
**When** ユーザーが `./install.sh` を実行する
**Then** システムは:
- `~/.claude/instincts/` ディレクトリを作成
- `~/.claude/instincts/bin/` → プロジェクトの `.claude/instincts/bin/` へのシンボリックリンクを作成
- `~/.claude/instincts/agents/` → プロジェクトの `.claude/instincts/agents/` へのシンボリックリンクを作成
- `~/.claude/commands/` に各コマンドファイルへのシンボリックリンクを作成
- `~/.claude/instincts/personal/` ディレクトリを作成
- `~/.claude/settings.json` にフック設定をマージ
- 成功メッセージを表示

### AC2: アンインストール成功
**When** ユーザーが `./uninstall.sh` を実行する
**Then** システムは:
- シンボリックリンク `~/.claude/instincts/bin/` を削除
- シンボリックリンク `~/.claude/instincts/agents/` を削除
- コマンドのシンボリックリンクを削除
- `~/.claude/settings.json` からフック設定を削除
- 実行中の Observer プロセスを停止
- データ（observations, personal/）は保持

### AC3: アンインストール with purge
**When** ユーザーが `./uninstall.sh --purge` を実行する
**Then** AC2 の処理に加え、`~/.claude/instincts/` 全体を削除

### AC4: 観測フックの動作
**When** インストール後に Claude Code でツールが実行される
**Then** フックが発火し、`~/.claude/instincts/observations.jsonl` にイベントが記録される

### AC5: コマンドの動作
**When** インストール後に `/instinct-status` を実行する
**Then** 学習された instinct の一覧が表示される

### AC6: 既存設定の保持
**When** 既存の `~/.claude/settings.json` にカスタム設定がある状態でインストールする
**Then** 既存の設定は保持され、フック設定のみが追加される

### AC7: 冪等性
**When** インストールスクリプトを複数回実行する
**Then** エラーなく完了し、最終状態は一度のインストールと同じである

### AC8: 前提条件チェック
**When** Python3 がインストールされていない環境でインストールを実行する
**Then** エラーメッセージを表示し、インストールを中断

### AC9: 型チェック成功
**When** `mypy src/` を実行する
**Then** エラーなく完了する

### AC10: テスト成功
**When** `pytest` を実行する
**Then** すべてのテストがパスする

---

## 実装タスク

1. [ ] pyproject.toml 作成（pytest, mypy 設定）
2. [ ] src/instincts/ パッケージ作成
   - [ ] config.py
   - [ ] observer.py (pre/post ロジック)
   - [ ] cli.py (status, evolve ロジック)
3. [ ] tests/ 作成
   - [ ] test_observer.py
   - [ ] test_cli.py
4. [ ] .claude/instincts/bin/ エントリーポイント作成
   - [ ] observe_pre.py
   - [ ] observe_post.py
   - [ ] instinct_cli.py
5. [ ] .claude/instincts/agents/observer.md 作成
6. [ ] .claude/commands/ 作成
   - [ ] instinct-status.md
   - [ ] evolve.md
7. [ ] install.sh 作成
8. [ ] uninstall.sh 作成
9. [ ] README.md 作成
10. [ ] mypy / pytest 実行確認
