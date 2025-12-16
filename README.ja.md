# ASScii: Video-to-ASS ASCII subtitle generator

[English](README.md)

ASSciiは、動画をリアルタイムでASCIIアートに変換しつつ、Aegisub互換のASS字幕として書き出せるデスクトップツールです。TkinterベースのGUIで元動画とASCII化したプレビューを並べて確認でき、微調整した結果をそのまま字幕ファイル化してYouTubeなどにアップロードするワークフローを支援します。

## 主な機能
- 2ペインプレビュー: 左に元動画、右にASCII化した結果を同時表示。
- 豊富な調整パラメータ: 列・行数、FPS、γ補正、コントラスト、明るさ、反転、文字セット(Blocks/Classic/Dense)などをリアルタイム変更。
- ASCIIマスク描画: ASCIIキャンバス上を左ドラッグでマスク(消去)、右ドラッグで復帰。意図しない領域を隠した状態でエクスポートできます。
- フレームコントロール: スライダー／スピンボックスで任意フレームへジャンプ、Pause/Play、Rewindのホットキーにも対応。
- ASS出力: 指定区間・座標・フォント情報・PlayResを設定し、1フレーム=1イベントのASSファイルを生成。
- 先読みキャッシュ: スクロールやループ再生でも安定したプレビューを維持。

## 動作要件
- Python 3.10以上 (標準Tkinterが使える環境)
- pipで導入する外部ライブラリ
  - numpy
  - opencv-python
  - pillow
- macOS / Windows / Linux いずれも動作想定。macOSでは`python3`がTkinterを同梱しているバージョンを利用してください。
- 大きな動画を扱う場合は十分なメモリとストレージを確保してください (`big_buck_bunny_1080p_h264.mov`を同梱)。

## セットアップ
1. 仮想環境を作成
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windowsは .venv\Scripts\activate
   ```
2. 依存パッケージをインストール
   ```bash
   python -m pip install --upgrade pip
   python -m pip install numpy opencv-python pillow
   ```
3. フォント: 既定では`DejaVuSansMono.ttf`を探します。別フォントを使いたい場合は同じディレクトリに配置するか、GUIのエクスポートダイアログで任意のフォント名を入力してください。

## 使い方
### 1. プレビューを起動
```bash
python ascii_video_preview.py               # ダイアログで動画を選択
python ascii_video_preview.py sample.mp4    # 直接パスを指定
```
- `o` : 動画を開く
- `Space` : 再生／一時停止
- `r` : 冒頭へ巻き戻し
- `e` : ASSエクスポートダイアログ

### 2. パラメータ調整
- **Cols / Rows**: ASCIIグリッドの解像度。Lock aspectを有効にすると動画比率に合わせて行数を自動調整。
- **FPS**: プレビューおよび書き出し間隔。高すぎるとASSファイルが巨大になるので注意。
- **Gamma / Contrast / Brightness**: グレースケール→文字マッピング前のトーン調整。
- **Charset / Invert / Font size**: キャラクターセット、輝度反転、表示フォントサイズ。
- **Eraser/Restore**: ASCII表示をクリックドラッグして部分的にマスク。
- **Frame Slider/Spinbox**: 任意フレームにジャンプ。動画の終端で自動ループします。

### 3. ASS字幕を書き出す
1. `Export ASS (e)`を押してダイアログを開く。
2. 下記パラメータを入力。
   - Start / Duration (sec): フレーム列の開始時刻と書き出し秒数。
   - Position X / Y: `PlayResX/Y`座標系での配置点。UI上のASCII描画位置と揃えたい場合は再生ウィンドウのサイズに合わせて調整。
   - Font name / Font size: ASSスタイルの書式。例: `DejaVu Sans Mono`, `Menlo`.
   - PlayResX / PlayResY: 字幕側の仮想解像度 (例: 1920x1080)。
3. 保存先`.ass`ファイルを指定すると1フレームごとのDialogueイベントを生成します。
4. 推奨ワークフロー: Aegisubで最終確認 → YTSubConverterでウェブ向けに変換 → YouTubeへアップロード。

## チューニングのヒント
- 列・行数を上げるほど細部が出ますが、処理とASSファイルが重くなります。YouTube字幕として使う場合は`cols=100前後`, `fps=10-12`程度が扱いやすい目安です。
- 文字セットは`Dense (16)`が最も細かい階調、`Blocks (5)`は大胆な表現に向きます。
- ガンマ・コントラストは暗部/明部で文字が潰れる場合に小刻みに変えてください。
- 明滅対策として輝度を抑えたい場合はBrightnessをマイナス方向へ。
- ASCIIマスクは動画ファイルごと・フレームごとに保持されます。`Clear Eraser (frame)`ボタンでリセット可能。

## よくある問題と対処
- **動画が開けない**: コーデック非対応の場合はH.264 MP4へ変換してください。
  ```bash
  ffmpeg -i input.mov -c:v libx264 -crf 18 -preset veryfast -c:a aac output.mp4
  ```
- **Tkinterが見つからない**: Linuxの場合`python3-tk`等をOSパッケージからインストールしてください。
- **フォントがずれる**: 固定幅フォントを利用し、エクスポート時のフォント名とプレビューで使っているフォントを揃えてください。

## サンプル
- `big_buck_bunny_1080p_h264.mov`を同梱しているので、初回はこれを使って操作感を確認できます。

## ライセンス
現在このリポジトリにはライセンスファイルが含まれていません。公開・配布する場合は適切なライセンス文書を追加してください。
