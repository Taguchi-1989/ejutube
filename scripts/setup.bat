@echo off
REM ejutube 初回セットアップ — PowerShell 7 ラッパー
REM このファイルをダブルクリックするか、コマンドプロンプトから実行してください。

REM PowerShell 7 (pwsh.exe) を優先し、なければ Windows 組み込みの powershell.exe を使う
where /q pwsh.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PS=pwsh.exe"
) else (
    set "PS=powershell.exe"
)

%PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] セットアップが失敗しました。上のメッセージを確認してください。
    pause
)
