@echo off
REM ejutube デイリー起動 — PowerShell 7 ラッパー
REM このファイルをダブルクリックするか、コマンドプロンプトから実行してください。
REM 引数例: start.bat --port 3001

REM PowerShell 7 (pwsh.exe) が必要です。見つからない場合はエラーを表示します。
where /q pwsh.exe 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PowerShell 7 is required for ejutube setup/start scripts.
    echo Install it from: https://aka.ms/powershell
    echo Or via winget:   winget install Microsoft.PowerShell
    echo.
    pause
    exit /b 1
)

pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] 起動に失敗しました。上のメッセージを確認してください。
    pause
)
