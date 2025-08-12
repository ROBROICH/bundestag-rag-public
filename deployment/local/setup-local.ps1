# Local Development Setup Script
# This script sets up the Bundestag RAG API for local development

param(
    [string]$OpenAIApiKey = "",
    [switch]$SkipVenv = $false,
    [switch]$UseConda = $false,
    [switch]$Force = $false,
    [string]$PythonVersion = "3.11"
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$VenvPath = Join-Path $ProjectRoot "venv"
$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
$EnvTemplatePath = Join-Path $PSScriptRoot ".env.local.template"
$EnvPath = Join-Path $ProjectRoot ".env"

Write-Host "🚀 Bundestag RAG API - Local Development Setup" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Gray

# Function to check if command exists
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Function to prompt for input with default
function Get-UserInput {
    param(
        [string]$Prompt,
        [string]$Default = "",
        [switch]$Secure = $false
    )
    
    if ($Default) {
        $PromptText = "$Prompt [$Default]: "
    } else {
        $PromptText = "$Prompt : "
    }
    
    if ($Secure) {
        $SecureInput = Read-Host -Prompt $PromptText -AsSecureString
        $UserInput = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureInput))
    } else {
        $UserInput = Read-Host -Prompt $PromptText
    }
    
    if ([string]::IsNullOrWhiteSpace($UserInput) -and $Default) {
        return $Default
    }
    return $UserInput
}

