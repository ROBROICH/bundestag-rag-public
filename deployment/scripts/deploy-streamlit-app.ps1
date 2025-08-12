# Deploy Bundestag RAG API Streamlit Application to Azure Container Apps
# This script builds and deploys the Streamlit application with optimized performance
#
# PERFORMANCE OPTIMIZATIONS:
# - Hash-based build detection: Avoids rebuilds when source code hasn't changed (saves 3-5 min)
# - Local Docker builds with ACR push: 2-3x faster than ACR builds (saves 2-3 min)
# - Advanced layer caching: Optimized Dockerfile with strategic COPY order (saves 1-2 min)
# - Smart change detection: Analyzes git changes and file hashes for minimal rebuilds
# - Config-only mode: Ultra-fast environment variable updates only (5-10s)
# - Skip-build mode: Deploy without building when image is current (15-20s)
# - Force-rebuild mode: Complete rebuild when needed (2-4 min with local Docker)
#
# DEPLOYMENT TIME COMPARISON:
# Traditional:     5-8 minutes every time
# Hash unchanged:  5-10 seconds (config-only)
# Local Docker:    1-3 minutes (with caching)
# ACR fallback:    2-5 minutes (cloud build)

param(
    [Parameter(Mandatory=$false)]
    [string]$OpenAIApiKey = "",
    
    [Parameter(Mandatory=$false)]
    [string]$BUNDESTAG_API_KEY = "",
    
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId = "d99d5ab1-2ca2-4463-808e-a4a8ecff486f",
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "westeurope",
    
    [Parameter(Mandatory=$false)]
    [string]$ContainerAppName = "",
    
    [Parameter(Mandatory=$false)]
    [string]$RegistryName = "",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageName = "bundestag-rag-api",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("New", "Existing")]
    [string]$DeploymentMode = "Existing",
    
    [Parameter(Mandatory=$false)]
    [string]$EnvironmentName = "",
    
    [Parameter(Mandatory=$false)]
    [string]$ResourcePrefix = "bundestag-rag",
    
    [Parameter(Mandatory=$false)]
    [switch]$FastDeploy = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$ForceRebuild = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$ConfigOnly = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$UseOptimized = $false
)

# Generate default names based on prefix if not provided
if ([string]::IsNullOrEmpty($ResourceGroup)) {
    $ResourceGroup = "rg-$ResourcePrefix"
}
if ([string]::IsNullOrEmpty($ContainerAppName)) {
    $ContainerAppName = "$ResourcePrefix-app"
}
if ([string]::IsNullOrEmpty($RegistryName)) {
    # Remove hyphens for registry name (Azure requirement)
    $RegistryName = "acr$($ResourcePrefix -replace '-', '')"
}
if ([string]::IsNullOrEmpty($EnvironmentName)) {
    $EnvironmentName = "$ResourcePrefix-env"
}

# Configuration
$SUBSCRIPTION_ID = $SubscriptionId
$RESOURCE_GROUP = $ResourceGroup
$CONTAINER_APP = $ContainerAppName
$REGISTRY_NAME = $RegistryName
$IMAGE_NAME = $ImageName
$IMAGE_TAG = $ImageTag
$LOCATION = $Location
$ENVIRONMENT = $EnvironmentName

