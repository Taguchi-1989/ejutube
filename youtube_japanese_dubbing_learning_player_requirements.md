# YouTube英語チュートリアル日本語化ラッパー 要件定義書

## 1. 背景

Cursor、Claude Code、Codex、Anthropic、OpenAI、Googleなどの公式・準公式チュートリアル動画は、英語圏で先行して公開されることが多い。動画としては情報密度が高く有用だが、日本語話者にとっては、聞き取り・専門用語・画面操作・英語字幕の読解を同時に処理する必要があり、学習コストが高い。

本プロジェクトでは、英語YouTubeチュートリアルを対象に、動画本体を再配布・改変するのではなく、YouTube公式プレイヤーを利用しつつ、日本語字幕・日本語読み上げ音声・要約・用語集・コマンド抽出を重ねる「日本語学習ラッパー」を構築する。

最終的には、ユーザーがYouTube URLを入力すると、エージェント的なパイプラインが字幕取得、翻訳、読み上げ台本化、TTS音声生成、同期データ生成、視聴用ページ生成まで自動で処理する状態を目指す。

## 2. 本プロジェクトで実現したいこと

### 2.1 中心コンセプト

英語公式チュートリアル動画を、日本語話者が理解しやすい形で視聴できるローカル学習環境を作る。

ただし、動画ファイルそのものをダウンロード・保存・再配布するのではなく、YouTube公式プレイヤーを埋め込み表示し、その上に日本語支援レイヤーを重ねる。

### 2.2 目指す体験

ユーザーは、見たい英語チュートリアル動画のURLを入力するだけで、以下の成果物を得られる。

- YouTube公式プレイヤーで再生される元動画
- YouTube側の英語字幕表示
- 自前生成された日本語字幕
- 日本語読み上げ音声
- チャプターごとの要約
- 重要用語集
- コマンド・設定手順の抽出
- 動画時刻に同期した日本語表示
- 必要に応じた音ズレ補正

### 2.3 伝えたい設計思想

この仕組みは「英語動画を日本語動画として作り替える」ものではない。

本質は、英語公式動画をそのまま尊重しながら、日本語話者向けの理解補助レイヤーを追加することである。

そのため、以下を重視する。

- 動画本体を保存しない
- YouTube公式プレイヤーを使う
- 日本語支援データのみ自前生成する
- 個人学習・社内検証・非公開利用を前提にする
- 将来、権利関係をクリアした素材であれば公開版にも転用できる設計にする
- OSS中心で再現性のあるパイプラインにする
- Claude Code / Codex / Cursor などのエージェントに作業を分解して実装させやすい構成にする

## 3. スコープ

## 3.1 対象範囲

対象は、主に以下のような英語動画である。

- Cursor公式チュートリアル
- Claude Code関連チュートリアル
- Anthropic公式動画
- OpenAI公式・開発者向け動画
- Google / Gemini / Firebase / Cloudflare / Vercel などの開発者向け動画
- AIコーディング、エージェント、CLI、開発ツール、SaaS運用に関する英語解説動画

## 3.2 MVPで対応する範囲

MVPでは以下を対象とする。

- 単一のYouTube動画URL
- 英語字幕が存在する動画
- 字幕ベースの日本語翻訳
- VOICEVOXなどOSS系TTSによる日本語音声生成
- 10〜30秒単位のチャンク同期
- ローカルWebアプリでの視聴
- 動画本体は保存しない
- YouTube公式プレイヤーを埋め込む

## 3.3 MVPでは対象外にする範囲

MVPでは以下を対象外にする。

- 動画ファイルのダウンロード
- 動画ファイルへの音声焼き込み
- 公開用の再編集動画生成
- YouTubeへの再アップロード
- 字幕がまったく存在しない動画の完全自動処理
- 複数話プレイリストの一括処理
- 厳密な口パク同期
- 1文ごとの完全同期
- 複数話者の声分け
- 商用公開前提の権利処理

## 4. 非ゴール

本プロジェクトは以下を目的としない。

- 他者の動画を翻訳動画として再配布すること
- YouTube動画をローカル動画ファイルとして保存・蓄積すること
- 公式動画を改変して別コンテンツとして公開すること
- 完全な同時通訳品質を目指すこと
- 声優品質の自然音声を最初から目指すこと
- すべてのYouTube動画を対象にすること

