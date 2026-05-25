# ejutube

## プロジェクト概要

ejutube は、英語の YouTube 開発者チュートリアル動画を日本語話者が快適に視聴するためのローカル学習プレイヤーです。

YouTube 動画本体はダウンロードせず、公式 IFrame Player でそのまま再生しながら、
自動生成した日本語字幕・VOICEVOX による日本語音声・チャプター要約・コマンド一覧を重ねて表示します。
URL を入力するだけで、字幕取得・翻訳・TTS 音声生成・同期データ生成がパイプラインで自動実行されます。

English summary: ejutube is a local web app that wraps English YouTube tutorials with Japanese subtitles,
narration audio (VOICEVOX TTS), and summaries, while streaming the original video through the official
YouTube IFrame Player. No video file is downloaded or stored.

詳細な要件定義は `youtube_japanese_dubbing_learning_player_requirements.md` を参照してください。

---

## クイックスタート

### 前提条件

- Python 3.11 以上
- Node.js 20 以上
- VOICEVOX Engine（`docs/VOICEVOX_SETUP.md` 参照）
- ffmpeg（PATH に通しておく）
- **LLM バックエンド** — 次のどちらか:
  - **Ollama**（デフォルト・推奨）: `http://127.0.0.1:11434` で起動し、`ollama pull gemma4:e4b` でモデルを取得。APIキー不要、ローカルで完結。
  - **Anthropic Claude API**（opt-in）: `EJUTUBE_LLM_BACKEND=anthropic` で切り替え。`ANTHROPIC_API_KEY` が必要。品質は高いが従量課金。

### 手順

```powershell
# 1. リポジトリを clone してプロジェクトルートに移動
cd D:\dev\ejutube

# 2. .env を作成
copy .env.example .env
# デフォルトでは Ollama を使用するため API キーは不要。
# Anthropic API を使いたい場合のみ ANTHROPIC_API_KEY と EJUTUBE_LLM_BACKEND=anthropic を設定。

# 3. Python 依存関係をインストール
pip install -e .

# 4. Node.js 依存関係をインストール（フロントエンド）
npm install

# 5. プロジェクト初期化
yt-ja init

# 6. VOICEVOX Engine を起動（別ターミナル）
# docs\VOICEVOX_SETUP.md を参照

# 7. YouTube URL を処理する
yt-ja process "https://www.youtube.com/watch?v=xxxxxxxxxxx"

# 8. ローカルサーバーを起動して視聴
yt-ja serve
```

---

## アーキテクチャ

```text
YouTube URL
  |
  v
Video ID 抽出
  |
  v
字幕取得（VTT/SRT）
  |
  v
字幕正規化（秒数変換・ノイズ除去）
  |
  v
チャンク分割（10〜30 秒単位）
  |
  v
日本語字幕生成（Claude API / LLM）
  |
  v
読み上げ台本生成（自然な日本語）
  |
  v
TTS 音声生成（VOICEVOX Engine）
  |
  v
音声長計測（ffprobe）
  |
  v
同期 JSON 生成（player.json）
  |
  v
ローカル Web プレイヤーで視聴
（YouTube IFrame + 日本語音声同期）
```

コンポーネント詳細は要件定義書 section 7 を参照してください。

---

## ディレクトリ構成

```
ejutube/
  pipeline/         Python パイプライン（字幕・翻訳・TTS・同期）
  web/              Next.js フロントエンド（YouTube プレイヤー UI）
  schemas/          JSON Schema（全ステージ間のデータ契約）
  output/           動画ごとの生成成果物（.gitignore 済み）
  samples/          テスト用サンプルデータ
  docs/             セットアップ手順・エージェント引き継ぎ
  glossary.default.json  技術用語辞書
```

---

## CLI コマンド一覧

```powershell
yt-ja init                                    # 初期化
yt-ja process URL                             # フルパイプライン実行
  [--from STAGE]                              #   STAGE から再開（normalize/translate/tts 等）
  [--stop-after STAGE]                        #   STAGE で停止（chunked/translated/tts_generated 等）
  [--force-tts] [--force-sync]                #   既存成果物を無視して再生成
  [--skip-metadata]                           #   yt-dlp によるメタデータ取得をスキップ
yt-ja fetch-subtitle VIDEO_ID [--file PATH]   # 字幕取得（--file でローカルVTT/SRT投入）
yt-ja normalize VIDEO_ID                      # 字幕正規化
yt-ja chunk VIDEO_ID                          # チャンク分割
yt-ja translate VIDEO_ID                      # 日本語字幕生成（subtitle_ja）
yt-ja narrate VIDEO_ID                        # 読み上げ台本生成（narration_ja）
yt-ja summarize VIDEO_ID                      # 要約 summary.md 生成
yt-ja extract-commands VIDEO_ID               # コマンド/ファイル/設定の抽出
yt-ja tts VIDEO_ID                            # TTS 音声生成
  [--voice tsumugi|zundamon|metan]            #   プリセット切替（既定: tsumugi）
  [--speaker INT] [--speed FLOAT] [--force]   #   詳細オーバーライド
yt-ja tts-speakers                            # 利用可能な VOICEVOX 話者一覧
yt-ja sync VIDEO_ID                           # player.json 生成（= build-player のエイリアス）
yt-ja build-player VIDEO_ID                   # player.json 生成
yt-ja serve [--port 3000]                     # Web サーバー起動
```

---

## 公開・配布ポリシー

ejutube のコード自体は Apache License 2.0 で GitHub 公開を想定して設計されています。

**ただし、`output/` 配下の生成物（字幕翻訳・要約・TTS 音声）は YouTube 動画の二次的著作物にあたり、配布・公開してはなりません。**

- `.gitignore` が `output/`、`audio/`、`*.wav` をブロックしているため、通常の `git push` では流出しません。
- 個人学習・社内検証用途のみを想定しています。公開サービス化する場合は別途権利処理が必要です。
- 詳細は要件定義書 §12.5 / §18.4 を参照してください。

---

## ライセンスとクレジット

- 本リポジトリのコードは Apache License 2.0（`LICENSE` 参照）です。第三者帰属情報は `NOTICE` に記載しています。
- TTS 音声ライブラリのクレジット表記は `CREDITS.md` を参照してください（VOICEVOX / 春日部つむぎ / ずんだもん / 四国めたん）。
- 動画コンテンツ自体の権利は YouTube および元動画のチャンネル所有者に帰属します。

---

## ライセンス・法務メモ

- 動画本体は保存しません。YouTube 公式プレイヤーを使用します。
- 生成した字幕・音声は個人学習・非公開利用を前提としています。
- VOICEVOX 各話者の利用規約を必ず確認してください。
- 公開・商用利用の前に別途権利処理を行ってください。