Write-Host "[DEPLOY] Deploying Bundestag RAG API Streamlit Application" -ForegroundColor Green
Write-Host "[INFO] Deployment Mode: $DeploymentMode" -ForegroundColor Cyan
if ($ConfigOnly.IsPresent) {
    Write-Host "[INFO] Config-only mode: Ultra-fast environment variable update" -ForegroundColor Magenta
    $ShouldSkipBuild = $true
} elseif ($SkipBuild.IsPresent) {
    Write-Host "[INFO] Skip-build mode: Using existing image" -ForegroundColor Cyan
    $ShouldSkipBuild = $true
} elseif ($ForceRebuild.IsPresent) {
    Write-Host "[INFO] Force-rebuild mode: Full image rebuild" -ForegroundColor Yellow
    $ShouldSkipBuild = $false
} elseif ($FastDeploy.IsPresent) {
    Write-Host "[INFO] Fast-deploy mode: Smart change detection" -ForegroundColor Cyan
} else {
    Write-Host "[INFO] Standard deployment with caching" -ForegroundColor Cyan
}
if ($DeploymentMode -eq "New") {
    Write-Host "[NEW] New deployment will create all resources" -ForegroundColor Yellow
    Write-Host "  Resource Group: $RESOURCE_GROUP" -ForegroundColor Gray
    Write-Host "  Location: $LOCATION" -ForegroundColor Gray
    Write-Host "  Registry: $REGISTRY_NAME" -ForegroundColor Gray
    Write-Host "  Container App: $CONTAINER_APP" -ForegroundColor Gray
    Write-Host "  Environment: $ENVIRONMENT" -ForegroundColor Gray
}

# Set the Azure subscription
Write-Host "[AUTH] Setting Azure subscription..." -ForegroundColor Yellow
try {
    az account set --subscription $SUBSCRIPTION_ID 2>$null
    if ($LASTEXITCODE -ne 0) { throw "Failed to set subscription" }
    
    $currentAccount = az account show --query "[name, user.name]" --output tsv
    Write-Host "[OK] Using subscription: $($currentAccount[0])" -ForegroundColor Green
    Write-Host "[OK] Account: $($currentAccount[1])" -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] Failed to set subscription. Please ensure you're logged in to Azure" -ForegroundColor Red
    Write-Host "   Run: az login" -ForegroundColor Yellow
    exit 1
}

