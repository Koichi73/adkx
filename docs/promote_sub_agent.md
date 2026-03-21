# サブエージェントを adk web に公開する

## 課題

`adk web` は各エージェントディレクトリの `root_agent` しか発見しない。
`test_sub_agent/agent.py` に定義された `greet_agent` のようなサブエージェントを単体でテストするには、別ディレクトリを手動で作る必要がある。

## 方針

### ステップ1: エイリアスディレクトリ方式（ADK無改造）

`.adk/preset.yaml` に `agent_path` を記載し、エイリアス用のディレクトリを作成する。
そのディレクトリの `__init__.py` が preset.yaml を読み、指定パスのエージェントを `root_agent` として公開する。

```
adk_web/
├── test_sub_agent/              # 元のエージェント（root_agent + greet_agent）
│   ├── __init__.py
│   ├── agent.py
│   └── .adk/
│       └── preset.yaml
├── test_sub_agent_greet/        # エイリアスディレクトリ（手動作成）
│   ├── __init__.py              # preset.yaml を読んで root_agent を動的解決
│   └── .adk/
│       └── preset.yaml          # agent_path で greet_agent を指定
```

`preset.yaml` の書き方:

```yaml
# agent_path: "モジュールパス.属性名" の形式（. 区切り）
agent_path: "test_sub_agent.agent.greet_agent"
```

`__init__.py` の実装:

```python
import importlib
import yaml
from pathlib import Path

_preset_path = Path(__file__).parent / ".adk" / "preset.yaml"
with open(_preset_path) as f:
    _config = yaml.safe_load(f)

_parts = _config["agent_path"].rsplit(".", 1)
_module = importlib.import_module(_parts[0])
root_agent = getattr(_module, _parts[1])
```

これだけで `adk web` のドロップダウンに `test_sub_agent_greet` が追加される。

### ステップ2: preset_server.py による自動生成

preset.yaml に `promote_agents` セクションを追加し、`preset_server.py` 起動時にエイリアスディレクトリを自動生成する。手動でディレクトリを作る手間を省く。

```yaml
promote_agents:
  # module 省略時は agent.py 内を参照（{parent}.agent.{name}）
  greet_agent: {}

  # 別ファイル・サブフォルダの場合は module を指定
  dog_agent:
    module: sub_agents.dog_agent

  # エージェントごとに initial_state を個別設定可能
  cat_agent:
    module: cat_agent
    initial_state:
      mood: happy
```
