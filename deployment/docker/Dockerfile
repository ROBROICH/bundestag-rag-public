# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies in a single layer with cleaning
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && pip install --upgrade pip setuptools wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Create non-root user for security  
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy requirements first for optimal layer caching
COPY requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --disable-pip-version-check \
    -r requirements.txt \
    && pip cache purge \
    && find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete \
    && find /usr/local/lib/python3.11/site-packages -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Create necessary directories and set permissions early
RUN mkdir -p data/cache data/vectors logs && \
    chown -R appuser:appuser /app

# Copy files in order of change frequency (most stable first for better caching)
# 1. Configuration and deployment files (least likely to change)
COPY deployment/ ./deployment/

# 2. Documentation (rarely changes)  
COPY docs/ ./docs/

# 3. Data files (occasionally changes)
COPY data/ ./data/

# 4. Configuration and Python source code LAST (changes most frequently - separate layers for better caching)
# Copy configuration first
COPY config/ ./config/

# Copy stable modules first (API, CLI, security, utils)
COPY src/__init__.py ./src/
COPY src/api/ ./src/api/
COPY src/cli/ ./src/cli/
COPY src/security/ ./src/security/
COPY src/utils/ ./src/utils/

# Copy web interface last (changes most during development)
COPY src/web/ ./src/web/

# Set final permissions
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port for Streamlit
EXPOSE 8501

# Add health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Set environment variables for Streamlit (Secure Configuration)
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_CORS=true
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=true
ENV STREAMLIT_SERVER_MAX_UPLOAD_SIZE=50
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Command to run the application
CMD ["streamlit", "run", "src/web/streamlit_app_modular.py", "--server.port=8501", "--server.address=0.0.0.0"]
