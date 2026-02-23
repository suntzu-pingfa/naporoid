# Napoleon アプリ仕様書

## 1. 概要
- 本アプリは 4 人対戦の Napoleon カードゲームを実装した Kivy アプリ。
- 人間プレイヤーは `P1`、CPU は `P2`〜`P4`。
- ゲーム進行は `bid -> lieut -> exchange -> play -> done`。
- Android ビルドは `buildozer.spec` の設定を利用する。

## 2. 構成
- `main.py`: 画面 UI、ユーザー操作、CPU の 0.2 秒間隔進行、ログ表示。
- `engine.py`: ゲームルール、手札管理、合法手判定、トリック勝敗判定、得点判定。
- `Cards/*.png`: カード画像リソース。
- `buildozer.spec`: Android パッケージ設定。

## 3. 実行環境・ビルド
### 3.1 ローカル実行
1. Python 3 と Kivy をインストール
2. `python main.py` を実行

### 3.2 Android ビルド設定
- タイトル: `Napoleon`
- パッケージ: `org.fujiwara.napoleon`
- 要件: `python3,kivy`
- 画面: `landscape`
- API: `android.api = 34`, `android.minapi = 24`
- アーキテクチャ: `arm64-v8a`

## 4. データ仕様
### 4.1 カード表現
- Joker: `Jo`
- 通常札: `<suit><rank>`
- スート: `s,h,d,c`（Spade, Heart, Diamond, Club）
- ランク: `2..9,0,J,Q,K,A`（`0` は 10）
- デッキ総数: 53 枚（52 枚 + Joker）

### 4.2 主要状態（GameEngine）
- `players[4]`: 各プレイヤー手札・役職
- `mount`: 山札 5 枚
- `obverse`: 切り札スート
- `target`: 目標絵札数
- `lieut_card`: 副官指定カード
- `stage`: `idle|bid|lieut|exchange|play|done`
- `leader_id`: 現在トリックのリーダー
- `turn_no`: トリック番号（1〜12）
- `turn_cards`: 現在トリックの実カード
- `turn_display`: 画面表示用カード
- `pict_won_count`: プレイヤーごとの獲得絵札数

## 5. 画面仕様（main.py）
### 5.1 主な UI 要素
- ステータス表示: ステージ、トリック番号、リーダー、Napoleon、宣言など
- ログ表示: 行動履歴を追記
- Declare 行: スート、目標値、`Declare`
- Lieut 行: 副官カード指定、`Set Lieut`、`Auto`
- 操作行: `Swap`、`FinishEx`、`Play`、`CPU`、`New`
- Table: P1〜P4 の場札表示
- Mount: 交換時のみ表示
- Hand: 自分の手札（横スクロール）

### 5.2 入力操作
- 手札タップ:
  - `exchange` 中は交換対象の選択
  - `play` 中はカードをプレイ
- Mount タップ:
  - `exchange` かつ人間が Napoleon の場合のみ選択
- `Play`:
  - 自ターンなら手札タップ待ち
  - CPU ターンなら CPU 自動進行開始

## 6. ゲーム進行仕様
### 6.1 新規ゲーム
- `new_game()` でシャッフル、配札（Mount 5 枚 + 各 12 枚）
- `main.py` 側で `napoleon_id` をランダム設定（1〜4）
- ステージを `bid` に設定

### 6.2 宣言（bid）
- 人間 Napoleon の場合:
  - UI 選択値で `obverse`, `target` を設定
- CPU Napoleon の場合:
  - ランダムで宣言
- 宣言後ステージを `lieut` に遷移

### 6.3 副官指定（lieut）
- 副官カードは Napoleon 手札外から選択必須
- 指定カードが Mount 内なら `lieut_in_mount=True`
- 指定カードが他プレイヤー手札にあれば `lieut_id` を確定
- 指定完了で `exchange` に遷移

### 6.4 交換（exchange）
- Napoleon 手札 1 枚と Mount 1 枚を交換
- 人間 Napoleon は UI で複数回実行可能
- `FinishEx` 実行で `play` 開始、`turn_no=1`

### 6.5 プレイ（play）
- リーダーから順に 1 枚ずつ出して 1 トリック（4 枚）
- 合法手:
  - 1 トリック目は `obverse` スートの非 Joker を禁止
  - フォロー時は同スート優先（ただし Joker は追従時にも許可）
- 4 枚揃うと勝者判定し、勝者が次トリックのリーダー
- 12 トリック終了で `done`

## 7. 勝敗判定仕様（engine.py）
### 7.1 特殊カード強度
- Joker: 最強
- Mighty (`sA`)
- Yoro (`hQ`): Mighty 同時出現時に特殊化
- 正ジャック（切り札 J）
- 逆ジャック（切り札反転スート J）

### 7.2 2 の特例
- 4 枚の実効スートが同一なら「2」カードに強化補正

### 7.3 絵札カウント
- 絵札: `10,J,Q,K,A`（Joker 除く）
- トリック勝者がそのトリック中の絵札を獲得

### 7.4 最終スコア
- Napoleon 側絵札数 `nap_pict` を算出
- `nap_pict == 20`: Napoleon 側敗北
- `nap_pict >= target`: Napoleon 側勝利
- ゲーム終了時に目標未達: Napoleon 側敗北

## 8. CPU 仕様
- カード選択は `legal_moves` から最大スコアを選択
- スコアは基本的に `strength(c) - resource_cost`
- Joker は早出し抑制の高コスト
- UI 側では CPU プレイを 0.2 秒間隔で実行

## 9. 表示仕様上の補助
- 4 枚目プレイ時に `turn_display` が即クリアされても見えるよう、
  UI 側で `last_turn_display_snapshot` を保持
- 各 P1〜P4 の場札はセル中央に表示
- ウィンドウサイズに応じてカードサイズを再計算

## 10. 既知の実装上の注意
- `engine.py` に `set_declaration()` はあるが、`main.py` は直接フィールド設定で宣言処理を実施している。
- 役職公開演出（副官公開など）は最小実装で、主に内部状態として管理される。

