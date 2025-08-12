# Deploy Streamlit App to Azure Container Apps - Documentation

## Overview

The `deploy-streamlit-app.ps1` script automates the deployment of the Bundestag RAG API Streamlit application to Azure Container Apps. It supports both new deployments (creating all required Azure resources) and updates to existing deployments.

## Features

- **Flexible Deployment Modes**: Deploy to new or existing Azure resources
- **Smart Defaults**: Auto-generates resource names based on a configurable prefix
- **Cost Optimization**: Implements scale-to-zero and right-sizing for cost savings
- **Error Handling**: Comprehensive validation and error reporting
- **Resource Management**: Creates and validates Azure resources automatically

## Prerequisites

- Azure CLI installed and configured
- PowerShell 5.1 or later
- Azure subscription with appropriate permissions
- Docker (if building locally)
- Project must be run from the repository root directory

## Usage

### Basic Usage

```powershell
# Deploy to existing resources (default mode)
.\deploy-streamlit-app.ps1

# Deploy with OpenAI API key
.\deploy-streamlit-app.ps1 -OpenAIApiKey "your-api-key-here"
```

### New Deployment (Creates All Resources)

```powershell
# Use all defaults with custom prefix
.\deploy-streamlit-app.ps1 -DeploymentMode New -SubscriptionId "your-sub-id" -ResourcePrefix "myapp-prod"

# Specify individual resource names
.\deploy-streamlit-app.ps1 -DeploymentMode New -SubscriptionId "your-sub-id" -ResourceGroup "rg-custom" -RegistryName "acrcustom"
```

### Update Existing Deployment

```powershell
# Update existing deployment with new code
.\deploy-streamlit-app.ps1 -DeploymentMode Existing -ResourceGroup "existing-rg" -RegistryName "existingacr"
```

## Parameters

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `OpenAIApiKey` | String | "" | No | OpenAI API key for AI features |
| `SubscriptionId` | String | "d99d5ab1-2ca2-4463-808e-a4a8ecff486f" | No | Azure subscription ID |
| `ResourceGroup` | String | Auto-generated | No | Resource group name |
| `Location` | String | "westeurope" | No | Azure region for resources |
| `ContainerAppName` | String | Auto-generated | No | Container app name |
| `RegistryName` | String | Auto-generated | No | Container registry name |
| `ImageName` | String | "bundestag-rag-api" | No | Docker image name |
| `ImageTag` | String | "latest" | No | Docker image tag |
| `DeploymentMode` | String | "Existing" | No | "New" or "Existing" |
| `EnvironmentName` | String | Auto-generated | No | Container Apps environment name |
| `ResourcePrefix` | String | "bundestag-rag" | No | Prefix for auto-generated names |

## Auto-Generated Resource Names

When resource names are not explicitly provided, they are generated using the `ResourcePrefix`:

- **Resource Group**: `rg-{ResourcePrefix}`
- **Container App**: `{ResourcePrefix}-app`
- **Container Registry**: `acr{ResourcePrefix}` (hyphens removed)
- **Environment**: `{ResourcePrefix}-env`

### Example with ResourcePrefix "myapp-prod":
- Resource Group: `rg-myapp-prod`
- Container App: `myapp-prod-app`
- Container Registry: `acrmyappprod`
- Environment: `myapp-prod-env`

## Deployment Modes

### New Deployment Mode
- Creates all Azure resources if they don't exist
- Validates subscription and permissions
- Sets up Container Apps environment with optimal settings
- Configures scale-to-zero and cost optimizations

### Existing Deployment Mode (Default)
- Validates that all required resources exist
- Updates existing container app with new image
- Applies cost optimizations to existing resources
- Fails gracefully if resources are missing

## Cost Optimizations

The script applies several cost-saving measures:

1. **Scale-to-Zero**: `min-replicas = 0`
   - Saves 70-80% during idle periods
   - App scales up automatically when requests arrive

2. **Right-Sizing**: `0.25 CPU, 0.5GB RAM`
   - Saves 40-50% compared to default sizing
   - Suitable for most Streamlit applications

3. **Estimated Savings**: €12-20/month compared to always-on Standard tier

## Environment Variables

The script automatically configures these Streamlit-specific environment variables:

