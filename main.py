#!/usr/bin/env python3
"""
Main entry point for the Bundestag RAG API project

Usage:
    python main.py interactive    # Start interactive CLI
    python main.py web           # Start Streamlit web interface
    python main.py test          # Test API connection
    python main.py search        # Search documents
    python main.py examples      # Run basic examples
"""

import sys
import subprocess
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Bundestag RAG API")
        print("=" * 20)
        print("Usage:")
        print("  python main.py interactive    # Start interactive CLI")
        print("  python main.py web           # Start Streamlit web interface")
        print("  python main.py test          # Test API connection")
        print("  python main.py search        # Search documents")
        print("  python main.py examples      # Run basic examples")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "interactive":
        # Run the interactive CLI
        subprocess.run([sys.executable, "-m", "src.cli.query_tool", "interactive"])
    
    elif command == "web":
        # Run the Streamlit web interface
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "src/web/streamlit_app.py",
            "--server.headless", "false",
            "--server.address", "localhost",
            "--server.port", "8501"
        ])
    
    elif command == "test":
        # Test API connection
        subprocess.run([sys.executable, "-m", "src.cli.query_tool", "test-connection"])
    
    elif command == "search":
        # Run search with remaining arguments
        args = [sys.executable, "-m", "src.cli.query_tool", "search"] + sys.argv[2:]
        subprocess.run(args)
    
    elif command == "examples":
        # Run basic examples
        subprocess.run([sys.executable, "examples/basic_queries.py"])
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