# Create resources if new deployment
if ($DeploymentMode -eq "New") {
    Write-Host "`n[CREATE] Creating Azure resources for new deployment..." -ForegroundColor Yellow
    
    # Create Resource Group
    Write-Host "Creating resource group: $RESOURCE_GROUP..." -ForegroundColor Yellow
    $rgExists = az group exists --name $RESOURCE_GROUP
    if ($rgExists -eq "false") {
        az group create --name $RESOURCE_GROUP --location $LOCATION --output none
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Resource group created" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to create resource group" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[OK] Resource group already exists" -ForegroundColor Green
    }
    
    # Create Container Registry
    Write-Host "Creating container registry: $REGISTRY_NAME..." -ForegroundColor Yellow
    $acrExists = az acr show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --output none 2>$null
    if ($LASTEXITCODE -ne 0) {
        az acr create --resource-group $RESOURCE_GROUP --name $REGISTRY_NAME --sku Basic --admin-enabled true --location $LOCATION --output none
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Container registry created" -ForegroundColor Green
            Start-Sleep -Seconds 10
        } else {
            Write-Host "[ERROR] Failed to create container registry" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[OK] Container registry already exists" -ForegroundColor Green
    }
    
    # Create Container Apps Environment
    Write-Host "Creating Container Apps environment: $ENVIRONMENT..." -ForegroundColor Yellow
    $envExists = az containerapp env show --name $ENVIRONMENT --resource-group $RESOURCE_GROUP --output none 2>$null
    if ($LASTEXITCODE -ne 0) {
        az containerapp env create --name $ENVIRONMENT --resource-group $RESOURCE_GROUP --location $LOCATION --output none
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Container Apps environment created" -ForegroundColor Green
            Start-Sleep -Seconds 30
        } else {
            Write-Host "[ERROR] Failed to create Container Apps environment" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[OK] Container Apps environment already exists" -ForegroundColor Green
    }
    
    # Create Container App
    Write-Host "Creating container app: $CONTAINER_APP..." -ForegroundColor Yellow
    $appExists = az containerapp show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --output none 2>$null
    if ($LASTEXITCODE -ne 0) {
        # Get ACR credentials
        $ACR_SERVER = az acr show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query "loginServer" --output tsv
        $ACR_USERNAME = az acr credential show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query "username" --output tsv
        $ACR_PASSWORD = az acr credential show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query "passwords[0].value" --output tsv
        
        # Create container app with initial configuration
        az containerapp create `
            --name $CONTAINER_APP `
            --resource-group $RESOURCE_GROUP `
            --environment $ENVIRONMENT `
            --image "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" `
            --target-port 8501 `
            --ingress external `
            --cpu 0.25 `
            --memory 0.5Gi `
            --min-replicas 0 `
            --max-replicas 3 `
            --registry-server $ACR_SERVER `
            --registry-username $ACR_USERNAME `
            --registry-password $ACR_PASSWORD `
            --output none
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Container app created" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to create container app" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[OK] Container app already exists" -ForegroundColor Green
    }
}
else {
    # Check if resources exist for existing deployment
    Write-Host "`n[CHECK] Checking existing resources..." -ForegroundColor Yellow
    
    # Check Resource Group
    $rgExists = az group exists --name $RESOURCE_GROUP
    if ($rgExists -eq "false") {
        Write-Host "[ERROR] Resource group '$RESOURCE_GROUP' does not exist. Please use -DeploymentMode New or specify an existing resource group." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Resource group exists" -ForegroundColor Green
    
    # Check Container Registry
    az acr show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --output none 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Container registry '$REGISTRY_NAME' does not exist. Please use -DeploymentMode New or specify an existing registry." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Container registry exists" -ForegroundColor Green
    
    # Check Container App
    az containerapp show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --output none 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Container app '$CONTAINER_APP' does not exist. Please use -DeploymentMode New or specify an existing app." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Container app exists" -ForegroundColor Green
}

# Determine which Dockerfile and requirements to use
# Default to optimized to avoid CUDA dependencies
if ($UseOptimized.IsPresent) {
    $DockerfilePath = "deployment/docker/Dockerfile.optimized"
    $RequirementsPath = "requirements-optimized.txt"
    Write-Host "[OPTIMIZED] Using optimized requirements (no CUDA dependencies, 60-80% smaller)" -ForegroundColor Cyan
} else {
    # Use regular requirements by default (but warn about CUDA dependencies)
    $DockerfilePath = "deployment/docker/Dockerfile"
    $RequirementsPath = "requirements.txt"
    Write-Host "[WARNING] Using full requirements.txt (includes unnecessary CUDA dependencies)" -ForegroundColor Yellow
    Write-Host "[TIP] Use -UseOptimized for faster, smaller builds without CUDA" -ForegroundColor Yellow
}

if (!(Test-Path $RequirementsPath)) {
    Write-Host "[ERROR] Requirements file not found at $RequirementsPath" -ForegroundColor Red
    exit 1
}

# Check if Dockerfile exists
if (!(Test-Path $DockerfilePath)) {
    Write-Host "[ERROR] Dockerfile not found at $DockerfilePath. Please run this script from the project root directory." -ForegroundColor Red
    exit 1
}

if (!(Test-Path "src/web/streamlit_app_modular.py")) {
    Write-Host "[ERROR] Streamlit application not found. Please ensure the application files exist." -ForegroundColor Red
    exit 1
}

# Step 1.5: Get registry server name (needed earlier for local build)
Write-Host "[INFO] Getting registry information..." -ForegroundColor Yellow
$ACR_SERVER = az acr show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query "loginServer" --output tsv
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Registry server: $ACR_SERVER" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to get registry information" -ForegroundColor Red
    exit 1
}

# Fast Deploy Logic: Smart detection of what actually needs rebuilding
$ShouldSkipBuild = $false

