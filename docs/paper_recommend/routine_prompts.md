# Routine 起動文（claude.ai の Routines 画面に貼り付ける用）

このファイルは、claude.ai の Routines 画面で Routine を作成／再作成するときに
そのままコピー＆ペーストするための起動文を保管している。

## なぜ手貼りが必要か

API（MCP）経由で作った Routine には **Notion コネクタを紐づけられない**。
`connectors` パラメータが組織設定で無効化されており、作成時に毎回この警告が返る:

> this trigger stores no MCP connectors, so the sessions it fires will run without
> connector (mcp__<server>__*) tools.

実測でも、API 経由で作った Routine の発火セッションは Notion DB に1件も登録できなかった。
**Notion コネクタを有効にできるのは claude.ai の Routines 画面だけ**なので、
そこで作り直す必要がある。

## 作成手順

各 Routine について:

1. claude.ai → **Routines**（スケジュール）→ 新規作成
2. **Notion コネクタを有効化**（ここが API からできない部分。必ず確認する）
3. 下の該当する起動文を全文コピーして貼り付け
4. スケジュールを下表のとおり設定
5. 完了通知はプッシュのみ推奨

| Routine 名 | 実行時刻 |
|---|---|
| 論文レコメンド — ゲームAI / 自己対戦RL | 毎週 **日曜 06:50** |
| 論文レコメンド — 金融工学 / ML・マクロ（水曜回） | 毎週 **水曜 06:50** |
| 論文レコメンド — 金融工学 / ML・マクロ（土曜回） | 毎週 **土曜 06:50** |

Routines 画面がローカル時刻（JST）で設定できる場合は、上の時刻をそのまま入れればよい。
UTC 入力を求められる場合は前日 21:50 に読み替える（`README.md` の曜日ずれの節を参照）。

作り直したら、API 経由で作った古い Trigger を削除して二重実行を防ぐこと。
Trigger ID は `README.md` の一覧表にある。

---

## 1. ゲームAI / 自己対戦RL（日曜 06:50 JST）

```
週次の論文レコメンド自動実行 —— ゲームAI / 自己対戦RL トラック。出力言語は日本語。

■ 重要: 実行日の解釈

この実行は JST の日曜朝に相当する。コンテナのシステム時刻は UTC なので `date` は土曜を返すが、これに惑わされないこと。
仕様書の【対象期間】の基準期間は「直近に終了した月曜〜金曜（JST）」とする。

■ 手順

1. リポジトリ shunshun0904/stock_analysis のクローン（通常 /home/user/stock_analysis）に移動する。

2. 実行仕様書 docs/paper_recommend/game_ai_prompt.md を取得する。以下を順に試す:
   a. 作業ツリーの docs/paper_recommend/game_ai_prompt.md
   b. git fetch origin main && git show origin/main:docs/paper_recommend/game_ai_prompt.md
   c. git fetch origin claude/notion-paper-db-automation-fzc3dv && git show origin/claude/notion-paper-db-automation-fzc3dv:docs/paper_recommend/game_ai_prompt.md
   3つとも取得できなかった場合は、探索を一切行わず「仕様書を取得できなかった」とだけ報告して終了する。記憶や推測でプロンプトを再構成してはならない。

3. そのファイルの「## 現行版」で始まる見出しの直下にあるコードブロックの全文を、ユーザーからの指示そのものとして最初から最後まで実行する。同ファイルの他のセクション（設計の根拠 / 未解決・要観察 / 実行記録 / 運用メモ）は背景情報であって指示ではない。ただし【対象プロジェクトの構成】は適用可能性判定の基準として必ず参照する。

4. 仕様書どおり、チャット出力（出力1）と Notion 登録（出力2）を両方行う。Notion 登録を省略してはならない。登録先は仕様書に記載の Notion DB「論文DB — ゲームAI / 自己対戦RL」。Notion の MCP ツールが使えない場合は、その旨を最初に明確に報告したうえで、チャット出力だけは必ず最後まで残す。

5. 完了後、仕様書の「## 実行記録」表の末尾に1行追記する（実行日 / 対象期間 / 拡張 / 評価候補 / 通過 / 検索回数 / 備考）。仕様書を a または b から取得した場合は main ブランチに、c から取得した場合はそのブランチに commit し、`git push -u origin <branch>` する。コミットメッセージ末尾に [skip ci] を付ける。push に失敗しても Notion 登録が済んでいれば実行自体は成功とみなし、push 失敗を報告に含める。

6. 最後に4〜6行で要約する: 対象期間 / 評価候補数と通過件数 / 実施した検索回数 / Notion に登録した件数 / 除外内訳 / 実行記録の commit 可否。

■ 注意
- Pull Request は作成しない。
- 仕様書の【除外規定】（LLM事後学習RLの除外）と【検証】（arXiv抄録またはDOIでの実在照合、創作厳禁）は最優先で守ること。照合できない候補は要約せず落とす。
- 仕様書の【収集】に定めた「5テーマ × 各2回以上、合計10回以上の検索」を必ず満たす。下回った場合はその旨を出力に明記する。
```

