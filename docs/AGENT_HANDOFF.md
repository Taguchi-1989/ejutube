# エージェント引き継ぎドキュメント（Stage 0 -> Stage 1 並行実装）

## プロジェクト概要

ejutube は、YouTube 英語チュートリアル動画に日本語字幕・音声・要約を重ねるローカル学習プレイヤーです。
動画本体はダウンロードせず、YouTube 公式 IFrame Player を使います。

詳細は `youtube_japanese_dubbing_learning_player_requirements.md` を参照してください。

---

## 共有スキーマ（全エージェント共通）

`schemas/` ディレクトリにある JSON Schema (draft-07) が全ステージ間の契約です。
これらのスキーマを変更してはなりません。変更が必要な場合は全エージェントに通知してください。

| ファイル | 役割 |
|--------|------|
| `schemas/metadata.schema.json` | 動画メタデータ（ステータス enum 含む） |
| `schemas/transcript-normalized.schema.json` | 正規化済み字幕アイテム配列 |
| `schemas/chunks.schema.json` | 10〜30 秒チャンク配列（翻訳後フィールド含む） |
| `schemas/narration-segments.schema.json` | TTS 音声長計測結果 |
| `schemas/player.schema.json` | フロントエンドが読み込む再生同期データ |

Pydantic v2 モデルは `pipeline/models.py` にあります。
Python エージェントはここから import してください。他の場所に同等モデルを定義しないでください。

```python
from pipeline.models import Metadata, TranscriptItem, Chunk, NarrationSegment, PlayerJson, PlayerChunk
```

---

## 出力ディレクトリ構造

各動画の成果物は以下のパスに保存します。

```
output/
  {video_id}/
    metadata.json          -- Metadata モデル
    transcript.en.vtt      -- 取得した英語字幕（生ファイル）
    transcript.normalized.json  -- TranscriptItem[] モデル
    transcript.ja.vtt      -- 日本語字幕 VTT（将来）
    chunks.json            -- Chunk[] モデル
    narration.script.md    -- 読み上げ台本（Markdown）
    narration_segments.json -- NarrationSegment[] モデル
    player.json            -- PlayerJson モデル
    summary.md             -- 要約
    glossary.json          -- 動画固有の用語集
    commands.md            -- コマンド抽出
    audio/
      0001.wav
      0002.wav
      ...
```

---

## Stage 1A — パイプライン コア（字幕・チャンク・CLI 実装）

### 担当ディレクトリ

- `pipeline/core/` — 全ての実装をここに書く
- `pipeline/cli.py` — スタブを実際のロジック呼び出しに置き換える

### 触れてはならないディレクトリ

- `web/` (Stage 1B 担当)
- `pipeline/translation/` (Stage 1C 担当)
- `pipeline/tts/` (Stage 1D 担当)
- `pipeline/sync/` (Stage 2 担当)

### タスク

1. `yt-ja fetch-subtitle VIDEO_ID` — 手動 VTT/SRT アップロード受け取り（`--file` オプション）
2. `yt-ja normalize VIDEO_ID` — VTT/SRT -> `transcript.normalized.json`（`TranscriptItem[]`）
3. `yt-ja chunk VIDEO_ID` — `transcript.normalized.json` -> `chunks.json`（`Chunk[]`）、10〜30 秒分割
4. `yt-ja init` — `output/` ディレクトリ確認、`.env` 確認

### テスト用サンプル

`samples/sample.en.vtt` と `samples/sample.metadata.json` を使って開発・テストしてください。

### 参照スキーマ

- `schemas/transcript-normalized.schema.json`
- `schemas/chunks.schema.json`

---

## Stage 1B — フロントエンド（Next.js + YouTube IFrame Player）

### 担当ディレクトリ

- `web/` — Next.js アプリを全てここに構築する

### 触れてはならないディレクトリ

- `pipeline/` (Python パイプライン担当)

### タスク

1. `web/` に Next.js + TypeScript アプリを作成する（`npx create-next-app`）
2. `output/{video_id}/player.json` を読み込む API route または静的読み込みを実装する
3. YouTube IFrame Player API を使った埋め込みプレイヤーを実装する
4. 現在の動画時刻に応じてチャンクをハイライトする字幕パネルを実装する
5. `audio_offset` 補正ボタン（+0.5s / -0.5s）を実装する

