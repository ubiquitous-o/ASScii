# ASScii: Video-to-ASS ASCII subtitle generator

[English](README.md)

ASSciiは、Tkinter製のデスクトップアプリで動画フレームをリアルタイムにASCIIアートへ変換し、その結果をAegisub互換のASS字幕として書き出せます。スタイライズした字幕やオーバーレイを作りたいクリエイター向けに、プレビューと書き出しを同じ設定で一貫して扱えるよう設計されています。

![スクリーンショット](imgs/screenshot.png)
[Sample Video is here.](https://youtu.be/F6egk1YDVNs?si=4CGu6RdAGxIfq4wy)

## ハイライト
- 元動画とASCIIレンダリングを並べて表示するデュアルプレビュー。
- グリッド解像度、FPS、ガンマ、コントラスト、明るさ、反転、文字セット、フォント情報、アスペクトロックなど豊富なトーン・レイアウト調整。
- ASCIIキャンバス上で左ドラッグ/右ドラッグによるフレーム単位のマスク（消去／復帰）。書き出したASSにもマスク結果が反映されます。
- フル動画／現在フレーム／任意範囲から選べるASS書き出し（1フレーム=1イベント、座標やPlayResも自由設定）で、ASCIIブロックを映像解像度に合わせて自動スケーリング。
- `lucida-console.ttf`を優先し、Courier New / Menlo / DejaVu Sans Mono など複数の等幅フォントを自動検出してプレビューとエクスポートに共通利用。
- `ascii_core.py`（変換ユーティリティ）と`ass_exporter.py`（字幕ライター）に分割されたモジュール構成で、GUIを使わずスクリプトからも呼び出しやすい。

## リポジトリ構成
- `asscii_app.py` – GUIエントリポイント。Tkinter + OpenCV + Pillowでプレビュー＆書き出しを提供。
- `ascii_core.py` – `AsciiParams`やトーン補正、ASCII描画、マスク処理などの共通ロジック。
- `ass_exporter.py` – GUIからも呼ばれるASS書き出しモジュール。バッチ処理時にも利用可能。

## 必要要件
- Tkinterを利用できるPython 3.10以上。
- 追加パッケージ:
  ```text
  numpy
  opencv-python
  pillow
  customtkinter
  ```
- OpenCVで読み込める動画（H.264 MP4推奨）。

## セットアップ
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install numpy opencv-python pillow customtkinter
```
任意: `lucida-console.ttf`や`DejaVuSansMono.ttf`などの等幅フォントをスクリプトと同じディレクトリに置くか、システムにインストールしてください。アプリが自動検出したフォント名はプレビューとエクスポート設定に反映されます。

## 使い方
### 起動
```bash
python asscii_app.py            # ファイルダイアログから選択
python asscii_app.py input.mp4  # パスを直接指定
```

### ホットキー・コントロール
- `o` – 動画を開く
- `Space` – 再生/一時停止（起動直後は一時停止状態）
- `r` – 先頭フレームへ巻き戻し
- `e` – ASSエクスポートダイアログ
- `Export Text` ボタン – 現在表示中のASCIIフレームをプレーンテキストとして保存
- スライダー/スピンボックス – 任意フレームへジャンプ（末尾到達でループ）
- Lock aspect – 現在のフォント寸法と動画比率から行数を自動調整（初期状態でON）
- Eraser（左ドラッグ）/Restore（右ドラッグ） – セル単位のマスク。`Clear Eraser (frame)`でリセット

### ASSエクスポート
1. `Export ASS (e)`を押す。
2. フル動画／現在フレーム／任意範囲から書き出し対象を選び、`pos_x/pos_y`・フォント情報・PlayResを入力します。各ASCIIフレームが`\an7\pos(...)`付きDialogueイベントになり、マスク結果も反映されます。
3. 出力先`.ass`を指定して保存。
4. 推奨フロー: Aegisubで確認 → [YTSubConverter](https://github.com/arcusmaximus/YTSubConverter)で必要に応じて変換 → YouTube等へアップロード。

### ASCIIテキストのエクスポート
`Export Text` を押すと、現在プレビュー中のASCIIフレーム（マスク適用済み）をUTF-8テキストとして保存できます。静止画シェアやデバッグに便利です。

### スクリプトからの利用
バッチ処理を行いたい場合は`ascii_core.py`/`ass_exporter.py`から`AsciiParams`や`frame_to_ascii`、`export_ass`をインポートして使用できます。GUIに依存しない純Python関数です。

## ヒント
- 列・行数を増やすとディテールは上がりますが、処理コストとASSファイルサイズが急増します。`cols≈100 / rows≈45 / fps=10–12`が扱いやすい目安です。
- 滑らかな階調には`Dense (16)`、大胆なブロック表現には`Blocks (5)`が便利。
- まずガンマやコントラストを調整してから明るさを上げるとハイライトの飽和を避けやすいです。
- 反転は明色背景の映像にASCII字幕を重ねる場合に有効です。

## サンプルメディア
このリポジトリでは大容量動画を同梱していません。テスト用途にはBlender Foundationが公開するCC映画 **Big Buck Bunny** を公式サイトからダウンロードしてご利用ください: [https://peach.blender.org/](https://peach.blender.org/)

## ライセンス
[MIT](LICENSE)
