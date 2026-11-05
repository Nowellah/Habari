# Send one message to the Mukwano gateway, as if a child sent it on a channel.
# Usage:
#   .\tools\send.ps1 sms HELP
#   .\tools\send.ps1 telegram "someone wants my pictures"
#   .\tools\send.ps1 sms HELP -From +256700000222      (pretend to be another child)
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("sms", "ussd", "voice", "whatsapp", "telegram", "web", "extension", "siri")]
    [string]$Channel,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$Text,

    [string]$From,
    [string]$Server = "http://localhost:8000"
)

# Default test sender for each channel, in the format that channel uses.
$defaults = @{
    sms       = "+256700000001"
    ussd      = "+256700000002"
    voice     = "+256700000003"
    whatsapp  = "+256700000004"
    telegram  = "tg:5550001"
    web       = "web-test-1"
    extension = "ext-test-1"
    siri      = "siri-test-1"
}
if (-not $From) { $From = $defaults[$Channel] }

$body = @{ channel = $Channel; sender_id = $From; text = $Text } | ConvertTo-Json -Compress
try {
    $r = Invoke-RestMethod -Method Post -Uri "$Server/api/channel/$Channel" -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
} catch {
    Write-Host "Could not reach the server at $Server. Is 'manage.py runserver' running in another window?" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[$Channel] child ($From): $Text" -ForegroundColor DarkGray
Write-Host "Reply: $($r.reply_text)" -ForegroundColor Green
if ($r.case_code) { Write-Host "Case code: $($r.case_code)" -ForegroundColor Yellow }
Write-Host "(state: $($r.state), reply in $($r.first_reply_ms) ms)" -ForegroundColor DarkGray
