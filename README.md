# 🏛️ Bundestag.AI Lens

**Azure AI application making German parliamentary information accessible to everyone.**

**Note:  This project & platform is for educational and research purposes. Please respect the Bundestag DIP API terms of service when using this application. The code was generated with GenAI support, hence don't use in production**

## 👥 Who Benefits from This Platform

### 👥 Citizens & Civil Society
- Easilly understand 50+-page documents 
- No legal expertise required
- Direct access to government decisions
- Unbiased, standardized summaries
- AI-powered fact extraction
- Easier democratic participation


### 🏛️ Government & Administration
- Enhanced public access
- Increased citizen participation
- Reduced information office burden
- Digital government demonstration

## 🏗️ System Architecture

Our platform follows a three-service architecture:

### 🏛️ Data Source - German Bundestag API
Official parliamentary documents

### 🧠 Intelligence Engine - AI Analysis Service  
Plain-language summaries & impact analysis

### ☁️ User Interface - Web Platform
Real-time interactive features

## 🚀 Quick Start

### Local Development
```powershell
# 1. Clone and setup
git clone <repository-url>
cd bundestag-rag-api
.\deployment\local\setup-local.ps1

# 2. Configure API key
$env:OPENAI_API_KEY="your-openai-api-key-here"

# 3. Start the application
streamlit run src\web\streamlit_app_modular.py
```

**Access at**: http://localhost:8501

### Azure Deployment
```powershell
# Deploy to existing subscription
.\deployment\scripts\deploy-streamlit-app.ps1 -OpenAIApiKey "your-api-key"

# Deploy to new subscription
.\deployment\scripts\deploy-streamlit-app.ps1 -DeploymentMode New -SubscriptionId "your-sub-id" -ResourcePrefix "myapp-prod" -OpenAIApiKey "your-api-key"
```

## 📚 Documentation & Guides

### Deployment
- **[Azure Deployment Documentation](deployment/docs/deploy-streamlit-app-documentation.md)** - Comprehensive Azure Container Apps deployment guide
- **[Local Development Guide](docs/deployment/LOCAL_DEPLOYMENT.md)** - Local development environment setup

### Technical Documentation
- **[Architecture Documentation](docs/summaries/PROJECT_ORGANIZATION.md)** - System architecture and data flow
- **[API Documentation](https://dip.bundestag.de/über-dip/hilfe/api)** - Official Bundestag DIP API docs

## 🔗 Live Demo

**[Try the Live Application](https://bundestag-rag-api-basic.politeocean-4adf01f2.westeurope.azurecontainerapps.io/)**

## 🛠️ Features

### AI-Powered Analysis
- **Smart Chunking**: Documents intelligently split for optimal AI processing
- **German-Optimized**: Specialized for parliamentary and legal texts  
- **Citizen Impact**: AI analyzes how legislation affects everyday citizens
- **Cost-Efficient**: GPT-4o-mini model balances performance and cost

### Roadmap
- **Optimized prompts per document type**: Optimized prompt templates for different document types
- **Evaulations**: Risk and safety evaluators
- **GraphRAG**: Evaluation of potential Knowledge Graph


### Search & Analytics
- Multiple document types (Drucksachen, Vorgänge, Plenarprotokolle)
- Advanced filtering and search capabilities
- Real-time data visualization
- Export functionality

## ⚙️ Configuration

### Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key (required for AI features)
- `BUNDESTAG_API_KEY`: Your DIP API key (pre-configured)
- `LOG_LEVEL`: Logging level (default: INFO)

## 🧪 Testing

```powershell
# Test API connection
python main.py test

# Run unit tests
python -m pytest tests/

# Interactive CLI
python main.py interactive
```

## 🔗 Resources

- [Bundestag DIP API Documentation](https://dip.bundestag.de/über-dip/hilfe/api)
- [Terms of Service](https://dip.bundestag.de/über-dip/nutzungsbedingungen)
- [Live Demo Application](https://bundestag-rag-api-basic.politeocean-4adf01f2.westeurope.azurecontainerapps.io/)

## 📄 License

This project is for educational and research purposes. Please respect the Bundestag DIP API terms of service.

---

For deployment issues, see the [Azure Deployment Documentation](deployment/docs/deploy-streamlit-app-documentation.md) troubleshooting section.