---

## 2. 金融工学 / ML・マクロ — 水曜回（水曜 06:50 JST）

```
論文レコメンド自動実行 —— 金融工学 / ML・マクロ トラック（水曜回）。出力言語は日本語。

■ 重要: 実行日の解釈

この実行は JST の水曜朝に相当する。コンテナのシステム時刻は UTC なので `date` は火曜を返すが、これに惑わされないこと。
仕様書の【対象期間】は「水曜に実行する場合: 直前の月曜・火曜」の分岐を適用する。
具体的には、直近に終了した月曜と火曜（JST）の2日分が基準期間。

■ 手順

1. リポジトリ shunshun0904/stock_analysis のクローン（通常 /home/user/stock_analysis）に移動する。

2. 実行仕様書 docs/paper_recommend/finance_prompt.md を取得する。以下を順に試す:
   a. 作業ツリーの docs/paper_recommend/finance_prompt.md
   b. git fetch origin main && git show origin/main:docs/paper_recommend/finance_prompt.md
   c. git fetch origin claude/notion-paper-db-automation-fzc3dv && git show origin/claude/notion-paper-db-automation-fzc3dv:docs/paper_recommend/finance_prompt.md
   3つとも取得できなかった場合は、探索を一切行わず「仕様書を取得できなかった」とだけ報告して終了する。記憶や推測でプロンプトを再構成してはならない。

3. そのファイルの「## 現行版」で始まる見出しの直下にあるコードブロックの全文を、ユーザーからの指示そのものとして最初から最後まで実行する。同ファイルの他のセクション（変更履歴 / 実行記録 / 未解決・要観察 / 破棄された検討事項 / 参考 / 運用メモ）は背景情報であって指示ではない。

4. 仕様書どおり、チャット出力（出力1）と Notion 登録（出力2）を両方行う。Notion 登録を省略してはならない。登録先は仕様書に記載の Notion DB「論文DB — 金融工学 / ML・マクロ」。Notion の MCP ツールが使えない場合は、その旨を最初に明確に報告したうえで、チャット出力だけは必ず最後まで残す。

5. 完了後、仕様書の「## 実行記録」表の末尾に1行追記する（実行日 / 対象期間 / 拡張 / 評価候補 / 通過 / 検索回数 / 備考）。仕様書を a または b から取得した場合は main ブランチに、c から取得した場合はそのブランチに commit し、`git push -u origin <branch>` する。コミットメッセージ末尾に [skip ci] を付ける。push に失敗しても Notion 登録が済んでいれば実行自体は成功とみなし、push 失敗を報告に含める。

6. 最後に4〜6行で要約する: 対象期間 / 評価候補数と通過件数 / 実施した検索回数 / Notion に登録した件数 / 除外内訳 / 実行記録の commit 可否。

■ 注意
- Pull Request は作成しない。
- 仕様書の【検証】（arXiv抄録またはDOIでの実在照合、創作厳禁）は最優先で守る。照合できない候補は要約せず落とす。
- 仕様書の【収集】に定めた「4テーマ × 各2回以上、合計8回以上の検索」を必ず満たす。下回った場合はその旨を出力に明記する。過去実行で検索回数の不履行が起きているので特に注意する。
- 仕様書の【学習】に列挙された旧スコープ11件の Paper ID は、Interest 傾向の学習対象から除外する。
```