## 5. 想定ユーザー

## 5.1 主ユーザー

- 英語の開発者向けチュートリアルを追いたい日本語話者
- Cursor / Claude Code / Codex / Gemini CLI / AIエージェント開発に関心があるユーザー
- 英語動画の内容は知りたいが、聞き取りに負荷を感じるユーザー
- OSS・CLI・ローカル処理に慣れているユーザー
- 自分用の学習データベースを構築したいユーザー

## 5.2 想定利用場面

- 英語公式チュートリアルのキャッチアップ
- AIコーディングツールの使い方学習
- 新機能発表動画の理解
- 自分用の調査メモ作成
- 後から検索できる学習ログ化
- Claude Code / Codexに実装させる前の教材理解

## 6. 基本方針

## 6.1 動画本体は保存しない

本システムでは、YouTube動画本体をダウンロード・保存・再エンコードしない。

動画はYouTube公式プレイヤーで再生する。

保存するのは、以下の自前生成データのみとする。

- 字幕テキスト
- 日本語翻訳
- 読み上げ台本
- 日本語TTS音声
- 要約
- 用語集
- コマンド一覧
- 同期メタデータ

## 6.2 英語字幕はYouTube側表示を優先

視聴画面では、YouTube公式プレイヤーの英語字幕表示を使えるようにする。

自前の英語字幕データは、翻訳・要約・TTS生成のための内部処理用として扱う。

## 6.3 日本語化は「字幕翻訳」と「読み上げ台本」を分ける

日本語字幕と日本語読み上げ音声は、同じテキストにしない。

- 日本語字幕：原文に比較的忠実な訳
- 読み上げ台本：聞いて理解しやすい自然な日本語

たとえば、英語1文をそのまま訳すのではなく、日本語音声では文を短く区切る。

## 6.4 厳密同期より実用同期を優先

字幕1行ごとの完全同期は、初期段階では目指さない。

日本語音声は英語音声より長くなることが多いため、10〜30秒単位のチャンク同期を基本とする。

## 6.5 OSS優先

可能な限りOSSで構成する。

ただし、翻訳品質や速度が不足する場合は、OpenAI、Claude、GeminiなどのAPIを差し替え可能にする。

## 7. 全体アーキテクチャ

## 7.1 概要

```text
YouTube URL
  ↓
Video ID抽出
  ↓
字幕取得
  ↓
字幕正規化
  ↓
チャンク分割
  ↓
日本語字幕生成
  ↓
読み上げ台本生成
  ↓
TTS音声生成
  ↓
音声長計測
  ↓
同期JSON生成
  ↓
ローカルWebプレイヤーで視聴
```

## 7.2 コンポーネント

### フロントエンド

- Next.js
- TypeScript
- React
- YouTube IFrame Player API
- ローカルファイルまたはAPI経由でplayer.jsonを読み込む

### バックエンド / パイプライン

- PythonまたはNode.js
- 字幕取得
- VTT/SRTパース
- チャンク生成
- 翻訳
- 読み上げ台本生成
- TTS生成
- ffmpegによる音声長計測・結合補助

### TTS

- 初期候補：VOICEVOX Engine
- 代替候補：AivisSpeech、COEIROINK、OpenAI TTS、ElevenLabs

### ストレージ

- ローカルファイルシステム
- 将来：SQLite / PostgreSQL / Supabase

## 8. 機能要件

## 8.1 URL入力機能

### 要件

ユーザーはYouTube URLを入力できる。

### 入力例

```text
https://www.youtube.com/watch?v=xxxxxxxxxxx
https://youtu.be/xxxxxxxxxxx
```

### 処理

- URLからvideo_idを抽出する
- 既に処理済みのvideo_idであれば既存成果物を表示する
- 未処理であればジョブを作成する

## 8.2 メタデータ取得機能

### 要件

動画の基本情報を取得する。

### 取得項目

- video_id
- title
- channel_name
- duration
- original_url
- created_at
- processing_status

## 8.3 字幕取得機能

### 要件

英語字幕を取得する。

### 優先順位

1. 手動アップロードされたVTT/SRT
2. 通常の英語字幕
3. 英語自動字幕
4. 字幕なしとして処理停止

