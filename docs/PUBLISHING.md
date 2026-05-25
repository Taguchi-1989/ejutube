# Publication checklist

最初の git push 前に確認してください。

1. [ ] `git status` で `output/` 配下や `.env` が未追跡（または .gitignore で無視）になっている
2. [ ] `.env` をコミットしていない（API キー流出防止）
3. [ ] `samples/voice_previews/` がコミットされていない
4. [ ] `LICENSE` / `CREDITS.md` / `README.md` の公開ポリシー節が存在する
5. [ ] `pyproject.toml` の author/email、`web/package.json` の author 等を確認（任意）
6. [ ] GitHub リポジトリの説明欄に「個人学習用、商用利用は権利処理が必要」と明記する
7. [ ] (任意) `git init && git add . && git status` でドライランし、想定外のファイルが含まれていないか目視確認

## 除外されるべきパス（.gitignore 保護済み）

| パス | 理由 |
|---|---|
| `output/` | YouTube 動画の二次的著作物（字幕・音声・要約） |
| `audio/` | 生成 TTS 音声 |
| `*.wav` | 生成 WAV ファイル |
| `*.mp3` | 生成 MP3 ファイル |
| `.env` | API キー |
| `.env.local` / `.env.*.local` | 環境固有の設定 |
| `samples/voice_previews/` | VOICEVOX 音声ライブラリ由来のサンプル音声 |
| `.claude/` | Claude Code ローカル設定 |

## 根拠

要件定義書 §12.5 および §18.4 に基づき、ejutube は生成物の非配布を設計方針としています。
コード・スキーマ・ドキュメント・架空コンテンツのサンプル VTT は公開可能です。