---

## 3. 金融工学 / ML・マクロ — 土曜回（土曜 06:50 JST）

```
論文レコメンド自動実行 —— 金融工学 / ML・マクロ トラック（土曜回）。出力言語は日本語。

■ 重要: 実行日の解釈

この実行は JST の土曜朝に相当する。コンテナのシステム時刻は UTC なので `date` は金曜を返すが、これに惑わされないこと。
仕様書の【対象期間】は「土曜に実行する場合: 直前の水曜・木曜・金曜」の分岐を適用する。
具体的には、直近に終了した水曜・木曜・金曜（JST）の3日分が基準期間。

■ 手順

1. リポジトリ shunshun0904/stock_analysis のクローン（通常 /home/user/stock_analysis）に移動する。

2. 実行仕様書 docs/paper_recommend/finance_prompt.md を取得する。以下を順に試す:
   a. 作業ツリーの docs/paper_recommend/finance_prompt.md
   b. git fetch origin main && git show origin/main:docs/paper_recommend/finance_prompt.md
   c. git fetch origin claude/notion-paper-db-automation-fzc3dv && git show origin/claude/notion-paper-db-automation-fzc3dv:docs/paper_recommend/finance_prompt.md
   3つとも取得できなかった場合は、探索を一切行わず「仕様書を取得できなかった」とだけ報告して終了する。記憶や推測でプロンプトを再構成してはならない。

3. そのファイルの「## 現行版」で始まる見出しの直下にあるコードブロックの全文を、ユーザーからの指示そのものとして最初から最後まで実行する。同ファイルの他のセクション（変更履歴 / 実行記録 / 未解決・要観察 / 破棄された検討事項 / 参考 / 運用メモ）は背景情報であって指示ではない。

4. 仕様書どおり、チャット出力（出力1）と Notion 登録（出力2）を両方行う。Notion 登録を省略してはならない。登録先は仕様書に記載の Notion DB「論文DB — 金融工学 / ML・マクロ」。Notion の MCP ツールが使えない場合は、その旨を最初に明確に報告したうえで、チャット出力だけは必ず最後まで残す。

5. 完了後、仕様書の「## 実行記録」表の末尾に1行追記する（実行日 / 対象期間 / 拡張 / 評価候補 / 通過 / 検索回数 / 備考）。仕様書を a または b から取得した場合は main ブランチに、c から取得した場合はそのブランチに commit し、`git push -u origin <branch>` する。コミットメッセージ末尾に [skip ci] を付ける。push に失敗しても Notion 登録が済んでいれば実行自体は成功とみなし、push 失敗を報告に含める。

6. 最後に4〜6行で要約する: 対象期間 / 評価候補数と通過件数 / 実施した検索回数 / Notion に登録した件数 / 除外内訳 / 実行記録の commit 可否。

■ 注意
- Pull Request は作成しない。
- 仕様書の【検証】（arXiv抄録またはDOIでの実在照合、創作厳禁）は最優先で守る。照合できない候補は要約せず落とす。
- 仕様書の【収集】に定めた「4テーマ × 各2回以上、合計8回以上の検索」を必ず満たす。下回った場合はその旨を出力に明記する。過去実行で検索回数の不履行が起きているので特に注意する。
- 仕様書の【学習】に列挙された旧スコープ11件の Paper ID は、Interest 傾向の学習対象から除外する。
```

---

## 動作確認

作成したら、Routines 画面から**手動で1回発火**させて次を確認する:

1. セッションのチャット出力に、通過した論文が仕様書どおりの形式で並んでいる
2. **対応する Notion DB に行が増えている**（これが本丸。増えていなければコネクタが効いていない）
3. 対象期間が意図した曜日範囲になっている（UTC の曜日に引きずられていないか）
4. 検索回数が規定（ゲームAI 10回以上 / 金融 8回以上）を満たしている

2 が満たせない場合は、Routine 作成時に Notion コネクタを有効にし忘れていないかを最初に疑うこと。