### 注意

YouTube公式APIで他者動画の字幕を取得することは制限があるため、実装時は利用規約・運用範囲を確認する。

ローカル個人利用の検証では、字幕取得ツールを利用する構成も検討するが、公開サービス化する場合は設計を変更する。

## 8.4 字幕正規化機能

### 要件

取得した字幕を内部形式に変換する。

### 入力

- VTT
- SRT

### 出力

```json
[
  {
    "id": 1,
    "start": 12.3,
    "end": 16.8,
    "text_en": "Let's connect Cursor with Claude Code."
  }
]
```

### 処理

- タイムスタンプを秒数に変換
- 空行・重複字幕の除去
- 極端に短い字幕の統合
- 長すぎる字幕の分割
- ノイズ文字の除去

## 8.5 チャンク分割機能

### 要件

字幕を10〜30秒程度の処理単位に分割する。

### 分割基準

- 時間長
- 文の切れ目
- 話題の切れ目
- コマンド実行や画面遷移の区切り

### 出力例

```json
[
  {
    "chunk_id": 1,
    "start": 0.0,
    "end": 28.5,
    "items": [1, 2, 3, 4],
    "text_en": "..."
  }
]
```

## 8.6 日本語字幕生成機能

### 要件

英語字幕から日本語字幕を生成する。

### 方針

- 原文の意味を保つ
- 技術用語は無理に日本語化しない
- UI名、コマンド、ライブラリ名は原則として保持する
- 長すぎる字幕は短く分ける

### 出力例

```json
{
  "chunk_id": 1,
  "subtitle_ja": "ここでは、CursorをClaude Codeと連携させます。"
}
```

## 8.7 読み上げ台本生成機能

### 要件

日本語字幕とは別に、音声で聞きやすい日本語台本を生成する。

### 方針

- 1文を短くする
- 音声で聞いて分かるように補助語を入れる
- 画面操作は明示する
- 不自然な直訳を避ける
- ただし、勝手な解釈や情報追加はしない

### 例

英語原文：

```text
Now let's open Cursor and connect it with Claude Code.
```

日本語字幕：

```text
それではCursorを開き、Claude Codeと接続しましょう。
```

読み上げ台本：

```text
では、ここでCursorを開きます。次に、Claude Codeと連携させます。
```

## 8.8 用語統一機能

### 要件

技術用語の訳を統一する。

### 用語辞書例

```json
{
  "Cursor": "Cursor",
  "Claude Code": "Claude Code",
  "agent": "エージェント",
  "repository": "リポジトリ",
  "pull request": "プルリクエスト",
  "terminal": "ターミナル",
  "prompt": "プロンプト"
}
```

### 方針

- プロダクト名は原則そのまま
- CLIコマンドは訳さない
- ファイル名・パス名は訳さない
- 初出時だけ補足説明を付ける

## 8.9 TTS音声生成機能

### 要件

読み上げ台本から日本語音声を生成する。

### 初期TTS

- VOICEVOX Engine

### 入力

```json
{
  "chunk_id": 1,
  "text": "では、ここでCursorを開きます。次に、Claude Codeと連携させます。",
  "speaker": 3,
  "speed_scale": 1.1
}
```

### 出力

```text
audio/0001.wav
```

### 調整項目

- 話速
- 音量
- 話者
- 無音区間
- 文末ポーズ

## 8.10 音声長計測機能

### 要件

生成されたTTS音声の長さを計測する。

### 目的

- 元チャンク時間との差分を把握する
- 音ズレ補正に使う
- 長すぎる台本を検出する

### 出力例

```json
{
  "chunk_id": 1,
  "video_start": 0.0,
  "video_end": 28.5,
  "target_duration": 28.5,
  "audio_duration": 31.2,
  "duration_diff": 2.7
}
```

## 8.11 同期JSON生成機能

### 要件

プレイヤーが読み込む同期データを生成する。

### 出力例

```json
{
  "video_id": "xxxxxxxxxxx",
  "title": "Example Tutorial",
  "chunks": [
    {
      "chunk_id": 1,
      "start": 0.0,
      "end": 28.5,
      "audio_file": "audio/0001.wav",
      "subtitle_ja": "...",
      "narration_text": "...",
      "summary": "..."
    }
  ]
}
```

