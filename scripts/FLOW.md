# ejutube — Setup & Launch Flow Reference

This document is the canonical description of what `setup.ps1` and `start.ps1` do,
step by step. Both scripts implement these flows. Read this when debugging a failed run.

---

## 1. ASCII Flow Diagram

### Setup Phase (`setup.ps1`)

```
START
  |
  v
[1] Python >= 3.11 on PATH?
      NO  --> Print https://www.python.org/downloads/  --> EXIT 1
      YES --> [OK] continue
  |
  v
[2] Node.js >= 18 on PATH?
      NO  --> Print https://nodejs.org/  --> EXIT 1
      YES --> [OK] continue
  |
  v
[3] ffmpeg on PATH?
      NO  --> Print winget / scoop hint  --> [WARN] continue (non-fatal)
      YES --> [OK] continue
  |
  v
[4] ollama on PATH?
      NO  --> Print https://ollama.com/download  --> EXIT 1
      YES --> ollama serve responding on :11434?
                NO  --> try `ollama serve` in background; wait 10s; recheck
                          still NO  --> [WARN] continue (ollama may self-start later)
               YES --> [OK] continue
  |
  v
[5] gemma4:e4b model listed in `ollama list`?
      NO  --> run `ollama pull gemma4:e4b`  (long download)
      YES --> [OK] continue
  |
  v
[6] VOICEVOX responding on :50021?
      NO  --> Print https://voicevox.hiroshiba.jp/  --> [WARN] continue (non-fatal)
      YES --> [OK] continue
  |
  v
[7] .env exists?
      YES --> [OK] skip copy
       NO --> copy .env.example to .env
  |
  v
[8] pip install -e .
      (idempotent — pip skips if already installed and unchanged)
  |
  v
[9] npm install (in web/)
      (idempotent — npm skips unchanged packages)
  |
  v
[10] pytest tests/ -q
      FAIL --> Print error output  --> EXIT 1
      PASS --> [OK] continue
  |
  v
[11] Print SUCCESS BANNER + next steps
      --> Run: scripts\start.bat
END
```

### Start Phase (`start.ps1`)

```
START
  |
  v
[1] .env exists?
      NO  --> Tell user to run setup.ps1  --> EXIT 1
      YES --> [OK] continue
  |
  v
[2] Ollama responding on :11434?
      NO  --> Start-Process `ollama serve` hidden; wait 5s; recheck
                still NO  --> [ERROR] EXIT 1
              YES --> [OK] continue
      YES --> [OK] continue
  |
  v
[3] VOICEVOX responding on :50021?
      NO  --> [WARN] "VOICEVOXを手動で起動してください" (non-fatal)
      YES --> [OK] continue
  |
  v
[4] gemma4:e4b listed in `ollama list`?
      NO  --> [WARN] モデルが見つかりません (setup.ps1 --pull で解決)
      YES --> [OK] continue
  |
  v
[5] Run `yt-ja serve [extra args]` in current window
  |
  v
[6] After 5s, open http://localhost:3000 in default browser
  |
  v
(Ctrl+C to stop)
END
```

---

## 2. State Table

