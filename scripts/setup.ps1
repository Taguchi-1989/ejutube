#Requires -Version 7.0
<#
.SYNOPSIS
    ejutube 初回セットアップスクリプト（Windows / PowerShell 7+）

.DESCRIPTION
    必要なランタイム・依存関係を確認し、Python/Node パッケージをインストールし、
    スモークテストを実行します。各ステップは冪等（何度でも安全に再実行可能）です。
    詳細なフローは scripts\FLOW.md を参照してください。

.EXAMPLE
    .\scripts\setup.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# スクリプト自身の場所からリポジトリルートを解決する
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# ---------------------------------------------------------------------------
# ユーティリティ関数
# ---------------------------------------------------------------------------

function Write-Step { param([string]$Msg)
    Write-Host ""
    Write-Host "==> $Msg" -ForegroundColor White
}
function Write-OK   { param([string]$Msg); Write-Host "  [OK]   $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg); Write-Host "  [WARN] $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg); Write-Host "  [ERROR] $Msg" -ForegroundColor Red }
function Write-Info { param([string]$Msg); Write-Host "  [INFO] $Msg" -ForegroundColor Cyan }

# HTTPポートが応答するか確認する（Test-NetConnection の代替 — HTTP レベルで確認）
function Test-HttpPort {
    param([int]$Port, [int]$TimeoutMs = 2000)
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$Port/")
        $req.Timeout   = $TimeoutMs
        $req.Method    = 'GET'
        $resp = $req.GetResponse()
        $resp.Close()
        return $true
    } catch [System.Net.WebException] {
        # HTTP エラー（4xx/5xx）でもポートは開いている
        if ($_.Exception.Response) { return $true }
        # Connection refused / actively refused
        $msg = $_.Exception.Message
        if ($msg -match 'refused|reset|actively refused|No connection could be made') { return $false }
        return $false
    } catch {
        return $false
    }
}

# バージョン文字列を [int, int, int] に変換する
function Parse-Version {
    param([string]$Raw)
    $clean = ($Raw -replace '^[^0-9]*', '') -replace '\s.*$', ''
    $parts = $clean.Split('.')
    return [int[]]@(
        (($parts.Count -gt 0) ? [int]$parts[0] : 0),
        (($parts.Count -gt 1) ? [int]$parts[1] : 0),
        (($parts.Count -gt 2) ? [int]$parts[2] : 0)
    )
}

# $Got >= $Min かどうか確認する
function Test-MinVersion {
    param([int[]]$Got, [int[]]$Min)
    for ($i = 0; $i -lt $Min.Count; $i++) {
        if ($Got[$i] -gt $Min[$i]) { return $true }
        if ($Got[$i] -lt $Min[$i]) { return $false }
    }
    return $true
}

# ---------------------------------------------------------------------------
# ステップ 1: Python 3.11+
# ---------------------------------------------------------------------------
function Step-1-Python {
    Write-Step "[1/10] Python 3.11+ を確認"

    $pythonExe = $null
    foreach ($candidate in @('python', 'python3')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            $raw = & $cmd.Source --version 2>&1
            $ver = Parse-Version ($raw -replace 'Python ', '')
            if (Test-MinVersion -Got $ver -Min @(3, 11)) {
                Write-OK "Python $($ver[0]).$($ver[1]).$($ver[2]) ($($cmd.Source))"
                $script:PythonExe = $cmd.Source
                $LASTEXITCODE = 0
                return
            } else {
                Write-Warn "Python $($ver[0]).$($ver[1]) が見つかりましたが 3.11 以上が必要です"
            }
        } catch { }
    }

    Write-Err "Python 3.11 以上が見つかりません。"
    Write-Info "インストール: https://www.python.org/downloads/"
    Write-Info "インストール時に 'Add Python to PATH' にチェックを入れてください。"
    exit 1
}