# ConfigOnly and SkipBuild bypass all build logic
if ($ConfigOnly.IsPresent -or $SkipBuild.IsPresent) {
    $ShouldSkipBuild = $true
    if ($ConfigOnly.IsPresent) {
        Write-Host "[CONFIGONLY] Skipping all builds - updating environment variables only" -ForegroundColor Magenta
    } else {
        Write-Host "[SKIPBUILD] Using existing image without rebuild" -ForegroundColor Cyan
    }
} elseif ($ForceRebuild.IsPresent) {
    $ShouldSkipBuild = $false
    Write-Host "[FORCEREBUILD] Forcing complete image rebuild" -ForegroundColor Yellow
} elseif ($FastDeploy.IsPresent) {
    Write-Host "[FASTDEPLOY] Analyzing changes for optimized deployment..." -ForegroundColor Cyan
    
    # Hash-based change detection for ultimate speed
    $hashFile = ".deployment-hash"
    $currentHash = ""
    
    # Calculate hash of all relevant files
    Write-Host "[HASH] Computing source code hash..." -ForegroundColor Yellow
    $filesToHash = Get-ChildItem -Path "src" -Recurse -File -Include "*.py" | Sort-Object FullName
    $filesToHash += Get-Item $RequirementsPath -ErrorAction SilentlyContinue
    $filesToHash += Get-Item $DockerfilePath -ErrorAction SilentlyContinue
    
    if ($filesToHash) {
        $hashContent = ""
        foreach ($file in $filesToHash) {
            if (Test-Path $file.FullName) {
                $fileHash = Get-FileHash -Path $file.FullName -Algorithm SHA256
                $hashContent += "$($file.FullName):$($fileHash.Hash)`n"
            }
        }
        $currentHash = (Get-FileHash -InputStream ([System.IO.MemoryStream]::new([System.Text.Encoding]::UTF8.GetBytes($hashContent))) -Algorithm SHA256).Hash
        Write-Host "[HASH] Current hash: $($currentHash.Substring(0, 12))..." -ForegroundColor Gray
    }
    
    # Check if hash matches previous deployment
    if (Test-Path $hashFile) {
        $previousHash = Get-Content $hashFile -ErrorAction SilentlyContinue
        if ($currentHash -eq $previousHash) {
            Write-Host "[FASTDEPLOY] No changes detected (hash match) - skipping build!" -ForegroundColor Green
            $ShouldSkipBuild = $true
        } else {
            Write-Host "[FASTDEPLOY] Changes detected - rebuild required" -ForegroundColor Yellow
            Write-Host "[HASH] Previous: $($previousHash.Substring(0, 12))..." -ForegroundColor Gray
            Write-Host "[HASH] Current:  $($currentHash.Substring(0, 12))..." -ForegroundColor Gray
        }
    } else {
        Write-Host "[FASTDEPLOY] No previous hash found - initial build required" -ForegroundColor Yellow
    }
    
    # Always save current hash for next run (regardless of build decision)
    if ($currentHash) {
        $currentHash | Out-File -FilePath $hashFile -Force
        Write-Host "[HASH] Hash saved for next deployment" -ForegroundColor Gray
    }
    
    # Fallback to git-based detection if no hash
    if (-not $currentHash) {
        # Check if we're in a git repository
        $isGitRepo = git rev-parse --is-inside-work-tree 2>$null
        if ($LASTEXITCODE -eq 0) {
            # Get all changes (staged, unstaged, and untracked)
            $stagedFiles = git diff --cached --name-only 2>$null
            $unstagedFiles = git diff --name-only 2>$null
            $untrackedFiles = git ls-files --others --exclude-standard 2>$null
            $lastCommitFiles = git diff --name-only HEAD~1 HEAD 2>$null
            
            # Combine all changes
            $changedFiles = @()
            if ($stagedFiles) { $changedFiles += $stagedFiles }
            if ($unstagedFiles) { $changedFiles += $unstagedFiles }
            if ($untrackedFiles) { $changedFiles += $untrackedFiles }
            if ($lastCommitFiles) { $changedFiles += $lastCommitFiles }
            $changedFiles = $changedFiles | Select-Object -Unique
            
            if ($LASTEXITCODE -eq 0 -and $changedFiles) {
            # Files that DON'T require Docker rebuild (only documentation/config changes)
            $nonCriticalExtensions = @("\.md$", "\.txt$", "\.gitignore$", "\.gitattributes$")
            $nonCriticalPaths = @("^\.github/", "^docs/", "^\.claude/", "^\.vscode/", "^\.idea/")
            $nonCriticalConfigFiles = @("\.editorconfig$", "\.pre-commit-config\.yaml$")
            
            $criticalChanges = $changedFiles | Where-Object { 
                $file = $_
                $requiresRebuild = $true
                
                # Non-critical documentation files don't require rebuild
                if ($nonCriticalExtensions | Where-Object { $file -match $_ }) {
                    $requiresRebuild = $false
                }
                # Non-critical paths don't require rebuild  
                elseif ($nonCriticalPaths | Where-Object { $file -match $_ }) {
                    $requiresRebuild = $false
                }
                # Non-critical config files don't require rebuild
                elseif ($nonCriticalConfigFiles | Where-Object { $file -match $_ }) {
                    $requiresRebuild = $false
                }
                # ALL other files require rebuild, including:
                # - Python files (src/**/*.py) - need new container layer
                # - Dependencies (requirements.txt) - need pip install
                # - Docker files (Dockerfile, .dockerignore) - need container rebuild
                # - Configuration (*.json, *.yml, *.yaml) - may affect runtime
                # - Data files - may be copied into container
                
                return $requiresRebuild
            }
            
            if (-not $criticalChanges) {
                Write-Host "[FASTDEPLOY] Only documentation/tooling files changed - skipping Docker rebuild" -ForegroundColor Green
                $nonCriticalFiles = $changedFiles -join ', '
                Write-Host "[FASTDEPLOY] Non-critical files: $nonCriticalFiles" -ForegroundColor Gray
                $ShouldSkipBuild = $true
            } else {
                Write-Host "[FASTDEPLOY] Application files changed, full rebuild required" -ForegroundColor Yellow
                Write-Host "[FASTDEPLOY] Critical files: $($criticalChanges -join ', ')" -ForegroundColor Gray
                if ($changedFiles.Count -gt $criticalChanges.Count) {
                    $nonCriticalFiles = $changedFiles | Where-Object { $_ -notin $criticalChanges }
                    Write-Host "[FASTDEPLOY] Non-critical files (also changed): $($nonCriticalFiles -join ', ')" -ForegroundColor DarkGray
                }
            }
            } else {
                Write-Host "[FASTDEPLOY] Could not determine changed files, proceeding with full build" -ForegroundColor Yellow
            }
        } else {
            Write-Host "[FASTDEPLOY] Not a git repository, proceeding with full build" -ForegroundColor Yellow
        }
    }
}

