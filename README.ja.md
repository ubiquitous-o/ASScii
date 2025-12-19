# ASScii: Video-to-ASS ASCII subtitle generator

[English](README.md)

ASSciiは、Tkinter製のデスクトップアプリで動画フレームをリアルタイムにASCIIアートへ変換し、その結果をAegisub互換のASS字幕として書き出せます。スタイライズした字幕やオーバーレイを作りたいクリエイター向けに、プレビューと書き出しを同じ設定で一貫して扱えるよう設計されています。

![スクリーンショット](imgs/screenshot.png)
[Sample Video is here.](https://youtu.be/F6egk1YDVNs?si=4CGu6RdAGxIfq4wy)

[Side by Side Ver.](https://youtube.com/shorts/jswRuja-WOU)

## ハイライト
- 元動画とASCIIレンダリングを並べて表示するデュアルプレビュー。
- グリッド解像度、FPS、ガンマ、コントラスト、明るさ、反転、組み込み文字セット/カスタム文字セット（日本語などマルチバイト文字対応）、アスペクトロックなど豊富なトーン・レイアウト調整。
- ASCIIキャンバス上で左ドラッグ/右ドラッグによるフレーム単位のマスク（消去／復帰）。書き出したASSにもマスク結果が反映されます。
- フル動画／現在フレーム／任意範囲から選べるASS書き出し（1フレーム=1イベント）。YouTubeが採用する384×288のPlayResへ自動正規化し、`Default`スタイル15ptを基準にした`\fs`倍率を自動計算するため、AegisubとYTSubConverterの見た目が一致します。
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

### コントロール
- `Open` / `Pause` / `Rewind` / `Export ASS` / `Export Text` ボタンから主要操作を行います。
- スライダーやフレーム入力で任意フレームへジャンプできます（末尾に達するとループ）。
- Lock aspect – フォントと動画の縦横比から行数を自動調整します（初期ON）。
- Eraser（左ドラッグ）/Restore（右ドラッグ） – セル単位でマスク。`Clear Eraser (frame)`でそのフレームのマスクをリセット。
- 再生はデフォルトで一時停止なので、設定を整えてからプレビューを更新してください。

### ASSエクスポート
1. `Export ASS (e)`を押す。
2. フル動画／現在フレーム／任意範囲から書き出し対象を選び、映像上での`pos_x/pos_y`を入力します。PlayResはデフォルトでYouTube基準の384×288になっており、GUIが座標・列/行・フォントサイズを自動的にそのグリッドへマッピングし、`Default`スタイル15ptに対する`\fs`倍率を挿入します。
3. 出力先`.ass`を指定して保存。
4. 推奨フロー: Aegisubで仕上がりを確認したら、そのまま [YTSubConverter](https://github.com/arcusmaximus/YTSubConverter) → YouTubeへ投入してください。手動でサイズを合わせる必要はありません。

### ASCIIテキストのエクスポート
`Export Text` を押すと、現在プレビュー中のASCIIフレーム（マスク適用済み）をUTF-8テキストとして保存できます。静止画シェアやデバッグに便利です。

### YouTube / YTSubConverter向け注意点
- エクスポーターは常に`PlayResX=384`, `PlayResY=288`を出力し、YouTubeが内部で確保しているキャンバスと同じスケールに合わせます。動画座標はこのグリッドへ自動変換され、YouTube側の2%セーフマージンも考慮されます。
- `Default`スタイルは15pt固定で、各Dialogueには`\fs`タグが挿入されます（`\fs`値 ÷ 15 が倍率）。そのためAegisubとYTSubConverterの描画倍率が一致します。
- YouTubeがサポートするフォント（Roboto / Courier Newなど）を選ぶと、プレビューと本番の字幅が一致しやすくなります。

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