# ---------------------------------------------------------------------------
# ステップ 2: Node.js 18+
# ---------------------------------------------------------------------------
function Step-2-Node {
    Write-Step "[2/10] Node.js 18+ を確認"

    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Err "Node.js が見つかりません。"
        Write-Info "インストール: https://nodejs.org/"
        exit 1
    }
    $raw = & node --version 2>&1
    $ver = Parse-Version $raw
    if (-not (Test-MinVersion -Got $ver -Min @(18, 0))) {
        Write-Err "Node.js $($ver[0]) が見つかりましたが、18 以上が必要です。"
        Write-Info "アップグレード: https://nodejs.org/"
        exit 1
    }
    Write-OK "Node.js $($ver[0]).$($ver[1]).$($ver[2])"
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 3: ffmpeg（非致命的）
# ---------------------------------------------------------------------------
function Step-3-FFmpeg {
    Write-Step "[3/10] ffmpeg を確認"

    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Warn "ffmpeg が見つかりません。TTS 音声生成（ffprobe）が使えません。"
        Write-Info "インストール方法:"
        Write-Info "  winget install Gyan.FFmpeg"
        Write-Info "  または scoop install ffmpeg"
        Write-Info "インストール後に新しいターミナルを開いてください。"
    } else {
        Write-OK "ffmpeg ($($cmd.Source))"
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 4: Ollama（必須）
# ---------------------------------------------------------------------------
function Step-4-Ollama {
    Write-Step "[4/10] Ollama を確認"

    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Err "Ollama が見つかりません。"
        Write-Info "インストール: https://ollama.com/download"
        Write-Info "インストール後にターミナルを再起動し、setup.ps1 を再実行してください。"
        exit 1
    }
    Write-OK "ollama ($($cmd.Source))"

    Write-Info ":11434 で Ollama が応答するか確認中..."
    if (Test-HttpPort -Port 11434) {
        Write-OK "Ollama は :11434 で稼働中"
    } else {
        Write-Info "Ollama がまだ起動していません。バックグラウンドで起動を試みます..."
        Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden -ErrorAction SilentlyContinue
        Write-Info "10秒待機中..."
        Start-Sleep -Seconds 10
        if (Test-HttpPort -Port 11434) {
            Write-OK "Ollama が :11434 で起動しました"
        } else {
            Write-Warn "Ollama が :11434 で応答しません。"
            Write-Info "手動起動: 別のターミナルで `ollama serve` を実行してください。"
        }
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 5: gemma4:e4b モデル
# ---------------------------------------------------------------------------
function Step-5-OllamaModel {
    Write-Step "[5/10] Ollama モデル gemma4:e4b を確認"

    try {
        $listOutput = & ollama list 2>&1
        if ($listOutput -match 'gemma4:e4b') {
            Write-OK "gemma4:e4b はすでにダウンロード済みです"
        } else {
            Write-Info "gemma4:e4b をダウンロードします（約 5 GB — しばらくかかります）..."
            & ollama pull gemma4:e4b
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "ollama pull gemma4:e4b が失敗しました。"
                Write-Info "Ollama が起動しているか確認して手動実行: ollama pull gemma4:e4b"
            } else {
                Write-OK "gemma4:e4b のダウンロード完了"
            }
        }
    } catch {
        Write-Warn "ollama list の実行に失敗しました: $_"
        Write-Info "Ollama が起動してから手動実行: ollama pull gemma4:e4b"
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 6: VOICEVOX Engine（非致命的）
# ---------------------------------------------------------------------------
function Step-6-VOICEVOX {
    Write-Step "[6/10] VOICEVOX Engine (:50021) を確認"

    if (Test-HttpPort -Port 50021) {
        Write-OK "VOICEVOX は :50021 で稼働中"
    } else {
        Write-Warn "VOICEVOX が :50021 で応答しません。"
        Write-Info "TTS（音声合成）機能を使うには VOICEVOX Engine が必要です。"
        Write-Info "ダウンロード: https://voicevox.hiroshiba.jp/"
        Write-Info "セットアップ手順: docs\VOICEVOX_SETUP.md"
        Write-Info "（VOICEVOX なしでも字幕翻訳機能は動作します）"
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 7: .env ファイル
# ---------------------------------------------------------------------------
function Step-7-EnvFile {
    Write-Step "[7/10] .env ファイルを確認"

    $envPath     = Join-Path $ProjectDir '.env'
    $examplePath = Join-Path $ProjectDir '.env.example'

    if (Test-Path $envPath) {
        Write-OK ".env はすでに存在します（スキップ）"
    } elseif (Test-Path $examplePath) {
        Copy-Item $examplePath $envPath
        Write-OK ".env.example から .env を作成しました"
        Write-Info "Anthropic API を使う場合は .env の ANTHROPIC_API_KEY を設定してください。"
    } else {
        Write-Warn ".env.example が見つかりません。.env を手動で作成してください。"
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 8: pip install -e .
# ---------------------------------------------------------------------------
function Step-8-PipInstall {
    Write-Step "[8/10] Python 依存関係をインストール (pip install -e .)"

    Push-Location $ProjectDir
    try {
        & $script:PythonExe -m pip install -e . --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Err "pip install -e . が失敗しました。"
            Write-Info "手動実行: cd `"$ProjectDir`" && pip install -e ."
            exit 1
        }
        Write-OK "Python パッケージのインストール完了"
    } finally {
        Pop-Location
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 9: npm install（web/）
# ---------------------------------------------------------------------------
function Step-9-NpmInstall {
    Write-Step "[9/10] Node.js 依存関係をインストール (npm install)"

    $webDir = Join-Path $ProjectDir 'web'
    if (-not (Test-Path $webDir)) {
        Write-Warn "web/ ディレクトリが見つかりません。フロントエンドのインストールをスキップします。"
        $LASTEXITCODE = 0
        return
    }

    Push-Location $webDir
    try {
        & npm install --silent 2>&1 | Where-Object { $_ -notmatch '^npm warn' } |
            ForEach-Object { Write-Host "  $_" }
        if ($LASTEXITCODE -ne 0) {
            Write-Err "npm install が失敗しました。"
            Write-Info "手動実行: cd `"$webDir`" && npm install"
            exit 1
        }
        Write-OK "Node.js パッケージのインストール完了"
    } finally {
        Pop-Location
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# ステップ 10: pytest スモークテスト
# ---------------------------------------------------------------------------
function Step-10-Pytest {
    Write-Step "[10/10] スモークテスト実行 (pytest tests/ -q)"

    Push-Location $ProjectDir
    try {
        $output   = & $script:PythonExe -m pytest tests/ -q 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Write-Err "pytest が失敗しました。セットアップに問題があります。"
            Write-Host ""
            $output | ForEach-Object { Write-Host "    $_" }
            Write-Host ""
            Write-Info "pip install -e .[dev] を実行してから再試行してください。"
            exit 1
        }
        $summary = ($output | Where-Object { $_ -match 'passed|failed|error' } | Select-Object -Last 1) ?? '（サマリなし）'
        Write-OK "pytest 完了: $summary"
    } finally {
        Pop-Location
    }
    $LASTEXITCODE = 0
}

# ---------------------------------------------------------------------------
# 完了バナー
# ---------------------------------------------------------------------------
function Show-Banner {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  ejutube セットアップ完了！" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  次のステップ:" -ForegroundColor Cyan
    Write-Host "    1. VOICEVOX Engine を起動（まだの場合）"
    Write-Host "       詳細: docs\VOICEVOX_SETUP.md"
    Write-Host ""
    Write-Host "    2. サーバーを起動:"
    Write-Host "       scripts\start.bat"
    Write-Host ""
    Write-Host "    3. 動画を処理:"
    Write-Host '       scripts\process.bat "https://www.youtube.com/watch?v=VIDEO_ID"'
    Write-Host ""
    Write-Host "  フロー詳細: scripts\FLOW.md"
    Write-Host ""
}

# ---------------------------------------------------------------------------
# メイン実行
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ejutube セットアップ開始" -ForegroundColor Cyan
Write-Host "  リポジトリ: $ProjectDir" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$script:PythonExe = 'python'  # Step-1 で上書きされる

Step-1-Python
Step-2-Node
Step-3-FFmpeg
Step-4-Ollama
Step-5-OllamaModel
Step-6-VOICEVOX
Step-7-EnvFile
Step-8-PipInstall
Step-9-NpmInstall
Step-10-Pytest
Show-Banner