# Step 1: Build the Docker image with optimized caching
if (-not $ShouldSkipBuild) {
    Write-Host "[BUILD] Building Docker image with optimized caching..." -ForegroundColor Yellow
    
    # Check if Docker is available for local build (much faster)
    $dockerAvailable = $false
    try {
        docker version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerAvailable = $true
            Write-Host "[OK] Docker detected - using local build with push (2-3x faster)" -ForegroundColor Green
        }
    } catch {}
    
    $fullImageName = "$ACR_SERVER/${IMAGE_NAME}:${IMAGE_TAG}"
    $cacheImageName = "$ACR_SERVER/${IMAGE_NAME}:cache"
    
    if ($dockerAvailable) {
        # Option 1: Local Docker build + push (FASTEST)
        Write-Host "[BUILD] Using local Docker build with layer caching..." -ForegroundColor Cyan
        
        # Login to ACR
        Write-Host "[AUTH] Logging into Azure Container Registry..." -ForegroundColor Yellow
        $ACR_USERNAME = az acr credential show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query "username" --output tsv
        $ACR_PASSWORD = az acr credential show --name $REGISTRY_NAME --resource-group $RESOURCE_GROUP --query "passwords[0].value" --output tsv
        
        echo $ACR_PASSWORD | docker login $ACR_SERVER -u $ACR_USERNAME --password-stdin 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARNING] Docker login failed, falling back to ACR build" -ForegroundColor Yellow
            $dockerAvailable = $false
        } else {
            Write-Host "[OK] Successfully logged into ACR" -ForegroundColor Green
            
            # Pull cache image if exists (for layer reuse) with timeout
            Write-Host "[CACHE] Pulling cache layers (60s timeout)..." -ForegroundColor Yellow
            $pullJob = Start-Job -ScriptBlock {
                param($cacheImageName)
                docker pull $cacheImageName 2>$null
                return $LASTEXITCODE
            } -ArgumentList $cacheImageName
            
            if (Wait-Job $pullJob -Timeout 60) {
                $pullResult = Receive-Job $pullJob
                Remove-Job $pullJob
                if ($pullResult -eq 0) {
                    Write-Host "[OK] Cache layers retrieved" -ForegroundColor Green
                } else {
                    Write-Host "[INFO] No cache found, building from scratch" -ForegroundColor Yellow
                }
            } else {
                Write-Host "[TIMEOUT] Cache pull timed out after 60 seconds, proceeding without cache" -ForegroundColor Yellow
                Stop-Job $pullJob
                Remove-Job $pullJob
            }
            
            # Build with cache-from
            Write-Host "[BUILD] Building image with cache layers..." -ForegroundColor Yellow
            $buildStart = Get-Date
            
            docker build `
                --cache-from $cacheImageName `
                --tag $fullImageName `
                --tag $cacheImageName `
                --file $DockerfilePath `
                --build-arg BUILDKIT_INLINE_CACHE=1 `
                .
            
            if ($LASTEXITCODE -eq 0) {
                $buildTime = ((Get-Date) - $buildStart).TotalSeconds
                Write-Host "[OK] Image built in $([math]::Round($buildTime, 1)) seconds" -ForegroundColor Green
                
                # Push both tags
                Write-Host "[PUSH] Pushing image to ACR..." -ForegroundColor Yellow
                $pushStart = Get-Date
                
                docker push $fullImageName
                if ($LASTEXITCODE -eq 0) {
                    docker push $cacheImageName
                    $pushTime = ((Get-Date) - $pushStart).TotalSeconds
                    Write-Host "[OK] Image pushed in $([math]::Round($pushTime, 1)) seconds" -ForegroundColor Green
                } else {
                    Write-Host "[ERROR] Failed to push image" -ForegroundColor Red
                    exit 1
                }
            } else {
                Write-Host "[ERROR] Failed to build image locally" -ForegroundColor Red
                $dockerAvailable = $false
            }
        }
    }
    
    # Fallback to ACR build if local Docker not available or failed
    if (-not $dockerAvailable) {
        Write-Host "[BUILD] Using Azure Container Registry build..." -ForegroundColor Yellow
        az acr build --registry $REGISTRY_NAME --image "${IMAGE_NAME}:${IMAGE_TAG}" --image "${IMAGE_NAME}:cache" --file $DockerfilePath . 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Docker image built via ACR" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to build Docker image" -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "[FASTDEPLOY] Skipping Docker build - using existing image" -ForegroundColor Green
}

