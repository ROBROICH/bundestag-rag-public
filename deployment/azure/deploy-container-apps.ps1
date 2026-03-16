# Deploy Bundestag MCP Chat to Azure Container Apps
# Prerequisites: Azure CLI logged in, Docker running
#
# Usage:
#   .\deployment\azure\deploy-container-apps.ps1 -ResourceGroup "rg-bundestag" -OpenAIKey "sk-..."
#   .\deployment\azure\deploy-container-apps.ps1 -ResourceGroup "rg-bundestag" -OpenAIKey "sk-..." -DIPKey "xxx"
#
# After first deploy, update ALLOWED_ORIGINS:
#   az containerapp update -n bundestag-mcp-chat -g rg-bundestag --set-env-vars ALLOWED_ORIGINS=https://<fqdn>

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$true)]
    [string]$OpenAIKey,

    [string]$DIPKey = "",
    [string]$ACRName = "acrbundestagrag",
    [string]$AppName = "bundestag-mcp-chat",
    [string]$Location = "westeurope",
    [string]$Model = "gpt-5-mini",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path

Write-Host "`n=== Step 1: Ensure resource group exists ===" -ForegroundColor Cyan
az group create --name $ResourceGroup --location $Location --output none 2>$null
Write-Host "  Resource group: $ResourceGroup ($Location)" -ForegroundColor Green

Write-Host "`n=== Step 2: Build & push Docker image ===" -ForegroundColor Cyan
$ACRServer = "$ACRName.azurecr.io"
$ImageFull = "$ACRServer/${AppName}:$ImageTag"

# Log into ACR
Write-Host "  Logging into ACR: $ACRServer"
az acr login --name $ACRName

# Build from Dockerfile.mcp
Write-Host "  Building image: $ImageFull"
Push-Location $RepoRoot
docker build -f deployment/docker/Dockerfile.mcp -t $ImageFull .
Pop-Location

# Push
Write-Host "  Pushing image..."
docker push $ImageFull
Write-Host "  Image pushed: $ImageFull" -ForegroundColor Green

Write-Host "`n=== Step 3: Deploy with Bicep ===" -ForegroundColor Cyan
$BicepFile = "$PSScriptRoot\bicep\azure-container-apps-mcp.bicep"

$DeployParams = @(
    "--resource-group", $ResourceGroup,
    "--template-file", $BicepFile,
    "--parameters",
    "appName=$AppName",
    "location=$Location",
    "containerImage=${AppName}:$ImageTag",
    "acrName=$ACRName",
    "openaiApiKey=$OpenAIKey",
    "dipApiKey=$DIPKey",
    "openaiModel=$Model"
)

az deployment group create @DeployParams --output none
Write-Host "  Bicep deployment complete" -ForegroundColor Green

Write-Host "`n=== Step 4: Get app URL ===" -ForegroundColor Cyan
$FQDN = az containerapp show -n $AppName -g $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
$AppUrl = "https://$FQDN"

Write-Host "`n  App URL:  $AppUrl" -ForegroundColor Green
Write-Host "  Chat:    $AppUrl/" -ForegroundColor Green
Write-Host "  MCP:     $AppUrl/mcp" -ForegroundColor Green
Write-Host "  Health:  $AppUrl/health" -ForegroundColor Green

Write-Host "`n=== Step 5: Set ALLOWED_ORIGINS to own domain ===" -ForegroundColor Cyan
az containerapp update -n $AppName -g $ResourceGroup --set-env-vars "ALLOWED_ORIGINS=$AppUrl" --output none
Write-Host "  CORS locked to: $AppUrl" -ForegroundColor Green

Write-Host "`n=== Deployment complete! ===" -ForegroundColor Green
Write-Host "  Test: curl $AppUrl/health" -ForegroundColor Yellow
