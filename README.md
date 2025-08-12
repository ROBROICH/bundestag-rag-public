# Bundestag RAG Application

A Retrieval-Augmented Generation (RAG) application for searching and analyzing German Bundestag documents.

## Features

- **Document Search**: Search through Bundestag documents with advanced filtering
- **AI-Powered Summaries**: Get intelligent summaries of search results
- **Analytics**: Visualize document statistics and trends
- **Multi-Model Support**: Works with OpenAI GPT and Azure OpenAI models

## Quick Start

### Prerequisites

- Python 3.9+
- Docker (optional, for containerized deployment)
- OpenAI API key or Azure OpenAI credentials

### Installation

1. Clone the repository:
```bash
git clone https://github.com/roman-broich/bundestag-rag-public.git
cd bundestag-rag-public
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your API keys:
   - Copy `config.json.example` to `config.json`
   - Add your OpenAI or Azure OpenAI credentials

4. Run the application:
```bash
streamlit run src/web/streamlit_app_modular.py
```

### Docker Deployment

```bash
docker-compose up -d
```

## Configuration

Edit `config.json` to configure:
- API endpoints and keys
- Model selection
- Search parameters
- UI preferences

## Architecture

- **Frontend**: Streamlit-based web interface
- **Search Engine**: Advanced document retrieval with caching
- **AI Integration**: Multi-model support for document analysis
- **Analytics**: Real-time document statistics and visualizations

## License

MIT License

## Contact

For questions or support, please open an issue on GitHub.
