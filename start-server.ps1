$ErrorActionPreference = "Stop"

$python = "C:\Users\test\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Convert-SecureStringToPlainText($secureValue) {
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -and $_ -ne 0 }
foreach ($processId in $pids) {
  Write-Host "Stoppe alten Serverprozess auf Port 8000: $processId"
  Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}

$plainKey = $env:OPENAI_API_KEY
if ([string]::IsNullOrWhiteSpace($plainKey)) {
  $plainKey = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($plainKey)) {
  $secureKey = Read-Host "OpenAI API Key eingeben" -AsSecureString
  $plainKey = Convert-SecureStringToPlainText $secureKey
}
$plainKey = ($plainKey -replace "\s", "").Trim()

$env:OPENAI_API_KEY = $plainKey
$env:OPENAI_MODEL = "gpt-4.1-mini"

if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
  throw "OPENAI_API_KEY wurde nicht gesetzt. Bitte Key beim Prompt einfuegen."
}

if (-not $env:OPENAI_API_KEY.StartsWith("sk-")) {
  throw "Der eingegebene Wert sieht nicht wie ein OpenAI API-Key aus."
}

Write-Host "OpenAI API Key gesetzt. Laenge:" $env:OPENAI_API_KEY.Length

$twilioSid = $env:TWILIO_ACCOUNT_SID
if ([string]::IsNullOrWhiteSpace($twilioSid)) {
  $twilioSid = (Read-Host "Twilio Account SID eingeben (Enter = ueberspringen)").Trim()
}
if (-not [string]::IsNullOrWhiteSpace($twilioSid)) {
  $twilioToken = $env:TWILIO_AUTH_TOKEN
  if ([string]::IsNullOrWhiteSpace($twilioToken)) {
    $secureTwilioToken = Read-Host "Twilio Auth Token eingeben" -AsSecureString
    $twilioToken = (Convert-SecureStringToPlainText $secureTwilioToken).Trim()
  }

  $twilioFrom = $env:TWILIO_WHATSAPP_FROM
  if ([string]::IsNullOrWhiteSpace($twilioFrom)) {
    $twilioFrom = (Read-Host "Twilio WhatsApp From eingeben, z. B. whatsapp:+14155238886").Trim()
  }

  $env:TWILIO_ACCOUNT_SID = $twilioSid
  $env:TWILIO_AUTH_TOKEN = $twilioToken
  $env:TWILIO_WHATSAPP_FROM = $twilioFrom

  if (-not $env:TWILIO_ACCOUNT_SID.StartsWith("AC")) {
    throw "Der Twilio Account SID sollte mit AC beginnen."
  }
  if ([string]::IsNullOrWhiteSpace($env:TWILIO_AUTH_TOKEN)) {
    throw "TWILIO_AUTH_TOKEN wurde nicht gesetzt."
  }
  if ([string]::IsNullOrWhiteSpace($env:TWILIO_WHATSAPP_FROM)) {
    throw "TWILIO_WHATSAPP_FROM wurde nicht gesetzt."
  }

  Write-Host "Twilio WhatsApp gesetzt:" $env:TWILIO_WHATSAPP_FROM
} else {
  Write-Host "Twilio uebersprungen. WhatsApp-Senden ist lokal deaktiviert."
}

Write-Host "Starte RecruitOS auf http://127.0.0.1:8000/"
& $python .\server.py
