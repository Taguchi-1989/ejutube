#Requires -Version 7.0
<#
.SYNOPSIS
    ejutube デイリー起動スクリプト（Windows / PowerShell 7+）

.DESCRIPTION
    Ollama の起動確認 → VOICEVOX の確認 → `yt-ja serve` の起動 → ブラウザを開く。
    詳細なフローは scripts\FLOW.md を参照してください。

.PARAMETER Port
    Web サーバーのポート番号（既定: 3000）。yt-ja serve の --port に渡されます。

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 --port 3001
#>

param(
    [int]$Port = 3000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# スクリプト自身の場所からリポジトリルートを解決する
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# 残りの引数（--port 以外）を yt-ja serve に渡す
# $args には $Port 以外のすべての引数が入る（PSBoundParameters でフィルタ）
$PassthroughArgs = @()
if ($PSBoundParameters.ContainsKey('Port')) {
    $PassthroughArgs = @('--port', $Port)
}

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

function Test-HttpPort {
    param([int]$Port, [int]$TimeoutMs = 2000)
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$Port/")
        $req.Timeout = $TimeoutMs
        $req.Method  = 'GET'
        $resp = $req.GetResponse()
        $resp.Close()
        return $true
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) { return $true }
        return $false
    } catch {
        return $false
    }
}

# ---------------------------------------------------------------------------
# ステップ 1: .env の存在確認
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ejutube 起動" -ForegroundColor Cyan
Write-Host "  リポジトリ: $ProjectDir" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Step "[1/4] .env ファイルを確認"

$envPath = Join-Path $ProjectDir '.env'
if (-not (Test-Path $envPath)) {
    Write-Err ".env が見つかりません。先にセットアップを実行してください:"
    Write-Info "  scripts\setup.bat をダブルクリック"
    Write-Info "  または: pwsh -File scripts\setup.ps1"
    exit 1
}
Write-OK ".env が存在します"

# ---------------------------------------------------------------------------
# ステップ 2: Ollama の確認・起動
# ---------------------------------------------------------------------------

Write-Step "[2/4] Ollama (:11434) を確認"

if (Test-HttpPort -Port 11434) {
    Write-OK "Ollama は :11434 で稼働中"
} else {
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd) {
        Write-Err "ollama コマンドが見つかりません。"
        Write-Info "インストール: https://ollama.com/download"
        Write-Info "インストール後に setup.bat を再実行してください。"
        exit 1
    }

    Write-Info "Ollama を起動します（バックグラウンド）..."
    Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden -ErrorAction SilentlyContinue
    Write-Info "5秒待機中..."
    Start-Sleep -Seconds 5

    if (Test-HttpPort -Port 11434) {
        Write-OK "Ollama が :11434 で起動しました"
    } else {
        Write-Err "Ollama が :11434 で応答しません。"
        Write-Info "別のターミナルで `ollama serve` を実行してから再試行してください。"
        exit 1
    }
}

# ---------------------------------------------------------------------------
# ステップ 3: VOICEVOX の確認（非致命的）
# ---------------------------------------------------------------------------

Write-Step "[3/4] VOICEVOX Engine (:50021) を確認"

if (Test-HttpPort -Port 50021) {
    Write-OK "VOICEVOX は :50021 で稼働中"
} else {
    Write-Warn "VOICEVOX が :50021 で応答しません。"
    Write-Info "TTS（音声合成）を使う場合は VOICEVOX を手動で起動してください。"
    Write-Info "詳細: docs\VOICEVOX_SETUP.md"
    Write-Info "（字幕翻訳・要約機能は VOICEVOX なしでも動作します）"
}

# ---------------------------------------------------------------------------
# gemma4:e4b モデルの確認（非致命的）
# ---------------------------------------------------------------------------

try {
    $listOutput = & ollama list 2>&1
    if ($listOutput -match 'gemma4:e4b') {
        Write-Info "モデル確認: gemma4:e4b はロード済みです"
    } else {
        Write-Warn "gemma4:e4b モデルが見つかりません。"
        Write-Info "翻訳・要約機能を使う前に: ollama pull gemma4:e4b"
    }
} catch {
    Write-Warn "ollama list の確認をスキップしました（Ollama が応答中のため）"
}

# ---------------------------------------------------------------------------
# ステップ 4: yt-ja serve の起動
# ---------------------------------------------------------------------------

Write-Step "[4/4] Web サーバーを起動 (yt-ja serve)"

$serveUrl = "http://localhost:$Port"
Write-Info "起動コマンド: yt-ja serve $($PassthroughArgs -join ' ')"
Write-Info "URL: $serveUrl"
Write-Info "Ctrl+C で停止します。"
Write-Host ""

# 5秒後にブラウザを開くジョブを起動する
$browserJob = Start-Job -ScriptBlock {
    param([string]$Url)
    Start-Sleep -Seconds 5
    Start-Process $Url
} -ArgumentList $serveUrl

Push-Location $ProjectDir
try {
    # yt-ja serve を現在のウィンドウで実行（ブロッキング）
    & yt-ja serve @PassthroughArgs
} catch {
    Write-Err "yt-ja serve の起動に失敗しました: $_"
    Write-Info "Python パッケージが正しくインストールされているか確認: pip install -e ."
    exit 1
} finally {
    Pop-Location
    Stop-Job  -Job $browserJob -ErrorAction SilentlyContinue
    Remove-Job -Job $browserJob -ErrorAction SilentlyContinue
}