### 読み込むデータ形式

`schemas/player.schema.json` の `PlayerJson` 型を TypeScript の型定義として使用してください。

```typescript
// web/src/types/player.ts として作成することを推奨
export interface PlayerChunk {
  chunk_id: number;
  start: number;
  end: number;
  audio: string;  // e.g. "audio/0001.wav"
  subtitle_ja: string;
  narration_ja: string;
  summary: string;
}

export interface PlayerJson {
  video_id: string;
  audio_offset: number;
  chunks: PlayerChunk[];
}
```

### 音声ファイルパス

`audio` フィールドは `output/{video_id}/` からの相対パスです（例: `audio/0001.wav`）。
Next.js の API route または `public/` シンボリックリンクで `output/` を配信してください。

---

## Stage 1C — 翻訳・台本生成（Claude API）

### 担当ディレクトリ

- `pipeline/translation/` — 全ての実装をここに書く

### 触れてはならないディレクトリ

- `web/` (Stage 1B 担当)
- `pipeline/core/` (Stage 1A 担当)
- `pipeline/tts/` (Stage 1D 担当)

### タスク

1. `yt-ja translate VIDEO_ID` — `chunks.json` に `subtitle_ja` を追加する
2. `yt-ja narrate VIDEO_ID` — `chunks.json` に `narration_ja` を追加する
3. `glossary.default.json` を読み込んで翻訳プロンプトに注入する
4. 翻訳エンジンを差し替え可能にする（Claude API / OpenAI / ローカル LLM）

### 入力・出力

- 入力: `output/{video_id}/chunks.json`（`Chunk[]`）
- 出力: `output/{video_id}/chunks.json`（`subtitle_ja`・`narration_ja` を追加した `Chunk[]`）

### 重要な翻訳方針（要件 section 8.6, 8.7, 8.8）

- 技術用語・コマンド・ファイル名は翻訳しない
- `glossary.default.json` の用語を優先する
- `subtitle_ja`（字幕）と `narration_ja`（台本）は別テキストにする
- 台本は短い文に分ける（TTS に渡すため）

---

## Stage 1D — VOICEVOX TTS アダプター

### 担当ディレクトリ

- `pipeline/tts/` — 全ての実装をここに書く

### 触れてはならないディレクトリ

- `web/` (Stage 1B 担当)
- `pipeline/core/` (Stage 1A 担当)
- `pipeline/translation/` (Stage 1C 担当)

### タスク

1. `yt-ja tts VIDEO_ID` — `chunks.json` の `narration_ja` を読み込み VOICEVOX で音声生成
2. 音声を `output/{video_id}/audio/{chunk_id:04d}.wav` に保存する
3. `yt-ja sync VIDEO_ID` — ffprobe で音声長を計測し `narration_segments.json` を生成する

### VOICEVOX API フロー

```
POST /audio_query?text=...&speaker=3
-> audio_query JSON

POST /synthesis?speaker=3
body: audio_query JSON
-> WAV binary
```

エンドポイントは `.env` の `VOICEVOX_ENDPOINT` から読む。
セットアップ手順は `docs/VOICEVOX_SETUP.md` を参照。

### 入力・出力

- 入力: `output/{video_id}/chunks.json`（`narration_ja` が設定済みの `Chunk[]`）
- 出力:
  - `output/{video_id}/audio/0001.wav` ... `audio/NNNN.wav`
  - `output/{video_id}/narration_segments.json`（`NarrationSegment[]`）

### 参照スキーマ

- `schemas/narration-segments.schema.json`

---

## 依存関係グラフ（並行実行時の注意）

```
Stage 1A (core) ──────────────────────────────────────┐
Stage 1B (frontend) ──────────────── player.json 待ち ─┤
Stage 1C (translation) ─── Stage 1A 完了後に実行可能 ──┤
Stage 1D (tts) ─────────── Stage 1C 完了後に実行可能 ──┘
```

Stage 1A〜1D の実装自体は並行できます。
テスト実行は依存順序に注意してください（1A -> 1C -> 1D の順でサンプルデータが完成する）。

---

## 共通開発メモ

- Python 環境: `pip install -e .`（プロジェクトルートで実行）
- CLI 確認: `python -m pipeline.cli --help`
- サンプルデータ: `samples/` ディレクトリを参照
- `.env` は `.env.example` をコピーして作成してください
