# Extrai as skills (Rezvani, Softaworks, GStack) em .claude\skills deste projeto
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Expand-Archive -Path ".\skills-bundle.zip" -DestinationPath "." -Force
Remove-Item ".\skills-bundle.zip"
$n = (Get-ChildItem ".\.claude\skills" -Directory).Count
Write-Host "OK: $n skills em .claude\skills"
if (Get-Command bun -ErrorAction SilentlyContinue) {
  Write-Host "Rodando setup do GStack..."
  Set-Location ".\.claude\skills\gstack"; bash ./setup
} else {
  Write-Host "GStack: instale o Bun (https://bun.sh) e rode 'bash ./setup' em .claude\skills\gstack para ativar o navegador e as sub-skills."
}
