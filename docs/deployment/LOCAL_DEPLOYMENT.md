# Local Deployment Guide

This guide provides step-by-step instructions for setting up and running the Bundestag RAG API application locally for development and testing.

## 🎯 Overview

Local deployment is ideal for:
- Development and debugging
- Testing new features
- Learning and experimentation
- Offline development

## 📋 Prerequisites

### Required Software
- **Python 3.11 or higher** ([Download Python](https://www.python.org/downloads/))
- **Git** ([Download Git](https://git-scm.com/downloads))
- **PowerShell** (Windows) or **Terminal** (macOS/Linux)

### Optional Software
- **Docker Desktop** ([Download Docker](https://www.docker.com/products/docker-desktop/)) - for containerized local development
- **Visual Studio Code** ([Download VS Code](https://code.visualstudio.com/)) - recommended IDE

### Required Accounts
- **OpenAI Account** with API access ([OpenAI Platform](https://platform.openai.com/))

## 🚀 Quick Start (5 Minutes)

### Method 1: Direct Python Setup (Recommended)

1. **Clone or navigate to the project:**
   ```powershell
   cd bundestag-rag-api
   ```

2. **Create Python virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Create environment file:**
   ```powershell
   # Copy the template
   Copy-Item .env.template .env
   
   # Edit .env file and add your OpenAI API key
   notepad .env
   ```

5. **Run the application:**
   ```powershell
   # Streamlit web application
   streamlit run src/web/streamlit_app_modular.py
   
   # OR CLI application
   python main.py interactive
   ```

6. **Access the application:**
   - **Web UI**: http://localhost:8501
   - **CLI**: Interactive prompts in terminal

### Method 2: Automated Setup Script

1. **Navigate to project directory:**
   ```powershell
   cd "C:\Users\robroich\OneDrive - Microsoft\01_ITZ\02_Bundes_ChatGPT\bundestag-rag-api"
   ```

2. **Run automated setup:**
   ```powershell
   .\deployment\scripts\setup-local-dev.ps1
   ```

3. **Follow the prompts to:**
   - Set up Python virtual environment
   - Install dependencies
   - Configure environment variables
   - Start the application

## 🐳 Docker-based Local Development

### Quick Docker Setup

1. **Build the Docker image:**
   ```powershell
   docker build -f deployment/docker/Dockerfile -t bundestag-rag-api:local .
   ```

2. **Run the container:**
   ```powershell
   docker run -p 8501:8501 `
     -e OPENAI_API_KEY="your-api-key-here" `
     -e STREAMLIT_SERVER_HEADLESS=true `
     bundestag-rag-api:local
   ```

3. **Access the application:**
   - **Web UI**: http://localhost:8501

### Docker Compose (Advanced)

1. **Create docker-compose.yml:**
   ```yaml
   version: '3.8'
   services:
     bundestag-rag-api:
       build:
         context: .
         dockerfile: deployment/docker/Dockerfile
       ports:
         - "8501:8501"
       environment:
         - OPENAI_API_KEY=${OPENAI_API_KEY}
         - STREAMLIT_SERVER_HEADLESS=true
         - STREAMLIT_SERVER_ENABLE_CORS=false
         - STREAMLIT_SERVER_ADDRESS=0.0.0.0
         - STREAMLIT_SERVER_PORT=8501
       volumes:
         - ./data:/app/data
         - ./logs:/app/logs
   ```

2. **Run with Docker Compose:**
   ```powershell
   docker-compose up --build
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root with:

```env
# Required - OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Optional - Streamlit Configuration
STREAMLIT_SERVER_HEADLESS=false
STREAMLIT_SERVER_ENABLE_CORS=true
STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true
STREAMLIT_SERVER_ADDRESS=127.0.0.1
STREAMLIT_SERVER_PORT=8501

# Optional - Application Configuration
CACHE_ENABLED=true
LOG_LEVEL=INFO
MAX_TEXT_LENGTH=32000
CHUNK_SIZE=8000
CHUNK_OVERLAP=200

# Optional - Development Configuration
DEVELOPMENT_MODE=true
DEBUG_API_CALLS=false
```

### Configuration Files

#### Streamlit Configuration
Create `.streamlit/config.toml`:
```toml
[server]
headless = false
enableCORS = true
enableXsrfProtection = true
address = "127.0.0.1"
port = 8501

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
```

#### Python Configuration
Ensure `requirements.txt` includes all necessary dependencies:
```
streamlit>=1.28.0
openai>=1.0.0
requests>=2.31.0
pydantic>=2.0.0
python-dotenv>=1.0.0
PyPDF2>=3.0.0
chromadb>=0.4.0
pandas>=2.0.0
numpy>=1.24.0
```

## 🧪 Testing Your Local Setup

### Basic Functionality Tests

1. **Test API Connection:**
   ```powershell
   python main.py test
   ```

2. **Test Examples:**
   ```powershell
   python main.py examples
   ```

3. **Test Streamlit Application:**
   - Start: `streamlit run src/web/streamlit_app_modular.py`
   - Visit: http://localhost:8501
   - Upload a test PDF document
   - Generate a summary

### Feature-Specific Tests

1. **Test OpenAI Integration:**
   ```powershell
   python -c "from src.web.openai_handler import OpenAIHandler; handler = OpenAIHandler(); print('OpenAI connection:', handler.client.models.list().data[0].id)"
   ```

2. **Test Document Processing:**
   ```powershell
   python tests/test_citizen_impact.py
   ```

3. **Test Web Interface:**
   - Upload a PDF document
   - Generate AI summary
   - Test citizen impact analysis
   - Verify modal functionality

## 🐛 Troubleshooting

### Common Issues and Solutions

#### Python Environment Issues

**Problem**: `ModuleNotFoundError` or import errors
```powershell
# Solution: Reinstall dependencies in virtual environment
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

**Problem**: Python version compatibility
```powershell
# Solution: Check Python version
python --version
# Ensure it's 3.11 or higher
```

#### OpenAI API Issues

**Problem**: API key errors
```powershell
# Solution: Verify API key format and validity
python -c "import openai; client = openai.OpenAI(); print(client.models.list().data[0].id)"
```

**Problem**: Rate limiting or quota issues
- Check your OpenAI account usage and limits
- Consider using a different model or reducing request frequency

#### Streamlit Issues

**Problem**: Port already in use
```powershell
# Solution: Use different port
streamlit run src/web/streamlit_app_modular.py --server.port 8502
```

**Problem**: Browser doesn't open automatically
- Manually navigate to http://localhost:8501
- Check firewall settings

#### File Path Issues

**Problem**: File not found errors
```powershell
# Solution: Check current directory
Get-Location
# Should be in the project root directory
```

#### Docker Issues

**Problem**: Docker build fails
```powershell
# Solution: Clean Docker cache
docker system prune -a
docker build --no-cache -f deployment/docker/Dockerfile -t bundestag-rag-api:local .
```

**Problem**: Container won't start
```powershell
# Solution: Check container logs
docker logs <container-id>
```

### Development Tips

#### Hot Reloading
Streamlit automatically reloads when you save Python files. For best development experience:
1. Keep the Streamlit server running
2. Edit files in your IDE
3. Save changes to see immediate updates

#### Debugging
Enable debug mode for detailed error messages:
```python
# Add to your .env file
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

#### Performance Optimization
For faster local development:
```python
# Add to your .env file
CACHE_ENABLED=true
DEVELOPMENT_MODE=true
```

## 📁 Local File Structure

When running locally, the application creates these directories:

```
bundestag-rag-api/
├── .env                       # Your environment variables
├── .streamlit/                # Streamlit configuration
│   └── config.toml           # Streamlit settings
├── venv/                      # Python virtual environment
├── data/                      # Application data
│   ├── cache/                # API response cache
│   └── uploads/              # Uploaded documents
├── logs/                      # Application logs
│   └── app.log              # Main log file
└── temp/                      # Temporary files
    └── processing/           # Document processing temp files
```

## 🔄 Development Workflow

### Recommended Development Process

1. **Start Development Session:**
   ```powershell
   cd "C:\Users\robroich\OneDrive - Microsoft\01_ITZ\02_Bundes_ChatGPT\bundestag-rag-api"
   .\venv\Scripts\Activate.ps1
   streamlit run src/web/streamlit_app_modular.py
   ```

2. **Make Changes:**
   - Edit Python files in your IDE
   - Streamlit will automatically reload on save
   - Test changes in the browser

3. **Test Changes:**
   ```powershell
   # Run specific tests
   python tests/test_citizen_impact.py
   
   # Test API functionality
   python main.py test
   ```

4. **Commit Changes:**
   ```powershell
   git add .
   git commit -m "Your change description"
   ```

### Code Organization Tips

- **Web UI**: Edit files in `src/web/`
- **API Logic**: Edit files in `src/api/`
- **Configuration**: Edit `config/settings.py`
- **Tests**: Add tests in `tests/`

## 🌐 Accessing Your Local Application

### Web Interface
- **URL**: http://localhost:8501
- **Features**: Full Streamlit interface with document upload, AI summaries, citizen impact analysis

### CLI Interface
```powershell
# Interactive mode
python main.py interactive

# Direct search
python main.py search drucksache --title "Klimaschutz" --limit 5

# API testing
python main.py test
```

### API Endpoints (if running API server)
- **Health Check**: http://localhost:8000/health
- **Search**: http://localhost:8000/api/search
- **Summary**: http://localhost:8000/api/summarize

## 📊 Performance Monitoring

### Local Monitoring Tools

1. **Streamlit Stats:**
   - Built-in performance metrics in Streamlit interface
   - Memory usage and execution time

2. **Python Profiling:**
   ```powershell
   python -m cProfile -o profile.stats main.py
   ```

3. **Log Analysis:**
   ```powershell
   Get-Content logs/app.log -Tail 50
   ```

## 🔐 Security for Local Development

### Best Practices

1. **Environment Variables:**
   - Never commit `.env` files
   - Use different API keys for development and production

2. **Local Network:**
   - By default, Streamlit only listens on localhost (127.0.0.1)
   - Safe for local development

3. **API Keys:**
   - Use development/test API keys when available
   - Monitor API usage during development

## 🆘 Getting Help

### If You're Stuck

1. **Check logs:**
   ```powershell
   Get-Content logs/app.log -Tail 50
   ```

2. **Verify environment:**
   ```powershell
   python --version
   pip list | findstr streamlit
   ```

3. **Test basic functionality:**
   ```powershell
   python main.py test
   ```

4. **Reset environment:**
   ```powershell
   Remove-Item -Recurse -Force venv
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

### Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Python Virtual Environments](https://docs.python.org/3/tutorial/venv.html)

---

**Happy Developing!** 🚀

For production deployment, see [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md).