- `STREAMLIT_SERVER_HEADLESS=true`
- `STREAMLIT_SERVER_ENABLE_CORS=false`
- `STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false`
- `STREAMLIT_SERVER_ADDRESS=0.0.0.0`
- `STREAMLIT_SERVER_PORT=8501`
- `OPENAI_API_KEY={provided key}` (if specified)

## File Requirements

The script expects these files to exist in the repository:

- `deployment/docker/Dockerfile` - Docker configuration
- `src/web/streamlit_app_modular.py` - Main Streamlit application

## Error Handling

The script includes comprehensive error handling for common scenarios:

- Azure CLI authentication issues
- Missing or invalid subscriptions
- Resource creation failures
- Docker build errors
- Network connectivity issues
- Missing required files

## Output and Logging

The script provides detailed console output with color-coded messages:

- `[DEPLOY]` - Main deployment actions
- `[INFO]` - Informational messages
- `[OK]` - Successful operations
- `[ERROR]` - Error conditions
- `[WARNING]` - Warning messages
- `[CREATE]` - Resource creation
- `[CHECK]` - Validation steps
- `[BUILD]` - Docker build operations
- `[UPDATE]` - Container app updates
- `[TEST]` - Application testing

## Post-Deployment

After successful deployment, the script provides:

1. **Application URL**: Direct link to the deployed Streamlit app
2. **Logging Command**: Command to view container logs
3. **Usage Examples**: Examples for future deployments
4. **Cost Summary**: Expected cost savings

### Viewing Logs

```powershell
az containerapp logs show --name {container-app-name} --resource-group {resource-group} --follow
```

## Troubleshooting

### Common Issues

1. **Authentication Error**
   ```
   [ERROR] Failed to set subscription
   ```
   **Solution**: Run `az login` and ensure you have access to the subscription

2. **Resource Already Exists**
   ```
   [ERROR] Container registry 'name' does not exist
   ```
   **Solution**: Use `-DeploymentMode New` or specify existing resource names

3. **Docker Build Failure**
   ```
   [ERROR] Failed to build Docker image
   ```
   **Solution**: Check Dockerfile and ensure all dependencies are available

4. **Missing Files**
   ```
   [ERROR] Dockerfile not found
   ```
   **Solution**: Run script from repository root directory

### Validation Steps

The script automatically validates:
- Azure subscription access
- Resource group existence
- Container registry availability
- Container Apps environment
- Required project files

## Security Considerations

- OpenAI API keys are passed as environment variables (not stored in images)
- Container registry uses admin credentials (consider using managed identity for production)
- All Azure resources use HTTPS endpoints
- No sensitive information is logged to console

## Performance Notes

- Initial deployment: 5-10 minutes (resource creation + build)
- Update deployment: 2-3 minutes (build + update only)
- Cold start: 10-30 seconds (after scale-to-zero)
- Build caching: Subsequent builds are faster due to layer caching

## Example Workflows

### Development Environment
```powershell
.\deploy-streamlit-app.ps1 -DeploymentMode New -ResourcePrefix "bundestag-dev" -SubscriptionId "dev-subscription-id"
```

### Staging Environment
```powershell
.\deploy-streamlit-app.ps1 -DeploymentMode New -ResourcePrefix "bundestag-staging" -Location "northeurope"
```

### Production Environment
```powershell
.\deploy-streamlit-app.ps1 -DeploymentMode New -ResourcePrefix "bundestag-prod" -OpenAIApiKey "prod-api-key"
```

### Regular Updates
```powershell
.\deploy-streamlit-app.ps1 -ResourceGroup "rg-bundestag-prod" -OpenAIApiKey "updated-api-key"
```

## Integration with CI/CD

The script can be integrated into GitHub Actions or Azure DevOps pipelines:

```yaml
- name: Deploy to Azure Container Apps
  run: |
    .\deployment\scripts\deploy-streamlit-app.ps1 -DeploymentMode Existing -ResourceGroup "${{ vars.RESOURCE_GROUP }}" -OpenAIApiKey "${{ secrets.OPENAI_API_KEY }}"
  shell: pwsh
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify all prerequisites are met
3. Review Azure CLI and PowerShell versions
4. Check Azure subscription permissions