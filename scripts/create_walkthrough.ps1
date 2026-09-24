param(
    [string]$Output = "artifacts/EstatePulse_Walkthrough.mp4"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$workDir = Join-Path $projectRoot "artifacts\walkthrough_work"
$audioDir = Join-Path $workDir "audio"
New-Item -ItemType Directory -Force -Path $audioDir | Out-Null

$scenes = @(
    @{
        File = "01-intro.wav"
        Text = "Meet EstatePulse, a conversational AI analyst for real estate portfolios. It turns structured property data into clear, decision ready answers."
    },
    @{
        File = "02-login.wav"
        Text = "A reviewer begins by selecting one of four isolated synthetic portfolios. Every conversation and calculation stays scoped to the selected owner."
    },
    @{
        File = "03-analysis.wav"
        Text = "Ask a question in natural language. EstatePulse retrieves exact portfolio records, performs financial calculations in Python, and streams a concise answer with structured evidence."
    },
    @{
        File = "04-insights.wav"
        Text = "The analyst can surface the signals that matter: value concentration, vacant assets, annual rent, and gross rental yield, all grounded in recorded holdings."
    },
    @{
        File = "05-safety.wav"
        Text = "Safety is built into every action. What if scenarios never change actual holdings, and proposed updates remain pending until the user reviews and confirms them."
    },
    @{
        File = "06-evals.wav"
        Text = "A dedicated evaluation harness measures intent accuracy, numerical grounding, tenant isolation, prompt injection resistance, latency, and model availability. The offline suite passes all fourteen cases."
    },
    @{
        File = "07-close.wav"
        Text = "EstatePulse combines a modern React experience with FastAPI, Gemini, LangGraph, and deterministic analytics for a fast, auditable portfolio assistant."
    }
)

Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice("Microsoft Zira Desktop")
$voice.Rate = 1
$voice.Volume = 100
try {
    foreach ($scene in $scenes) {
        $audioPath = Join-Path $audioDir $scene.File
        $voice.SetOutputToWaveFile($audioPath)
        $voice.Speak($scene.Text)
        $voice.SetOutputToNull()
    }
}
finally {
    $voice.Dispose()
}

$outputPath = Join-Path $projectRoot $Output
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outputPath) | Out-Null

Push-Location $projectRoot
try {
    uv run --with pillow --with numpy --with imageio --with imageio-ffmpeg python scripts/render_walkthrough.py --audio-dir $audioDir --output $outputPath
}
finally {
    Pop-Location
}

Write-Output $outputPath
