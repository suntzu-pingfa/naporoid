# Napoleonアプリ チュートリアル（初心者向け）

このガイドは、**このアプリで1ゲームを最後まで遊ぶ手順**を簡単にまとめたものです。

## 1. まず画面の見方
- `Stage`：現在の進行状態（`bid` / `lieut` / `exchange` / `play` / `done`）
- `Turn`：現在のターン番号
- `Decl`：宣言内容（Suit + 目標枚数）
- `Lieut`：副官として指名したカード
- `Your Hand`：あなたの手札
- ボタン：
  - `Declare`：宣言する
  - `CPU`：CPU進行
  - `Swap`：交換
  - `FinishEx`：交換終了
  - `Play`：カードを出す
  - `New`：新規ゲーム

---

## 2. ゲーム開始〜Declaration（Stage: bid）
1. `Spade / Heart / Diamond / Club` からSuitを選ぶ  
2. 目標枚数（13〜16）を選ぶ  
3. `Declare` を押す  

### ポイント
- CPUも宣言に参加します。
- CPUの宣言に対してHumanが再宣言できる流れになっています。
- Declarationに勝ったプレイヤーのSuitがObverseとなります。
- Obverseの反対のSuit (Spade <-> Club、Heart <-> Diamond)がReverseとなります。
- Spade-A(Mighty)、ObverseのJack、ReverseのJackが役札となり、左に示した順に強いカードとなります。

---

## 3. Lieut指名（Stage: lieut）
Napoleonになったプレイヤーが、**Lieutカード**を指定します。  
- Humanなら手動指定またはAuto
- CPUなら自動で選択

### ポイント
- 選んだカードの持ち主がLieutです（Mount内なら後で判明）。

---

## 4. Exchange（Stage: exchange）
NapoleonはMountと手札を交換します。

### 操作方法
1. `Your Hand` から1枚選ぶ  
2. `Mount` から1枚選ぶ  
3. `Swap` が有効になったら押す  
4. 必要回数交換したら `FinishEx`

### ポイント
- `Swap` は「手札1枚 + Mount1枚」選ばないと有効化されません。
- CPU Napoleon時は自動で交換します。

---

## 5. Play（Stage: play）
順番にカードを出して1ターン4枚で勝者決定、これを繰り返します。
ターンの勝者は、ターンで出された絵札(10、Jack、Queen、King)を獲得することができます。

### 基本操作
1. `Your Hand` からカードを選ぶ  
2. `Play` を押す  

### 表/裏表示ルール
- 先頭カードのSuitを持っていない場合、出したカードが裏になることがあります。
- 裏カードがあるターンは、終了後に表へ戻して表示してから進行します。

---

## 6. 特殊カード表示メッセージ
ターン終了時（必要なら裏返し解除後）に表示されます。

- `Mighty!`（sA）
- `Oberse Jack!`
- `Reverse Jack!`
- `Yoromeki!`（hQ）
- `Yoromeki Hits!!!`（同ターンでMighty(sA)とYoromeki(hQ)が揃った場合に条件成立）
- `Spade 2 Wins!` のような `2` 特殊勝利表示（条件成立時）

---

## 7. Jokerと2の重要ルール（このアプリ）
- **Joker**：ターン最初に出した場合、**役札がない限り強い**  
- **2**：ターンですべてのSuitが同じ場合かつ役札がない限り強いが、**1ターン目は通常の2扱い**

---

## 8. 結果画面（Stage: done）
最終結果で以下が表示されます。
- Napoleonの勝敗
- Target
- Napoleon + Lieutの絵札獲得枚数
- Napoleon / Lieut / Coalition / Mount のカード一覧
- Napoleon + Lieutの絵札獲得枚数がDeclarationの以上であれば、Napoleon軍の勝ちとなります。
- Napoleon + Lieutの絵札獲得枚数がDeclarationのTarget未満であれば、Coalition軍の勝ちとなります。

`New Game` で次のゲームへ進めます。

---

## 9. うまくいかない時
- ボタンが押せない：`Stage` と選択状態（カード選択済みか）を確認
- Exchangeできない：手札1枚とMount1枚の両方を選んでいるか確認
- Playできない：自分の手番か、リビール待ち中でないか確認
