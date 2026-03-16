# OpenAI Configuration
import os

# SECURITY: API key should NEVER be hardcoded. Use environment variables only.
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# OpenAI Model Configuration — GPT-5 mini
# Specs: 400K context, 128K max output, $0.25/$2.00 per 1M tokens
# Docs: https://developers.openai.com/api/docs/models/gpt-5-mini
OPENAI_MODEL_DEFAULT = "gpt-5-mini"
OPENAI_MODEL_FULL = "gpt-5"
OPENAI_MODEL = os.getenv('OPENAI_MODEL', OPENAI_MODEL_DEFAULT)

OPENAI_MAX_TOKENS = 16384   # Output tokens for final response (use max_completion_tokens in API calls)
OPENAI_TIMEOUT = 120.0      # API timeout in seconds (2 minutes)
# NOTE: GPT-5 does NOT support custom temperature — only default (1.0) is allowed

# Advanced Token Management Configuration
# GPT-5 mini context window: 400,000 tokens | GPT-5 full: 1,000,000 tokens
MODEL_CONTEXT_WINDOW_MINI = 400000   # GPT-5 mini
MODEL_CONTEXT_WINDOW_FULL = 1000000  # GPT-5 full
MODEL_CONTEXT_WINDOW = MODEL_CONTEXT_WINDOW_FULL if OPENAI_MODEL == OPENAI_MODEL_FULL else MODEL_CONTEXT_WINDOW_MINI

OUTPUT_TOKENS_RESERVED = 16384  # Reserve tokens for response (matches OPENAI_MAX_TOKENS Phase 2 budget)
SYSTEM_PROMPT_TOKENS = 500     # Estimated tokens for system prompt
INPUT_TOKENS_AVAILABLE = MODEL_CONTEXT_WINDOW - OUTPUT_TOKENS_RESERVED - SYSTEM_PROMPT_TOKENS

# Token-based Text Processing (accurate for German parliamentary text)
# German compound words and legal terminology: ~4.5 characters per token
CHARS_PER_TOKEN = 4.5  # Accurate estimate for German parliamentary text

# Precision Chunking Strategy: Smaller chunks for better accuracy
# Trade-off: More API calls but higher quality analysis
MAX_CHUNK_TOKENS = 30000  # ~30K tokens per chunk (focused analysis for accuracy)
MAX_CHUNK_CHARS = int(MAX_CHUNK_TOKENS * CHARS_PER_TOKEN)  # ~52,500 characters
CHUNK_OVERLAP_TOKENS = 1500  # Balanced overlap for accuracy and efficiency
CHUNK_OVERLAP_CHARS = int(CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN)  # ~2,625 characters

# Map-Reduce Processing Configuration
# Balanced for accuracy: smaller chunks need detailed summaries
CHUNK_SUMMARY_MAX_TOKENS = 1800    # Detailed summaries for accuracy-focused chunks
INTERMEDIATE_SUMMARY_MAX_TOKENS = 3000  # For intermediate consolidation steps
FINAL_SUMMARY_MAX_TOKENS = 4000     # Keep high for comprehensive final summary

# Legacy character-based settings (for backwards compatibility)
MAX_TEXT_LENGTH = MAX_CHUNK_CHARS    # Updated to match token-based calculation
CHUNK_SIZE = MAX_CHUNK_CHARS         # Updated to match token-based calculation
CHUNK_OVERLAP = CHUNK_OVERLAP_CHARS  # Updated to match token-based calculation

# Multi-level Processing Thresholds
SINGLE_CHUNK_THRESHOLD = MAX_CHUNK_CHARS  # Process in single call if under this
MULTI_CHUNK_THRESHOLD = MAX_CHUNK_CHARS * 4  # Use intermediate summaries if over this

# Content Length Management Configuration
# Maximum limits for AI-generated content to prevent memory and processing issues
MAX_SUMMARY_LENGTH_CHARS = 100000  # 100KB max for a single summary (very large documents)
MAX_SUMMARY_LENGTH_TOKENS = int(MAX_SUMMARY_LENGTH_CHARS / CHARS_PER_TOKEN)  # ~28,571 tokens
MAX_COMBINED_SUMMARIES_CHARS = 500000  # 500KB max for combined chunk summaries before final consolidation
MAX_COMBINED_SUMMARIES_TOKENS = int(MAX_COMBINED_SUMMARIES_CHARS / CHARS_PER_TOKEN)  # ~142,857 tokens

# Warning thresholds (when to alert users about large content)
SUMMARY_WARNING_THRESHOLD_CHARS = 50000  # 50KB - warn user about large summary
SUMMARY_WARNING_THRESHOLD_TOKENS = int(SUMMARY_WARNING_THRESHOLD_CHARS / CHARS_PER_TOKEN)  # ~14,286 tokens

# Maximum input document size limits
MAX_INPUT_DOCUMENT_CHARS = 2000000  # 2MB max input document size
MAX_INPUT_DOCUMENT_TOKENS = int(MAX_INPUT_DOCUMENT_CHARS / CHARS_PER_TOKEN)  # ~571,429 tokens

# Emergency truncation settings
EMERGENCY_TRUNCATE_RATIO = 0.8  # Truncate to 80% of limit if exceeded
TRUNCATION_BUFFER_CHARS = 1000  # Leave buffer when truncating

# File Paths
SYSTEM_PROMPT_FILE = "openai_system_prompt.txt"
SYSTEM_PROMPT_DE_FILE = "openai_system_prompt_de.txt"
SYSTEM_PROMPT_CITIZEN_IMPACT_FILE = "openai_system_prompt_citizen_impact.txt"