## 8.12 Webプレイヤー機能

### 要件

YouTube動画と日本語音声を同期して再生できる。

### 画面構成

```text
┌──────────────────────────────┬──────────────────────────────┐
│ YouTube公式プレイヤー          │ 日本語支援パネル                │
│ 英語字幕ON                    │ 現在の日本語字幕                │
│ ミュート再生                   │ 読み上げテキスト                │
│                              │ 用語メモ                        │
├──────────────────────────────┴──────────────────────────────┤
│ チャプター / コマンド一覧 / 要約 / 原文字幕                   │
└──────────────────────────────────────────────────────────────┘
```

### 再生挙動

- YouTube動画を再生する
- YouTube音声はミュートまたは低音量にする
- 日本語TTS音声を同期再生する
- 現在時刻に応じて字幕をハイライトする
- 一時停止時は日本語音声も停止する
- シーク時は該当チャンクから再開する

## 8.13 音ズレ補正機能

### 要件

ユーザーが手動で音ズレを補正できる。

### UI

- 日本語音声を0.5秒早める
- 日本語音声を0.5秒遅らせる
- 現在の補正値を保存する

### 保存例

```json
{
  "global_audio_offset": -0.8
}
```

## 8.14 要約生成機能

### 要件

チャンクごと、および動画全体の要約を生成する。

### 出力

- 30秒ごとの要点
- 章ごとの要約
- 動画全体の200字要約
- 実装で試すべきポイント
- 注意点

## 8.15 コマンド抽出機能

### 要件

動画内で言及されたコマンド、ファイル名、設定値を抽出する。

### 出力例

```md
# Commands

```bash
npm install
npm run dev
```

# Files

- package.json
- .env.local
- src/app/page.tsx
```

### 方針

- コマンドは原文保持
- 推測で存在しないコマンドを作らない
- 不明な場合は「動画内で明示されていない」と記録する

## 9. データ構造

## 9.1 ディレクトリ構成

```text
output/
  {video_id}/
    metadata.json
    transcript.en.vtt
    transcript.normalized.json
    transcript.ja.vtt
    chunks.json
    narration.script.md
    narration_segments.json
    player.json
    summary.md
    glossary.json
    commands.md
    audio/
      0001.wav
      0002.wav
```

## 9.2 metadata.json

```json
{
  "video_id": "xxxxxxxxxxx",
  "url": "https://www.youtube.com/watch?v=xxxxxxxxxxx",
  "title": "Example Tutorial",
  "channel": "Example Channel",
  "duration": 1234.5,
  "created_at": "2026-05-25T00:00:00+09:00",
  "status": "completed"
}
```

## 9.3 chunks.json

```json
[
  {
    "chunk_id": 1,
    "start": 0.0,
    "end": 28.5,
    "text_en": "...",
    "subtitle_ja": "...",
    "narration_ja": "..."
  }
]
```

## 9.4 player.json

```json
{
  "video_id": "xxxxxxxxxxx",
  "audio_offset": 0,
  "chunks": [
    {
      "chunk_id": 1,
      "start": 0.0,
      "end": 28.5,
      "audio": "audio/0001.wav",
      "subtitle_ja": "...",
      "narration_ja": "...",
      "summary": "..."
    }
  ]
}
```

## 10. パイプライン設計

## 10.1 ジョブ状態

```text
created
  ↓
metadata_loaded
  ↓
subtitle_fetched
  ↓
subtitle_normalized
  ↓
chunked
  ↓
translated
  ↓
narration_script_created
  ↓
tts_generated
  ↓
sync_generated
  ↓
completed
```

## 10.2 エラー状態

```text
failed_no_subtitle
failed_translation
failed_tts
failed_sync
failed_unknown
```

## 10.3 再実行可能性

各ステップは中間成果物を保存し、失敗時に途中から再実行できるようにする。

例：

- 字幕取得済みなら翻訳から再開
- 翻訳済みならTTS生成から再開
- TTS生成済みなら同期JSON生成から再開

## 11. 品質要件

## 11.1 翻訳品質

- 技術用語を崩さない
- 勝手な補足をしない
- 原文の手順順序を保つ
- 画面操作やコマンドを誤訳しない
- 読み上げ台本は自然な日本語にする

## 11.2 音声品質