| Step | What is checked | Tool used | Fatal? | Action on failure |
|------|----------------|-----------|--------|-------------------|
| 1 (setup) | `python --version` >= 3.11 | `Get-Command python` + version parse | YES | Print URL, exit 1 |
| 2 (setup) | `node --version` >= 18 | `Get-Command node` + version parse | YES | Print URL, exit 1 |
| 3 (setup) | `ffmpeg -version` | `Get-Command ffmpeg` | NO | WARN + continue |
| 4 (setup) | Ollama binary exists | `Get-Command ollama` | YES | Print URL, exit 1 |
| 4b (setup) | :11434 responds | `Invoke-WebRequest` with timeout | NO | Try background start, WARN |
| 5 (setup) | `gemma4:e4b` in `ollama list` | parse stdout | NO | `ollama pull gemma4:e4b` |
| 6 (setup) | :50021 responds | `Invoke-WebRequest` with timeout | NO | WARN + continue |
| 7 (setup) | `.env` exists | `Test-Path` | NO | Copy `.env.example` |
| 8 (setup) | pip install | `pip install -e .` | YES | Print error, exit 1 |
| 9 (setup) | npm install | `npm install` in `web/` | YES | Print error, exit 1 |
| 10 (setup) | pytest | `pytest tests/ -q` | YES | Print output, exit 1 |
| 1 (start) | `.env` exists | `Test-Path` | YES | Tell user to run setup, exit 1 |
| 2 (start) | :11434 responds | `Invoke-WebRequest` with timeout | YES | Try background start, recheck, exit 1 |
| 3 (start) | :50021 responds | `Invoke-WebRequest` with timeout | NO | WARN |
| 4 (start) | `gemma4:e4b` in `ollama list` | parse stdout | NO | WARN |
| 5 (start) | `yt-ja serve` | subprocess | YES (blocks) | Ctrl+C to exit |
| 6 (start) | Open browser | `Start-Process` | NO | Proceeds silently |

---

## 3. Idempotency Notes

Every step is designed to be safe when re-run:

- **Python / Node / ffmpeg / Ollama checks**: read-only, no side effects.
- **ollama pull**: Ollama skips the download if the model is already present.
- **.env copy**: guarded by `if (-not (Test-Path .env))` — never overwrites.
- **pip install -e .**: pip's dependency resolver skips unchanged packages.
- **npm install**: npm skips packages that are already at the correct version.
- **pytest**: read-only test run, no state changes to production files.
- **start.ps1 Ollama start**: guarded by `Test-NetConnection` before and after attempt.

Re-running `setup.ps1` after a partial failure picks up from whatever step failed,
because each step independently checks its own precondition.

---

## 4. Troubleshooting Table

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `[ERROR] Python 3.11+ が見つかりません` | Python not installed or < 3.11 | Install from https://www.python.org/downloads/ ; check "Add to PATH" |
| `[ERROR] Node.js 18+ が見つかりません` | Node not installed or < 18 | Install from https://nodejs.org/ |
| `[WARN] ffmpeg が見つかりません` | ffmpeg not on PATH | `winget install Gyan.FFmpeg` or add ffmpeg/bin to PATH |
| `[ERROR] Ollama が見つかりません` | Ollama not installed | Install from https://ollama.com/download |
| `[WARN] Ollama が :11434 で応答しません` | Ollama not started | Run `ollama serve` in a separate terminal, or it starts automatically on first use |
| `ollama pull` hangs very long | Large model download (~5 GB) | Wait; check disk space; retry on faster network |
| `[WARN] VOICEVOX が :50021 で応答しません` | VOICEVOX not started | Run VOICEVOX desktop app, or see docs\VOICEVOX_SETUP.md |
| `pytest` fails | Import error or missing dependency | Run `pip install -e .[dev]` manually; check error message |
| `npm install` fails | Node version mismatch | Upgrade Node to 18+ |
| `yt-ja serve` not found | pip install didn't complete | Re-run `setup.ps1`; or `pip install -e .` manually |
| Browser opens but page errors | Web server not ready yet | Wait a few more seconds then refresh |
| `[ERROR] .env が見つかりません` in start.ps1 | setup.ps1 not yet run | Run `scripts\setup.bat` first |
| `gemma4:e4b` model missing at start | Model not pulled | Run `ollama pull gemma4:e4b` |
| Port 3000 already in use | Another process using it | Pass `--port 3001` to `start.ps1` |
| Port 11434 conflict | Another Ollama instance | Stop the duplicate; or use the running one |
| Port 50021 conflict | VOICEVOX already running | Usually OK — it's the one you want |
| `ExecutionPolicy` error | Windows blocks unsigned scripts | setup.bat / start.bat pass `-ExecutionPolicy Bypass` automatically |
| PowerShell 5 incompatibility | `??` / ternary syntax not supported | Install PowerShell 7 from https://github.com/PowerShell/PowerShell/releases |
