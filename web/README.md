# ejutube web

英語YouTubeチュートリアルを日本語字幕・音声で学ぶローカル学習プレイヤー (Next.js フロントエンド)

## 開発起動

```bash
# プロジェクトルート (D:\dev\ejutube) から
npm run dev --workspace=web

# または web/ ディレクトリ内から
npm run dev
```

ブラウザで http://localhost:3000 を開く。

## デモデータで動作確認

`output/DEMO0000000/` にサンプルデータが含まれています。

http://localhost:3000/play/DEMO0000000 を開くとデモプレイヤーが表示されます。

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `OUTPUT_DIR` | `../output` (web/ からの相対パス) | pipeline の出力ディレクトリ |

`.env.local` に設定するか、コマンド実行時に指定してください。

```bash
OUTPUT_DIR=/absolute/path/to/output npm run dev
```

## player.json の読み込み方

`GET /api/videos/{videoId}/player` が `output/{videoId}/player.json` を返します。

スキーマは `schemas/player.schema.json` を参照。TypeScript 型は `lib/types.ts` にあります。

## API routes

| パス | メソッド | 説明 |
|------|---------|------|
| `/api/videos` | GET | 処理済み動画一覧 |
| `/api/videos/{videoId}/player` | GET | player.json を返す |
| `/api/videos/{videoId}/audio/{file}` | GET | WAV 音声ファイルをストリーム |
| `/api/videos/{videoId}/offset` | PATCH | audio_offset を更新・保存 |
| `/api/process` | POST | 処理ジョブ作成 (スタブ) |

## キーボードショートカット (プレイヤー画面)

| キー | 動作 |
|------|------|
| Space | 再生 / 停止 |
| ← | 前のチャンクへ |
| → | 次のチャンクへ |
| [ | 音ズレ補正 -0.1s |
| ] | 音ズレ補正 +0.1s |

## ビルド

```bash
npm run build --workspace=web
```
