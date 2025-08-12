# Azure Deployment Guide

This guide provides comprehensive instructions for deploying the Bundestag RAG API application to Microsoft Azure using Azure Container Apps.

## 🎯 Overview

Azure deployment provides:
- **Production-ready hosting** with auto-scaling
- **HTTPS endpoints** with managed certificates
- **High availability** and reliability
- **Cost-effective** serverless container hosting
- **Integrated monitoring** and logging

## 🏗️ Current Production Deployment

### Live Application
- **URL**: https://bundestag-rag-api-basic.politeocean-4adf01f2.westeurope.azurecontainerapps.io/
- **Status**: ✅ **Live and Running**
- **Last Updated**: July 31, 2025
- **Infrastructure**: Complete and operational

### Azure Resources
- **Resource Group**: `rg-bundestag-rag-basic`
- **Location**: West Europe
- **Container Registry**: `acrbundestagbasic.azurecr.io`
- **Container Environment**: `bundestag-env-basic`
- **Container App**: `bundestag-rag-api-basic`

## 📋 Prerequisites

### Required Software
- **Azure CLI** ([Install Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli))
- **PowerShell** (Windows) or **PowerShell Core** (cross-platform)
- **Git** for version control (optional but recommended)

### Required Accounts & Access
- **Azure Subscription** with Contributor access
- **OpenAI Account** with API key ([OpenAI Platform](https://platform.openai.com/))

### Verification
```powershell
# Verify Azure CLI installation
az --version

# Login to Azure
az login

# Verify subscription
az account show
```

## 🚀 Quick Deployment (5 Minutes)

### Method 1: Automated PowerShell Script (Recommended)

1. **Navigate to project directory:**
   ```powershell
   cd "C:\Users\robroich\OneDrive - Microsoft\01_ITZ\02_Bundes_ChatGPT\bundestag-rag-api"
   ```

2. **Run deployment script:**
   ```powershell
   .\deployment\scripts\deploy-streamlit-app.ps1 -OpenAIApiKey "your-openai-api-key-here"
   ```

3. **Verify deployment:**
   ```powershell
   .\deployment\scripts\verify-deployment.ps1
   ```

**What the script does:**
- ✅ Builds Docker image using Azure Container Registry
- ✅ Updates existing Container App with new image
- ✅ Configures all necessary environment variables
- ✅ Provides application URL and status

### Method 2: GitHub Actions CI/CD

If you prefer automated deployments with version control:

1. **Push code to GitHub repository**
2. **Configure GitHub secrets:**
   - `AZURE_CREDENTIALS`: Azure service principal JSON
   - `OPENAI_API_KEY`: Your OpenAI API key
3. **Push changes to trigger deployment**

## 🔧 Infrastructure Setup (For New Deployments)

If you need to create infrastructure from scratch:

### Option A: Using Bicep Templates

1. **Deploy infrastructure:**
   ```powershell
   az deployment group create `
     --resource-group rg-bundestag-rag-basic `
     --template-file deployment/azure/azure-app-service.bicep `
     --parameters location=westeurope
   ```

### Option B: Using Azure CLI Commands

1. **Create resource group:**
   ```powershell
   az group create --name rg-bundestag-rag-basic --location westeurope
   ```

2. **Create container registry:**
   ```powershell
   az acr create `
     --resource-group rg-bundestag-rag-basic `
     --name acrbundestagbasic `
     --sku Basic `
     --admin-enabled true
   ```

3. **Create container apps environment:**
   ```powershell
   az containerapp env create `
     --name bundestag-env-basic `
     --resource-group rg-bundestag-rag-basic `
     --location westeurope
   ```

4. **Create container app:**
   ```powershell
   az containerapp create `
     --name bundestag-rag-api-basic `
     --resource-group rg-bundestag-rag-basic `
     --environment bundestag-env-basic `
     --image mcr.microsoft.com/azuredocs/containerapps-helloworld:latest `
     --target-port 8501 `
     --ingress external `
     --min-replicas 0 `
     --max-replicas 3 `
     --cpu 0.5 `
     --memory 1Gi
   ```

## 🐳 Docker Image Management

### Building Images

#### Option A: Azure Container Registry Build (Recommended)
```powershell
# Build image in Azure (no local Docker required)
az acr build `
  --registry acrbundestagbasic `
  --image bundestag-rag-api:latest `
  --file deployment/docker/Dockerfile .
```

#### Option B: Local Docker Build
```powershell
# Build locally and push to ACR
docker build -f deployment/docker/Dockerfile -t bundestag-rag-api:latest .
az acr login --name acrbundestagbasic
docker tag bundestag-rag-api:latest acrbundestagbasic.azurecr.io/bundestag-rag-api:latest
docker push acrbundestagbasic.azurecr.io/bundestag-rag-api:latest
```

### Managing Container Registry

```powershell
# Get registry credentials
$ACR_SERVER = az acr show --name acrbundestagbasic --resource-group rg-bundestag-rag-basic --query "loginServer" --output tsv
$ACR_USERNAME = az acr credential show --name acrbundestagbasic --resource-group rg-bundestag-rag-basic --query "username" --output tsv
$ACR_PASSWORD = az acr credential show --name acrbundestagbasic --resource-group rg-bundestag-rag-basic --query "passwords[0].value" --output tsv

# List images
az acr repository list --name acrbundestagbasic --output table

# List tags for specific image
az acr repository show-tags --name acrbundestagbasic --repository bundestag-rag-api --output table
```

## ⚙️ Configuration Management

### Environment Variables

#### Required Variables
```powershell
az containerapp update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --set-env-vars `
    OPENAI_API_KEY=your-openai-api-key-here `
    STREAMLIT_SERVER_HEADLESS=true `
    STREAMLIT_SERVER_ENABLE_CORS=false `
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false `
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 `
    STREAMLIT_SERVER_PORT=8501
```

#### Optional Variables
```powershell
az containerapp update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --set-env-vars `
    CACHE_ENABLED=true `
    LOG_LEVEL=INFO `
    MAX_TEXT_LENGTH=32000 `
    CHUNK_SIZE=8000 `
    CHUNK_OVERLAP=200
```

### Using Azure Key Vault (Recommended for Production)

1. **Create Key Vault:**
   ```powershell
   az keyvault create `
     --name kv-bundestag-basic `
     --resource-group rg-bundestag-rag-basic `
     --location westeurope
   ```

2. **Store secrets:**
   ```powershell
   az keyvault secret set `
     --vault-name kv-bundestag-basic `
     --name openai-api-key `
     --value "your-openai-api-key"
   ```

3. **Configure Container App to use Key Vault:**
   ```powershell
   az containerapp update `
     --name bundestag-rag-api-basic `
     --resource-group rg-bundestag-rag-basic `
     --secrets openai-key=keyvaultref:https://kv-bundestag-basic.vault.azure.net/secrets/openai-api-key,identityref:/subscriptions/your-subscription/resourceGroups/rg-bundestag-rag-basic/providers/Microsoft.ManagedIdentity/userAssignedIdentities/your-identity `
     --set-env-vars OPENAI_API_KEY=secretref:openai-key
   ```

## 🔄 Application Updates

### Updating the Application

1. **Build new image:**
   ```powershell
   az acr build --registry acrbundestagbasic --image bundestag-rag-api:latest --file deployment/docker/Dockerfile .
   ```

2. **Update container app:**
   ```powershell
   az containerapp update `
     --name bundestag-rag-api-basic `
     --resource-group rg-bundestag-rag-basic `
     --image acrbundestagbasic.azurecr.io/bundestag-rag-api:latest
   ```

### Zero-Downtime Updates

Container Apps supports zero-downtime deployments with traffic splitting:

```powershell
# Create new revision with new image
az containerapp update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --image acrbundestagbasic.azurecr.io/bundestag-rag-api:new-version

# Split traffic between revisions
az containerapp revision set-mode `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --mode multiple

# Set traffic weights (50% old, 50% new)
az containerapp ingress traffic set `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --revision-weight old-revision=50 new-revision=50
```

## 📊 Monitoring and Logging

### Application Logs

```powershell
# View recent logs
az containerapp logs show `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --tail 50

# Follow live logs
az containerapp logs show `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --follow
```

### Application Metrics

```powershell
# Check application status
az containerapp show `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --query "properties.runningStatus"

# View revision history
az containerapp revision list `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --output table
```

### Azure Monitor Integration

1. **Enable Application Insights:**
   ```powershell
   az monitor app-insights component create `
     --app bundestag-insights `
     --location westeurope `
     --resource-group rg-bundestag-rag-basic
   ```

2. **Configure Container App:**
   ```powershell
   $INSTRUMENTATION_KEY = az monitor app-insights component show --app bundestag-insights --resource-group rg-bundestag-rag-basic --query "instrumentationKey" --output tsv
   
   az containerapp update `
     --name bundestag-rag-api-basic `
     --resource-group rg-bundestag-rag-basic `
     --set-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$INSTRUMENTATION_KEY"
   ```

## 🔧 Scaling Configuration

### Auto-scaling Rules

```powershell
# Configure CPU-based scaling
az containerapp update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --min-replicas 0 `
  --max-replicas 10 `
  --scale-rule-name cpu-scale `
  --scale-rule-type cpu `
  --scale-rule-metadata targetCpuUtilization=70
```

### Manual Scaling

```powershell
# Scale to specific number of replicas
az containerapp revision copy `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --min-replicas 2 `
  --max-replicas 5
```

## 🔐 Security Configuration

### Network Security

```powershell
# Configure ingress settings
az containerapp ingress update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --type external `
  --allow-insecure false `
  --target-port 8501
```

### Authentication (Optional)

```powershell
# Enable Azure Active Directory authentication
az containerapp auth update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --enable-token-store true `
  --action Return401
```

## 🐛 Troubleshooting

### Common Issues and Solutions

#### Issue 1: OpenAI API Key Problems

**Symptoms:**
- HTTP 401 errors from OpenAI
- "Incorrect API key provided" messages

**Solution:**
```powershell
# Use the dedicated fix script
.\deployment\scripts\fix-openai-key.ps1 -OpenAIApiKey "your-correct-api-key"
```

**What this script does:**
- Validates API key format
- Deactivates conflicting old revisions
- Updates environment variables atomically
- Forces container restart
- Verifies the fix

#### Issue 2: Application Won't Start

**Symptoms:**
- Container restarts continuously
- HTTP 502/503 errors

**Solution:**
```powershell
# Check container logs
az containerapp logs show --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic --tail 100

# Restart the application
az containerapp restart --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic
```

#### Issue 3: High Resource Usage

**Symptoms:**
- Slow response times
- Memory or CPU warnings

**Solution:**
```powershell
# Increase resource allocation
az containerapp update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --cpu 1.0 `
  --memory 2Gi
```

#### Issue 4: Multiple Revisions Conflicts

**Symptoms:**
- Inconsistent behavior
- Environment variable conflicts

**Solution:**
```powershell
# List all revisions
az containerapp revision list --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic --output table

# Deactivate old revisions (keep only latest)
az containerapp revision deactivate --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic --revision <old-revision-name>
```

### Emergency Procedures

#### Quick Health Check
```powershell
# Run comprehensive verification
.\deployment\scripts\verify-deployment.ps1
```

#### Complete Application Reset
```powershell
# 1. Build fresh image
az acr build --registry acrbundestagbasic --image bundestag-rag-api:emergency --file deployment/docker/Dockerfile .

# 2. Update with fresh image and clean environment
az containerapp update `
  --name bundestag-rag-api-basic `
  --resource-group rg-bundestag-rag-basic `
  --image acrbundestagbasic.azurecr.io/bundestag-rag-api:emergency `
  --set-env-vars `
    OPENAI_API_KEY=your-api-key `
    STREAMLIT_SERVER_HEADLESS=true `
    STREAMLIT_SERVER_ENABLE_CORS=false `
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false `
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 `
    STREAMLIT_SERVER_PORT=8501

# 3. Restart application
az containerapp restart --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic
```

## 💰 Cost Management

### Current Costs (Monthly Estimates)
- **Container Apps** (0.5 CPU, 1GB RAM): €15-25
- **Container Registry** (Basic): €4
- **Log Analytics**: €2-5
- **Application Insights** (optional): €5-10
- **Total**: €21-44 per month

### Cost Optimization Tips

1. **Scale to Zero:**
   ```powershell
   az containerapp update --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic --min-replicas 0
   ```

2. **Right-size Resources:**
   ```powershell
   # Monitor usage and adjust
   az containerapp update --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic --cpu 0.25 --memory 0.5Gi
   ```

3. **Use Reserved Capacity** (for consistent workloads)

4. **Clean up old images:**
   ```powershell
   az acr repository delete --name acrbundestagbasic --repository bundestag-rag-api --tag old-tag
   ```

## 🔄 CI/CD Pipeline Setup

### GitHub Actions Workflow

Create `.github/workflows/deploy-azure.yml`:

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [ main ]
  workflow_dispatch:

env:
  AZURE_CONTAINER_REGISTRY: acrbundestagbasic
  CONTAINER_APP_NAME: bundestag-rag-api-basic
  RESOURCE_GROUP: rg-bundestag-rag-basic
  IMAGE_NAME: bundestag-rag-api

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Azure Login
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Build and push image
      run: |
        az acr build --registry ${{ env.AZURE_CONTAINER_REGISTRY }} \
          --image ${{ env.IMAGE_NAME }}:${{ github.sha }} \
          --file deployment/docker/Dockerfile .
    
    - name: Update Container App
      run: |
        az containerapp update \
          --name ${{ env.CONTAINER_APP_NAME }} \
          --resource-group ${{ env.RESOURCE_GROUP }} \
          --image ${{ env.AZURE_CONTAINER_REGISTRY }}.azurecr.io/${{ env.IMAGE_NAME }}:${{ github.sha }} \
          --set-env-vars OPENAI_API_KEY="${{ secrets.OPENAI_API_KEY }}"
```

### Azure DevOps Pipeline

Create `azure-pipelines.yml`:

```yaml
trigger:
- main

variables:
  azureServiceConnection: 'azure-service-connection'
  resourceGroup: 'rg-bundestag-rag-basic'
  containerRegistry: 'acrbundestagbasic'
  containerApp: 'bundestag-rag-api-basic'
  imageName: 'bundestag-rag-api'

stages:
- stage: Build
  jobs:
  - job: BuildAndPush
    pool:
      vmImage: 'ubuntu-latest'
    steps:
    - task: AzureCLI@2
      displayName: 'Build and push image'
      inputs:
        azureSubscription: $(azureServiceConnection)
        scriptType: 'bash'
        scriptLocation: 'inlineScript'
        inlineScript: |
          az acr build --registry $(containerRegistry) \
            --image $(imageName):$(Build.BuildId) \
            --file deployment/docker/Dockerfile .

- stage: Deploy
  dependsOn: Build
  jobs:
  - job: UpdateContainerApp
    pool:
      vmImage: 'ubuntu-latest'
    steps:
    - task: AzureCLI@2
      displayName: 'Update Container App'
      inputs:
        azureSubscription: $(azureServiceConnection)
        scriptType: 'bash'
        scriptLocation: 'inlineScript'
        inlineScript: |
          az containerapp update \
            --name $(containerApp) \
            --resource-group $(resourceGroup) \
            --image $(containerRegistry).azurecr.io/$(imageName):$(Build.BuildId) \
            --set-env-vars OPENAI_API_KEY="$(OPENAI_API_KEY)"
```

## 🌐 Custom Domain Setup (Optional)

### Configure Custom Domain

1. **Add custom domain:**
   ```powershell
   az containerapp hostname add `
     --name bundestag-rag-api-basic `
     --resource-group rg-bundestag-rag-basic `
     --hostname yourdomain.com
   ```

2. **Configure DNS records:**
   - Create CNAME record pointing to the Container App URL
   - Verify domain ownership

3. **Bind SSL certificate:**
   ```powershell
   az containerapp hostname bind `
     --name bundestag-rag-api-basic `
     --resource-group rg-bundestag-rag-basic `
     --hostname yourdomain.com `
     --certificate your-certificate-id
   ```

## 📚 Additional Resources

### Azure Documentation
- [Azure Container Apps Documentation](https://docs.microsoft.com/en-us/azure/container-apps/)
- [Azure Container Registry Documentation](https://docs.microsoft.com/en-us/azure/container-registry/)
- [Azure CLI Reference](https://docs.microsoft.com/en-us/cli/azure/)

### Monitoring & Troubleshooting
- [Container Apps Monitoring](https://docs.microsoft.com/en-us/azure/container-apps/monitor)
- [Application Insights Integration](https://docs.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)

### Security Best Practices
- [Container Apps Security](https://docs.microsoft.com/en-us/azure/container-apps/security)
- [Azure Key Vault Integration](https://docs.microsoft.com/en-us/azure/key-vault/)

## 🆘 Support & Help

### Quick Help Commands

```powershell
# Application health check
Invoke-RestMethod -Uri "https://bundestag-rag-api-basic.politeocean-4adf01f2.westeurope.azurecontainerapps.io/" -Method GET

# Check deployment status
.\deployment\scripts\verify-deployment.ps1

# Fix common OpenAI issues
.\deployment\scripts\fix-openai-key.ps1 -OpenAIApiKey "your-key"

# View live logs
az containerapp logs show --name bundestag-rag-api-basic --resource-group rg-bundestag-rag-basic --follow
```

### Getting Support

1. **Check application logs first**
2. **Review this deployment guide**
3. **Run verification scripts**
4. **Check Azure service health**
5. **Review cost and quota limits**

---

**Deployment Status**: ✅ **Production Ready**  
**Application URL**: https://bundestag-rag-api-basic.politeocean-4adf01f2.westeurope.azurecontainerapps.io/  
**Last Updated**: August 2, 2025
