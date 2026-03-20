# adk web の内部構造調査と adk-preset の設計判断

## 背景

ADK（Google Agent Development Kit）の `adk web` コマンドは、エージェントの動作をブラウザ上で確認できる開発用UIを提供する。しかし、セッションの初期stateや初期クエリを毎回手入力する必要があり、開発中に同じ条件で繰り返しテストする場面でこの手間が積み重なる。

この文書では、`adk web` の内部構造を調査した結果と、それを踏まえた解決策の設計判断を記録する。

---

## 調査結果

対象バージョン: google-adk 1.27.2

### 全体構成

`adk web` は以下の3層で構成されている。

**CLIレイヤー** (`cli_tools_click.py`) がコマンドライン引数を受け取り、**FastAPIレイヤー** (`fast_api.py`) がサービス群を初期化して `AdkWebServer` を構築する。`AdkWebServer` (`adk_web_server.py`, 約1900行) が REST API エンドポイント群を定義し、**Angular製のフロントエンド** (minified JS, 約4.7MB) がブラウザUIを提供する。

### セッション作成の流れ

セッション作成に関わるコードを追った結果、以下が判明した。

**バックエンドには初期state注入の口がすでにある。** `adk_web_server.py` の217行目で定義されている `CreateSessionRequest` は、`state: Optional[dict[str, Any]]` と `events: Optional[list[Event]]`、`session_id: Optional[str]` を受け付ける。`POST /apps/{app_name}/users/{user_id}/sessions` にこのbodyを送ると、`session_service.create_session(state=state)` がそのまま呼ばれる。つまり、REST APIレベルでは初期stateの注入は完全にサポートされている。

**フロントエンドにはその入力手段がない。** AngularのUIコードを確認したところ、"New Session" ボタンは `createSession(userId, appName)` をbody無しでPOSTするだけで、stateを渡すフォームやフィールドは存在しない。これが「毎回手入力が面倒」の根本原因である。

### create_empty_state の正体

`cli/utils/state.py` にある `create_empty_state()` は、エージェントのinstructionテンプレート内の `{variable}` パターンを正規表現で検出し、空文字列の辞書を生成するだけの関数だった。これはeval（評価）機能用のヘルパーであり、ユーザーが `create_session` で渡す初期stateとは独立した仕組みである。

### adk run（CLI版）の既存機能

`cli.py` には `InputFile` というPydanticモデルが定義されており、`state` と `queries` をJSONファイルから読み込んで `run_input_file()` で実行する仕組みが既に存在する。ただしこれは `adk run` コマンド専用で、`adk web` のUIとは連携しない。

### ブラウザURLパラメータ

フロントエンドのルーティングを確認したところ、`?app={name}&session={id}&userId={uid}` のクエリパラメータで特定のセッションを直接開けることが分かった。これは既存のセッション間を移動するための機能だが、外部から作成したセッションへの直接遷移にもそのまま使える。

---

## 設計判断

### 検討した選択肢

調査結果を踏まえ、3つのアプローチを検討した。

**A. adk web のフロントエンドを改修する。** Angular UIにstate入力フォームを追加する方法。最も直接的だが、minifiedされたAngularアプリを改修するのは現実的でなく、ADKのバージョンアップで差分が壊れるリスクが高い。本家へのPRが通るまでの待ち時間も不明。

**B. adk web 全体を自作する。** FastAPI + 軽量フロントエンドで `adk web` 相当のUIを再構築する方法。自由度は最高だが、`adk web` が持つチャットUI、stateビューア、イベント表示、trace表示、eval機能などを再実装するコストが大きすぎる。

**C. 既存のREST APIを外部から叩くCLIラッパーを作る。** バックエンドには既にstateを受け付けるAPIがあり、フロントエンドにはURLパラメータでセッションを開く機能がある。この2つを繋ぐ薄いスクリプトだけで目的は達成できる。

### 採用: C（CLIラッパー）

以下の理由でCを採用した。

**adk web 本体を一切改変しない。** REST APIを外部から叩くだけなので、ADKのバージョンアップに影響されない。APIの `/sessions` エンドポイントが消えない限り動き続ける。

**既存のUI資産をそのまま活かせる。** `adk web` のチャットUI、stateビューア、trace表示などはそのまま使える。セッション作成の一点だけを外部から補完する最小限の介入。

**ワークフローが自然。** `adk web` を起動 → プリセットスクリプトを実行 → ブラウザが開く、という流れは既存の開発フローに無理なく乗る。

### 設計上の工夫

**yamlプリセットファイル。** `adk run` が `InputFile`（JSON）を使っている前例に倣いつつ、手書きしやすさを重視してYAMLを採用した。配置場所は `.adk/preset.yaml` とし、`adk web` が自動生成する `.adk/` ディレクトリの中に自然に収まるようにした。

**名前付きプリセット。** 同一のpreset.yaml内に `presets:` セクションを設け、`--preset debug` のように切り替えられるようにした。debug、demo、testなど、シナリオ別の初期条件を1ファイルで管理できる。

**初期クエリの送信。** セッション作成（`POST /sessions`）と初期クエリ送信（`POST /run`）を分離した。`--no-query` オプションでstateだけ設定してクエリは手動入力、という使い分けも可能。

**ブラウザ自動起動。** URLパラメータ `?app=...&session=...&userId=...` を組み立てて `webbrowser.open()` で開くことで、作成したセッションに直接遷移する。`--no-browser` でCI/スクリプト利用にも対応した。

---

## まとめ

`adk web` のバックエンドには初期state注入のAPIが既に存在し、フロントエンドにはセッション直接遷移のURL機構がある。この2つの間にフロントエンドの入力UIが欠けているだけだった。その隙間を埋める最小限のCLIラッパーを作ることで、adk web本体を改変せずに課題を解決した。