- 聞き取りやすい話速
- 極端な機械音声感は許容するが、理解を妨げないこと
- 文末で適度なポーズを入れる
- 長すぎる台本は短縮する

## 11.3 同期品質

- チャンク単位で概ね対応していればよい
- 1〜3秒程度のズレは許容する
- 大きなズレは手動補正可能にする
- シーク時に破綻しないこと

## 11.4 操作性

- URL入力から処理開始できる
- 処理状況が分かる
- 完了後すぐ再生できる
- 失敗理由が分かる
- 再処理できる

## 12. 非機能要件

## 12.1 ローカル優先

初期版はローカルPCで動くことを優先する。

### 想定環境

- Windows + WSL
- Linux
- macOS

## 12.2 再現性

- CLIで実行できる
- configファイルで設定できる
- 依存関係をREADMEに明記する
- Docker化できる構成にする

## 12.3 拡張性

以下を差し替え可能にする。

- 字幕取得方式
- 翻訳エンジン
- TTSエンジン
- チャンク分割ロジック
- プレイヤーUI
- ストレージ

## 12.4 セキュリティ

- APIキーは.envで管理する
- 生成データはローカル保存を基本にする
- 外部公開しない
- 公開モードを作る場合は認証を必須にする

## 12.5 法務・規約配慮

- 動画本体を保存しない
- YouTube公式プレイヤーを使う
- 公開・共有を前提にしない
- TTS音声や字幕を第三者に配布しない
- OSSライセンスと音声ライブラリの利用条件を確認する
- 公開サービス化する場合は別途権利処理を行う

## 13. 推奨技術スタック

## 13.1 MVP構成

```text
Frontend:
  Next.js
  TypeScript
  React
  YouTube IFrame Player API

Pipeline:
  Python
  ffmpeg
  webvtt-py or pysubs2
  yt-dlp or manual subtitle upload

TTS:
  VOICEVOX Engine

Storage:
  Local filesystem

Job management:
  simple JSON status file
```

## 13.2 将来構成

```text
Frontend:
  Next.js
  TypeScript
  Tailwind CSS
  shadcn/ui

Backend:
  FastAPI or Next.js API routes

Queue:
  Celery / BullMQ / simple worker

DB:
  SQLite → PostgreSQL

Storage:
  Local filesystem → S3互換ストレージ

Translation:
  local LLM / OpenAI / Claude / Gemini

TTS:
  VOICEVOX / AivisSpeech / OpenAI TTS / ElevenLabs
```

## 14. CLI仕様案

## 14.1 基本コマンド

```bash
yt-ja init
yt-ja process "https://www.youtube.com/watch?v=xxxxxxxxxxx"
yt-ja serve
```

## 14.2 ステップ別実行

```bash
yt-ja fetch-subtitle VIDEO_ID
yt-ja normalize VIDEO_ID
yt-ja translate VIDEO_ID
yt-ja narrate VIDEO_ID
yt-ja tts VIDEO_ID
yt-ja sync VIDEO_ID
yt-ja build-player VIDEO_ID
```

## 14.3 再実行

```bash
yt-ja process VIDEO_ID --from translate
yt-ja process VIDEO_ID --force-tts
yt-ja process VIDEO_ID --force-sync
```

## 14.4 設定ファイル

```yaml
subtitle:
  preferred_language: en
  allow_auto_subtitle: true
  allow_manual_upload: true

translation:
  engine: local
  glossary_path: glossary.default.json

narration:
  style: technical_explainer
  max_chunk_seconds: 30

voicevox:
  endpoint: http://127.0.0.1:50021
  speaker: 3
  speed_scale: 1.1

player:
  default_mute_youtube: true
  default_caption_lang: en
  audio_offset: 0
```

## 15. UI要件

## 15.1 トップ画面

### 要素

- YouTube URL入力欄
- 処理開始ボタン
- 既存処理済み動画一覧
- 処理状況一覧

## 15.2 処理状況画面

### 表示項目

- 動画タイトル
- 現在ステップ
- 完了ステップ
- エラー内容
- 再実行ボタン

## 15.3 プレイヤー画面

### 要素

- YouTube埋め込みプレイヤー
- 日本語字幕表示
- 読み上げテキスト表示
- チャンク一覧
- 要約
- コマンド一覧
- 用語集
- 音ズレ補正ボタン

