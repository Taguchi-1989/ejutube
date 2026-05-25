# VOICEVOX Engine セットアップ手順（Windows）

## 概要

ejutube パイプラインは日本語 TTS に VOICEVOX Engine を使用します。
VOICEVOX Engine はローカルで動作する HTTP サーバーで、テキストを受け取り WAV 音声を返します。

## ダウンロード

1. https://github.com/VOICEVOX/voicevox_engine/releases にアクセスします。
2. 最新リリースの Assets から `windows-cpu.zip`（または GPU 版）をダウンロードします。
3. 任意のディレクトリに展開します（例: `C:\tools\voicevox_engine\`）。

## 起動

```powershell
cd C:\tools\voicevox_engine
.\run.exe
```

起動すると `http://127.0.0.1:50021` でサーバーが立ち上がります。

動作確認:

```powershell
Invoke-RestMethod http://127.0.0.1:50021/version
```

`"0.x.x"` のようなバージョン文字列が返れば正常です。

## .env 設定

```
VOICEVOX_ENDPOINT=http://127.0.0.1:50021
```

## 話者プリセット

`--voice` オプションでプリセット名を指定します（デフォルト: `tsumugi`）。

```powershell
yt-ja tts VIDEO_ID --voice tsumugi   # デフォルト 春日部つむぎ (id=8) — 聞きやすい
yt-ja tts VIDEO_ID --voice zundamon  # ずんだもん (id=3)
yt-ja tts VIDEO_ID --voice metan     # 四国めたん (id=2)
```

speaker ID を直接指定する場合（`--voice` より優先）:

```powershell
yt-ja tts VIDEO_ID --speaker 8
```

プリセット一覧と全話者を確認するには:

```powershell
yt-ja tts-speakers
```

### 確認済み話者 ID（VOICEVOX v0.25.0）

| プリセット | 表示名       | speaker_id | スタイル  |
|------------|--------------|------------|-----------|
| tsumugi    | 春日部つむぎ | 8          | ノーマル  |
| zundamon   | ずんだもん   | 3          | ノーマル  |
| metan      | 四国めたん   | 2          | ノーマル  |

## GPU 版について

NVIDIA GPU がある場合は `windows-gpu.zip` を使うと生成速度が大幅に向上します。
GPU 版には CUDA 11.8 以上が必要です。

## ライセンス注意事項

VOICEVOX の各話者キャラクターには個別の利用規約があります。
商用利用・公開利用の前に必ず各キャラクターの規約を確認してください。

参照: https://voicevox.hiroshiba.jp/term/

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| ポート 50021 が使用中 | タスクマネージャーで競合プロセスを終了する |
| `run.exe` が起動しない | Visual C++ 再頒布パッケージをインストールする |
| 音声が生成されない | `VOICEVOX_ENDPOINT` が `.env` に設定されているか確認する |