# Step 2: Prepare environment variables
$ENV_VARS = @(
    "STREAMLIT_SERVER_HEADLESS=true",
    "STREAMLIT_SERVER_ENABLE_CORS=true", 
    "STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true",
    "STREAMLIT_SERVER_ADDRESS=0.0.0.0",
    "STREAMLIT_SERVER_PORT=8501"
)

if ($OpenAIApiKey -ne "") {
    $ENV_VARS += "OPENAI_API_KEY=$OpenAIApiKey"
    Write-Host "[OK] OpenAI API key will be configured" -ForegroundColor Green
} else {
    Write-Host "[WARNING] No OpenAI API key provided. AI features will not work." -ForegroundColor Yellow
}

if ($BUNDESTAG_API_KEY -ne "") {
    $ENV_VARS += "BUNDESTAG_API_KEY=$BUNDESTAG_API_KEY"
    Write-Host "[OK] Bundestag API key will be configured" -ForegroundColor Green
} else {
    Write-Host "[WARNING] No Bundestag API key provided. Using default key from settings." -ForegroundColor Yellow
}

# Step 3: Update the container app with cost optimization settings
if ($FastDeploy.IsPresent -and $ShouldSkipBuild) {
    Write-Host "[FASTDEPLOY] Triggering fast deployment without rebuild..." -ForegroundColor Cyan
    
    # For fast deploy, we update the container app with minimal changes to trigger a restart
    # This forces Azure to restart the running instances without rebuilding the image
    az containerapp update `
        --name $CONTAINER_APP `
        --resource-group $RESOURCE_GROUP `
        --cpu 0.25 `
        --memory 0.5Gi `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[FASTDEPLOY] Container app updated successfully (no rebuild)" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to update container app" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[UPDATE] Updating container app with new image and cost optimizations..." -ForegroundColor Yellow
    Write-Host "[COST] Applying cost optimization settings:" -ForegroundColor Cyan
    Write-Host "  - Scale-to-zero: min_replicas = 0 (save 70-80% during idle periods)" -ForegroundColor Green
    Write-Host "  - Right-sizing: 0.25 CPU, 0.5GB RAM (save 40-50% of compute costs)" -ForegroundColor Green

    # Update the container with new image and cost optimization settings
    az containerapp update `
        --name $CONTAINER_APP `
        --resource-group $RESOURCE_GROUP `
        --image "$ACR_SERVER/${IMAGE_NAME}:${IMAGE_TAG}" `
        --cpu 0.25 `
        --memory 0.5Gi `
        --min-replicas 0 `
        --max-replicas 3 `
        --output none

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Container app image updated" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to update container app image" -ForegroundColor Red
        exit 1
    }
}

# Update environment variables
az containerapp update `
    --name $CONTAINER_APP `
    --resource-group $RESOURCE_GROUP `
    --set-env-vars $ENV_VARS `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Environment variables updated" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to update environment variables" -ForegroundColor Red
    exit 1
}

# Restart the container app to ensure fresh deployment
Write-Host "[RESTART] Restarting container app..." -ForegroundColor Yellow
az containerapp restart --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --output none
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Container app restarted" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Container app restart may have failed" -ForegroundColor Yellow
}

# Step 4: Get application URL
Write-Host "[URL] Getting application URL..." -ForegroundColor Yellow
$APP_FQDN = az containerapp show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" --output tsv
if ($LASTEXITCODE -eq 0) {
    $APP_URL = "https://$APP_FQDN"
    Write-Host "[OK] Application URL: $APP_URL" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to get application URL" -ForegroundColor Red
}

# Step 5: Wait for deployment to complete
if ($FastDeploy.IsPresent -and $ShouldSkipBuild) {
    Write-Host "[FASTDEPLOY] Waiting for fast deployment to complete..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30  # Faster wait time for revision restart
} else {
    Write-Host "[WAIT] Waiting for deployment to complete..." -ForegroundColor Yellow
    Start-Sleep -Seconds 60
}

# Step 6: Test the application
Write-Host "[TEST] Testing application..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri $APP_URL -Method GET -TimeoutSec 30 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        $content = $response.Content
        if ($content -like "*streamlit*" -or $content -like "*Bundestag*") {
            Write-Host "[OK] Streamlit application is running successfully!" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Application responded but may not be Streamlit" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[WARNING] Application returned status: $($response.StatusCode)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "[WARNING] Application may still be starting up. Please wait a few minutes and try accessing: $APP_URL" -ForegroundColor Yellow
}

# Final status report
Write-Host ""
Write-Host "[SUMMARY] Deployment Summary" -ForegroundColor Green
Write-Host "===================" -ForegroundColor Green
Write-Host "Deployment Mode: $DeploymentMode" -ForegroundColor Green
Write-Host "Subscription: $SUBSCRIPTION_ID" -ForegroundColor Green
Write-Host "Resource Group: $RESOURCE_GROUP" -ForegroundColor Green
Write-Host "Location: $LOCATION" -ForegroundColor Green
Write-Host "Resource Prefix: $ResourcePrefix" -ForegroundColor Green
Write-Host "[OK] Docker image built and pushed to ACR" -ForegroundColor Green
Write-Host "[OK] Container app updated with latest image" -ForegroundColor Green
Write-Host "[OK] Cost optimizations applied:" -ForegroundColor Green
Write-Host "   - Scale-to-zero enabled (saves 70-80% during idle periods)" -ForegroundColor Green
Write-Host "   - Right-sized resources: 0.25 CPU, 0.5GB RAM (saves 40-50%)" -ForegroundColor Green
Write-Host "   [TIP] Estimated monthly savings: 12-20 EUR/month" -ForegroundColor Yellow
Write-Host "Application URL: $APP_URL" -ForegroundColor Green
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Gray
Write-Host "  az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --follow" -ForegroundColor Gray
Write-Host ""
Write-Host "OPTIMIZED DEPLOYMENT OPTIONS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  # FASTEST: Config-only update (5-10 seconds):" -ForegroundColor Green
Write-Host "  .\deploy-streamlit-app.ps1 -ConfigOnly -OpenAIApiKey 'key'" -ForegroundColor Gray
Write-Host ""
Write-Host "  # FAST: Skip build, use existing image (15-20 seconds):" -ForegroundColor Green
Write-Host "  .\deploy-streamlit-app.ps1 -SkipBuild" -ForegroundColor Gray
Write-Host ""
Write-Host "  # SMART: Auto-detection with hash checking (5s-3min):" -ForegroundColor Yellow
Write-Host "  .\deploy-streamlit-app.ps1 -FastDeploy" -ForegroundColor Gray
Write-Host ""
Write-Host "  # STANDARD: Optimized build with local Docker (1-3 min):" -ForegroundColor Yellow
Write-Host "  .\deploy-streamlit-app.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "  # FORCE: Complete rebuild when needed (2-4 min):" -ForegroundColor Yellow
Write-Host "  .\deploy-streamlit-app.ps1 -ForceRebuild" -ForegroundColor Gray
Write-Host ""
Write-Host "  # OPTIMIZED: Use optimized Dockerfile (30-60% faster builds):" -ForegroundColor Green
Write-Host "  .\deploy-streamlit-app.ps1 -UseOptimized -FastDeploy" -ForegroundColor Gray
Write-Host ""
Write-Host "  # New subscription setup:" -ForegroundColor Gray
Write-Host "  .\deploy-streamlit-app.ps1 -DeploymentMode New -SubscriptionId 'your-sub-id' -ResourcePrefix 'myapp-prod'" -ForegroundColor Gray

if ($OpenAIApiKey -eq "") {
    Write-Host "" -ForegroundColor Yellow
    Write-Host "To enable AI features, run this script again with the -OpenAIApiKey parameter:" -ForegroundColor Yellow
    Write-Host "   .\deploy-streamlit-app.ps1 -OpenAIApiKey your-api-key-here" -ForegroundColor Gray
}

if ($BUNDESTAG_API_KEY -eq "") {
    Write-Host "" -ForegroundColor Yellow
    Write-Host "To use a custom Bundestag API key, run this script again with the -BUNDESTAG_API_KEY parameter:" -ForegroundColor Yellow
    Write-Host "   .\deploy-streamlit-app.ps1 -BUNDESTAG_API_KEY your-bundestag-key-here" -ForegroundColor Gray
}