## 15.4 プレイヤー操作

- 再生
- 停止
- シーク
- 次チャンクへ移動
- 前チャンクへ移動
- 日本語音声ON/OFF
- YouTube音声ON/OFF
- 英語字幕表示ON/OFF

## 16. エージェント実装単位

Claude Code / Codex / Cursor などのエージェントに投げる場合、以下の単位に分ける。

## 16.1 タスク1：プロジェクト雛形

- Next.jsアプリを作成
- Python pipelineディレクトリを作成
- outputディレクトリ構成を作成
- READMEを作成

## 16.2 タスク2：URL解析とメタデータ保存

- YouTube URLからvideo_idを抽出
- metadata.jsonを生成
- 処理済み動画一覧を表示

## 16.3 タスク3：字幕取り込み

- 手動VTT/SRTアップロード対応
- 必要に応じて字幕取得ツール対応
- transcript.en.vttを保存

## 16.4 タスク4：字幕正規化

- VTT/SRTをJSON化
- start/end秒数に変換
- ノイズ除去

## 16.5 タスク5：チャンク分割

- 10〜30秒単位に分割
- chunks.jsonを生成

## 16.6 タスク6：翻訳・読み上げ台本生成

- 日本語字幕生成
- 読み上げ台本生成
- 用語辞書適用

## 16.7 タスク7：VOICEVOX連携

- VOICEVOX Engineに接続
- audio_query生成
- synthesis実行
- wav保存

## 16.8 タスク8：同期JSON生成

- 音声長を測定
- player.jsonを生成
- 音ズレ補正値を保存可能にする

## 16.9 タスク9：Webプレイヤー

- YouTube IFrame Player API連携
- 日本語音声同期
- 字幕ハイライト
- シーク対応

## 16.10 タスク10：要約・コマンド抽出

- summary.md生成
- commands.md生成
- glossary.json生成

## 17. 受け入れ基準

## 17.1 MVP完了条件

以下を満たせばMVP完了とする。

- YouTube URLを登録できる
- 手動または自動で英語字幕を取り込める
- 字幕をJSONに正規化できる
- 10〜30秒チャンクに分割できる
- 日本語字幕を生成できる
- 読み上げ台本を生成できる
- VOICEVOXで日本語音声を生成できる
- player.jsonを生成できる
- YouTube埋め込み動画と日本語音声を同期再生できる
- 英語字幕はYouTubeプレイヤー側で表示できる
- シーク時に大きく破綻しない
- 音ズレを手動補正できる

## 17.2 品質確認項目

- 動画本体が保存されていないこと
- 日本語音声だけが保存されていること
- 字幕と音声が概ね対応していること
- 技術用語が崩れていないこと
- コマンドが誤って翻訳されていないこと
- 処理失敗時に原因が分かること

## 18. リスクと対策

## 18.1 字幕が取得できない

### リスク

動画によっては英語字幕がない。

### 対策

- 手動VTT/SRTアップロードを用意する
- 将来、Whisper系音声認識を追加する
- 字幕なしの場合は明確に失敗させる

## 18.2 日本語音声が長すぎる

### リスク

日本語TTSが元動画区間より長くなり、音ズレする。

### 対策

- 読み上げ台本を短縮する
- 話速を上げる
- 30秒チャンク同期にする
- 音ズレ補正を用意する

## 18.3 誤訳

### リスク

専門用語やコマンドを誤訳する。

### 対策

- 用語辞書を使う
- コマンドやファイル名は翻訳しない
- 翻訳後に検証ステップを入れる

## 18.4 規約・権利リスク

### リスク

動画・字幕・音声の扱いによっては利用規約や著作権上の問題が生じる。

### 対策

- 動画本体を保存しない
- YouTube公式プレイヤーを使う
- 公開しない
- 生成物を配布しない
- 公開版は権利処理済み素材のみ対象にする

## 18.5 TTSライセンス

### リスク

音声ライブラリごとに利用条件が異なる。

### 対策

- 各音声の利用規約を確認する
- クレジット表記を保存する
- 公開前提では別途確認する

## 19. 将来拡張

## 19.1 プレイリスト一括処理

