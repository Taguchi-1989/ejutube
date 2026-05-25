#Requires -Version 7.0
<#
.SYNOPSIS
    ejutube 生成物クリーンアップスクリプト

.DESCRIPTION
    output/ の削除（確認あり）と __pycache__ / .pytest_cache / *.egg-info の削除を行います。
    .env / node_modules / .venv は削除しません。

.PARAMETER Force
    確認プロンプトをスキップして output/ を削除します。

.EXAMPLE
    .\scripts\clean.ps1
    .\scripts\clean.ps1 -Force
#>

param(
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

function Write-OK   { param([string]$Msg); Write-Host "  [OK]   $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg); Write-Host "  [WARN] $Msg" -ForegroundColor Yellow }
function Write-Info { param([string]$Msg); Write-Host "  [INFO] $Msg" -ForegroundColor Cyan }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ejutube クリーンアップ" -ForegroundColor Cyan
Write-Host "  リポジトリ: $ProjectDir" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# output/ の削除（確認あり）
# ---------------------------------------------------------------------------

$outputDir = Join-Path $ProjectDir 'output'
if (Test-Path $outputDir) {
    $doDelete = $Force.IsPresent
    if (-not $doDelete) {
        Write-Host ""
        Write-Host "  output/ を削除しますか？" -ForegroundColor Yellow
        Write-Host "  （字幕・音声・player.json など生成物がすべて消えます）" -ForegroundColor Yellow
        $ans = Read-Host "  削除する場合は 'yes' と入力してください"
        $doDelete = ($ans -eq 'yes')
    }

    if ($doDelete) {
        Remove-Item -Recurse -Force $outputDir
        Write-OK "output/ を削除しました"
    } else {
        Write-Warn "output/ の削除をスキップしました"
    }
} else {
    Write-Info "output/ は存在しません（スキップ）"
}

# ---------------------------------------------------------------------------
# __pycache__ の削除
# ---------------------------------------------------------------------------

$pycacheDirs = Get-ChildItem -Path $ProjectDir -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch 'node_modules|\.venv' }

if ($pycacheDirs.Count -gt 0) {
    $pycacheDirs | ForEach-Object {
        Remove-Item -Recurse -Force $_.FullName
        Write-Info "削除: $($_.FullName)"
    }
    Write-OK "__pycache__ を $($pycacheDirs.Count) 個削除しました"
} else {
    Write-Info "__pycache__ は見つかりませんでした"
}

# ---------------------------------------------------------------------------
# .pytest_cache の削除
# ---------------------------------------------------------------------------

$pytestCache = Join-Path $ProjectDir '.pytest_cache'
if (Test-Path $pytestCache) {
    Remove-Item -Recurse -Force $pytestCache
    Write-OK ".pytest_cache を削除しました"
} else {
    Write-Info ".pytest_cache は見つかりませんでした"
}

# ---------------------------------------------------------------------------
# *.egg-info の削除
# ---------------------------------------------------------------------------

$eggInfoDirs = Get-ChildItem -Path $ProjectDir -Recurse -Directory -Filter '*.egg-info' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch 'node_modules|\.venv' }

if ($eggInfoDirs.Count -gt 0) {
    $eggInfoDirs | ForEach-Object {
        Remove-Item -Recurse -Force $_.FullName
        Write-Info "削除: $($_.FullName)"
    }
    Write-OK "*.egg-info を $($eggInfoDirs.Count) 個削除しました"
} else {
    Write-Info "*.egg-info は見つかりませんでした"
}

Write-Host ""
Write-OK "クリーンアップ完了"
Write-Host ""
