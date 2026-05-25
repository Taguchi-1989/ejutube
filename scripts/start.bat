@echo off
REM ejutube デイリー起動 — PowerShell 7 ラッパー
REM このファイルをダブルクリックするか、コマンドプロンプトから実行してください。
REM 引数例: start.bat --port 3001

REM PowerShell 7 (pwsh.exe) を優先し、なければ Windows 組み込みの powershell.exe を使う
where /q pwsh.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PS=pwsh.exe"
) else (
    set "PS=powershell.exe"
)

%PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] 起動に失敗しました。上のメッセージを確認してください。
    pause
)