YouTubeプレイリストURLを入力すると、複数動画を順番に処理する。

## 19.2 Whisper対応

字幕がない動画に対して、音声認識で英語文字起こしを生成する。

## 19.3 複数TTS対応

- VOICEVOX
- AivisSpeech
- OpenAI TTS
- ElevenLabs

を切り替え可能にする。

## 19.4 自動品質チェック

- 翻訳漏れ検出
- コマンド誤訳検出
- 長すぎる読み上げ台本検出
- 音声長差分検出

## 19.5 学習データベース化

処理済み動画から以下を検索できるようにする。

- コマンド
- 用語
- 要約
- プロダクト名
- チュートリアル手順

## 19.6 社内学習用モード

権利上問題ない社内動画や自作動画を対象に、完全な吹き替え動画生成も可能にする。

この場合は、動画ファイルの再エンコードも許可する別モードとして設計する。

## 20. 実装時の優先順位

## Phase 1：字幕・要約MVP

- URL登録
- 字幕取り込み
- 字幕正規化
- 日本語翻訳
- 要約生成
- Markdown出力

## Phase 2：TTS生成

- 読み上げ台本生成
- VOICEVOX連携
- 音声生成
- 音声長計測

## Phase 3：同期プレイヤー

- YouTube IFrame Player API連携
- 日本語音声同期
- 字幕ハイライト
- 音ズレ補正

## Phase 4：エージェント化

- URL投入から完了まで自動化
- ステップ別再実行
- エラー復帰
- 処理状況UI

## Phase 5：プレイリスト・学習DB化

- プレイリスト一括処理
- 検索
- タグ管理
- コマンド集約

## 21. エージェントに渡す初回プロンプト案

```md
You are implementing a local learning player for English YouTube developer tutorials.

Goal:
Build a local web app and pipeline that takes a YouTube URL, imports or fetches English subtitles, translates them into Japanese, creates Japanese narration scripts, generates TTS audio, and plays the original YouTube video through the official embedded player while synchronizing the generated Japanese audio and subtitles.

Important constraints:
- Do not download or store the video file.
- Use the official YouTube embedded player for video playback.
- Store only generated learning assets: Japanese subtitles, narration scripts, TTS audio, summaries, glossary, commands, and sync metadata.
- MVP should work locally.
- Prefer OSS tools.
- Use chunk-level synchronization, not sentence-perfect dubbing.

Initial stack:
- Next.js + TypeScript for UI
- Python for pipeline scripts
- VOICEVOX Engine for Japanese TTS
- ffmpeg for audio duration inspection
- VTT/SRT parser for subtitles
- Local filesystem for outputs

First implementation target:
1. Create project structure.
2. Implement URL registration and video_id extraction.
3. Implement manual VTT/SRT subtitle import.
4. Normalize subtitles into JSON.
5. Split subtitles into 10-30 second chunks.
6. Generate placeholder Japanese subtitle/narration fields.
7. Generate player.json.
8. Build a basic YouTube embedded player page that loads player.json and displays the current chunk.

Do not implement video downloading.
Do not implement public sharing.
```

## 22. 最初に作るべき最小プロトタイプ

最初は翻訳やTTSを完全実装しなくてもよい。

最小プロトタイプでは、以下だけを実現する。

1. YouTube URLを入力する
2. video_idを抽出する
3. 手動でVTTを入れる
4. VTTをJSON化する
5. 30秒チャンクに分ける
6. ダミー日本語テキストを入れる
7. YouTubeプレイヤーを表示する
8. 再生時間に応じて現在チャンクをハイライトする

これができれば、後から翻訳・TTS・要約を差し込める。

## 23. 判断

このプロジェクトは技術的には十分実現可能である。

最も重要なのは、動画を日本語動画として作り替えるのではなく、YouTube公式動画を日本語学習UIで包む設計にすることである。

その設計であれば、以下の利点がある。

- 権利リスクを抑えやすい
- 実装が軽い
- ローカル運用しやすい
- エージェントに分解して実装させやすい
- 将来、学習データベース化しやすい
- Cursor / Claude Code / Codex などの英語チュートリアル追跡と相性がよい

MVPでは、まず「字幕ベースの日本語学習プレイヤー」を作り、その後に「日本語TTS同期」を追加するのが最も堅実である。

