@echo off
REM ejutube 動画処理ラッパー
REM 使い方: scripts\process.bat "https://www.youtube.com/watch?v=VIDEO_ID"
REM
REM 追加オプションも渡せます:
REM   scripts\process.bat URL --from translate
REM   scripts\process.bat URL --stop-after chunked

if "%~1"=="" (
    echo 使い方: %~nx0 "https://www.youtube.com/watch?v=VIDEO_ID" [オプション]
    echo.
    echo オプション例:
    echo   --from translate       translate ステージから再開
    echo   --stop-after chunked   chunk ステージで停止
    echo   --force-tts            TTS を強制再生成
    echo   --skip-metadata        メタデータ取得をスキップ
    pause
    exit /b 1
)

REM OUTPUT_DIR を明示的に設定してから yt-ja process を実行する
set "PYTHONIOENCODING=utf-8"
set "OUTPUT_DIR=%~dp0..\output"

yt-ja process %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] 処理が失敗しました。上のメッセージを確認してください。
    pause
    exit /b 1
)