try {
    Write-Host "📍 Project Location: $ProjectRoot" -ForegroundColor Cyan
    Set-Location $ProjectRoot

    # Step 1: Verify Prerequisites
    Write-Host "`n🔍 Checking Prerequisites..." -ForegroundColor Yellow
    
    # Check Python
    if (-not (Test-Command "python")) {
        Write-Error "❌ Python is not installed or not in PATH. Please install Python $PythonVersion or higher."
    }
    
    $PythonVersionOutput = python --version 2>&1
    Write-Host "✅ Found: $PythonVersionOutput" -ForegroundColor Green
    
    # Check Git (optional)
    if (Test-Command "git") {
        Write-Host "✅ Git is available" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Git not found (optional)" -ForegroundColor Yellow
    }

    # Step 2: Python Environment Setup
    if (-not $SkipVenv) {
        Write-Host "`n🐍 Setting up Python Environment..." -ForegroundColor Yellow
        
        if ($UseConda) {
            Write-Host "📦 Using Conda environment..." -ForegroundColor Cyan
            if (-not (Test-Command "conda")) {
                Write-Error "❌ Conda is not installed or not in PATH."
            }
            
            $CondaEnvName = "bundestag-rag"
            $ExistingEnv = conda env list | Select-String $CondaEnvName
            
            if ($ExistingEnv -and -not $Force) {
                $Response = Get-UserInput "Conda environment '$CondaEnvName' already exists. Recreate?" "n"
                if ($Response -eq "y" -or $Response -eq "yes") {
                    conda env remove -n $CondaEnvName -y
                    conda create -n $CondaEnvName python=$PythonVersion -y
                }
            } else {
                if ($ExistingEnv) { conda env remove -n $CondaEnvName -y }
                conda create -n $CondaEnvName python=$PythonVersion -y
            }
            
            conda activate $CondaEnvName
            Write-Host "✅ Conda environment '$CondaEnvName' activated" -ForegroundColor Green
            
        } else {
            Write-Host "📦 Using Python virtual environment..." -ForegroundColor Cyan
            
            if (Test-Path $VenvPath) {
                if ($Force) {
                    Write-Host "🗑️  Removing existing virtual environment..." -ForegroundColor Yellow
                    Remove-Item -Recurse -Force $VenvPath
                } else {
                    $Response = Get-UserInput "Virtual environment already exists. Recreate?" "n"
                    if ($Response -eq "y" -or $Response -eq "yes") {
                        Remove-Item -Recurse -Force $VenvPath
                    } else {
                        Write-Host "📂 Using existing virtual environment" -ForegroundColor Cyan
                    }
                }
            }
            
            if (-not (Test-Path $VenvPath)) {
                Write-Host "🔨 Creating virtual environment..." -ForegroundColor Cyan
                python -m venv $VenvPath
            }
            
            # Activate virtual environment
            $ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
            if (Test-Path $ActivateScript) {
                & $ActivateScript
                Write-Host "✅ Virtual environment activated" -ForegroundColor Green
            } else {
                Write-Error "❌ Failed to find activation script at $ActivateScript"
            }
        }
    }

    # Step 3: Install Dependencies
    Write-Host "`n📦 Installing Dependencies..." -ForegroundColor Yellow
    
    if (-not (Test-Path $RequirementsPath)) {
        Write-Error "❌ requirements.txt not found at $RequirementsPath"
    }
    
    Write-Host "📋 Installing packages from requirements.txt..." -ForegroundColor Cyan
    python -m pip install --upgrade pip
    pip install -r $RequirementsPath
    
    Write-Host "✅ Dependencies installed successfully" -ForegroundColor Green

    # Step 4: Environment Configuration
    Write-Host "`n⚙️  Configuring Environment..." -ForegroundColor Yellow
    
    if (-not (Test-Path $EnvPath) -or $Force) {
        if (Test-Path $EnvTemplatePath) {
            Copy-Item $EnvTemplatePath $EnvPath
            Write-Host "📄 Created .env file from template" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Template not found, creating basic .env file" -ForegroundColor Yellow
            $BasicEnv = @"
# Bundestag RAG API - Local Development Configuration
OPENAI_API_KEY=your-openai-api-key-here
STREAMLIT_SERVER_HEADLESS=false
STREAMLIT_SERVER_ENABLE_CORS=true
STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true
STREAMLIT_SERVER_ADDRESS=127.0.0.1
STREAMLIT_SERVER_PORT=8501
CACHE_ENABLED=true
LOG_LEVEL=INFO
DEVELOPMENT_MODE=true
"@
            Set-Content -Path $EnvPath -Value $BasicEnv
            Write-Host "📄 Created basic .env file" -ForegroundColor Green
        }
    } else {
        Write-Host "📄 .env file already exists" -ForegroundColor Cyan
    }

    # Step 5: OpenAI API Key Configuration
    Write-Host "`n🔑 Configuring OpenAI API Key..." -ForegroundColor Yellow
    
    if ([string]::IsNullOrWhiteSpace($OpenAIApiKey)) {
        $OpenAIApiKey = Get-UserInput "Enter your OpenAI API Key" "" -Secure
    }
    
    if (-not [string]::IsNullOrWhiteSpace($OpenAIApiKey)) {
        # Update .env file with API key
        $EnvContent = Get-Content $EnvPath
        $UpdatedContent = $EnvContent | ForEach-Object {
            if ($_ -match '^OPENAI_API_KEY=') {
                "OPENAI_API_KEY=$OpenAIApiKey"
            } else {
                $_
            }
        }
        Set-Content -Path $EnvPath -Value $UpdatedContent
        Write-Host "✅ OpenAI API key configured" -ForegroundColor Green
    } else {
        Write-Host "⚠️  OpenAI API key not set - you'll need to update .env manually" -ForegroundColor Yellow
    }

    # Step 6: Create necessary directories
    Write-Host "`n📁 Creating Project Directories..." -ForegroundColor Yellow
    
    $Directories = @(
        "data",
        "data/cache", 
        "data/uploads",
        "logs",
        "temp",
        "temp/processing"
    )
    
    foreach ($Dir in $Directories) {
        $DirPath = Join-Path $ProjectRoot $Dir
        if (-not (Test-Path $DirPath)) {
            New-Item -ItemType Directory -Path $DirPath -Force | Out-Null
            Write-Host "📂 Created: $Dir" -ForegroundColor Cyan
        }
    }

    # Step 7: Test Installation
    Write-Host "`n🧪 Testing Installation..." -ForegroundColor Yellow
    
    try {
        Write-Host "🔍 Testing API connection..." -ForegroundColor Cyan
        python main.py test 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ API connection test passed" -ForegroundColor Green
        } else {
            Write-Host "⚠️  API connection test had issues (this may be normal if API key is not set)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Could not run API test (this may be normal)" -ForegroundColor Yellow
    }
    
    try {
        Write-Host "🔍 Testing imports..." -ForegroundColor Cyan
        $ImportTest = python -c "import streamlit; import openai; import src.api.client; print('All imports successful')" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Import test passed" -ForegroundColor Green
        } else {
            Write-Host "❌ Import test failed: $ImportTest" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ Import test failed" -ForegroundColor Red
    }

    # Step 8: Provide Usage Instructions
    Write-Host "`n🎯 Setup Complete!" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Gray
    
    Write-Host "`n📖 How to start the application:" -ForegroundColor Cyan
    Write-Host ""
    
    if ($UseConda) {
        Write-Host "1. Activate Conda environment:" -ForegroundColor White
        Write-Host "   conda activate bundestag-rag" -ForegroundColor Yellow
    } else {
        Write-Host "1. Activate virtual environment:" -ForegroundColor White
        Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    }
    
    Write-Host "`n2. Start the Streamlit web application:" -ForegroundColor White
    Write-Host "   streamlit run src/web/streamlit_app_modular.py" -ForegroundColor Yellow
    
    Write-Host "`n3. OR start the CLI application:" -ForegroundColor White
    Write-Host "   python main.py interactive" -ForegroundColor Yellow
    
    Write-Host "`n🌐 Access URLs:" -ForegroundColor Cyan
    Write-Host "   Web UI: http://localhost:8501" -ForegroundColor Yellow
    Write-Host "   CLI: Interactive terminal interface" -ForegroundColor Yellow
    
    Write-Host "`n⚙️  Configuration:" -ForegroundColor Cyan
    Write-Host "   Environment file: .env" -ForegroundColor Yellow
    Write-Host "   Logs directory: logs/" -ForegroundColor Yellow
    Write-Host "   Data directory: data/" -ForegroundColor Yellow
    
    if ([string]::IsNullOrWhiteSpace($OpenAIApiKey) -or $OpenAIApiKey -eq "your-openai-api-key-here") {
        Write-Host "`n⚠️  IMPORTANT: Update your OpenAI API key in .env file!" -ForegroundColor Red
        Write-Host "   Edit .env and set OPENAI_API_KEY=your-actual-api-key" -ForegroundColor Yellow
    }
    
    Write-Host "`n🆘 Need help?" -ForegroundColor Cyan
    Write-Host "   Check: deployment/LOCAL_DEPLOYMENT.md" -ForegroundColor Yellow
    Write-Host "   Or run: python main.py test" -ForegroundColor Yellow

} catch {
    Write-Host "`n❌ Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`n🔧 Troubleshooting:" -ForegroundColor Cyan
    Write-Host "1. Ensure Python 3.11+ is installed" -ForegroundColor Yellow
    Write-Host "2. Check if you have the necessary permissions" -ForegroundColor Yellow
    Write-Host "3. Try running with -Force to recreate environment" -ForegroundColor Yellow
    Write-Host "4. Check the full deployment guide: deployment/LOCAL_DEPLOYMENT.md" -ForegroundColor Yellow
    exit 1
}
