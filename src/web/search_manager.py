"""
Search and Results Manager for Bundestag DIP API Explorer
Handles search operations and results with performance optimizations for table rendering and async operations.
Enhanced with modern UI design principles and improved user experience.
"""

import streamlit as st
import pandas as pd
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import time
import hashlib
import asyncio

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Modern table display using native Streamlit components
import pandas as pd
import streamlit as st

from src.utils.helpers import format_date

# Import UI enhancements
try:
    from src.web.ui_enhancements import (
        apply_custom_css, apply_mobile_optimizations, 
        add_performance_indicators, create_search_tips_component,
        display_status_indicator, create_feature_showcase
    )
    UI_ENHANCEMENTS_AVAILABLE = True
except ImportError:
    UI_ENHANCEMENTS_AVAILABLE = False

# Import performance optimizations
try:
    from src.web.performance_optimizations import (
        dom_optimizer, memory_optimizer, performance_monitor, 
        rerun_optimizer, optimize_performance
    )
    PERFORMANCE_OPTIMIZATIONS_AVAILABLE = True
except ImportError:
    PERFORMANCE_OPTIMIZATIONS_AVAILABLE = False
    # Create dummy optimizers
    class DummyOptimizer:
        def __getattr__(self, name):
            return lambda *args, **kwargs: True
    
    dom_optimizer = DummyOptimizer()
    memory_optimizer = DummyOptimizer()
    performance_monitor = DummyOptimizer()
    rerun_optimizer = DummyOptimizer()


class SearchManager:
    """Manages search functionality and parameters with enhanced UI and performance optimizations"""
    
    def __init__(self):
        logger.info("Initializing SearchManager")
        # Apply UI enhancements if available
        if UI_ENHANCEMENTS_AVAILABLE:
            logger.info("Applying UI enhancements")
            apply_custom_css()
            apply_mobile_optimizations()
            add_performance_indicators()
        
        # Apply global performance optimizations
        if PERFORMANCE_OPTIMIZATIONS_AVAILABLE:
            logger.info("Applying performance optimizations")
            optimize_performance()
        
        # Cache for search results to avoid duplicate API calls
        self._search_cache = {}
        self._cache_timeout = 300  # 5 minutes
        
        # Initialize UI state
        if 'ui_theme' not in st.session_state:
            st.session_state.ui_theme = 'modern'
            logger.debug("UI theme set to modern")
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []
            logger.debug("Search history initialized")
        
        logger.info("SearchManager initialization complete")
    
    def display_welcome_screen(self):
        """Display enhanced welcome screen with platform overview"""
        # Check if full documentation should be displayed
        if st.session_state.get('show_full_documentation', False):
            self._display_full_documentation()
            return
        
        if UI_ENHANCEMENTS_AVAILABLE:
            self._display_executive_summary_welcome()
        
        else:
            # Fallback welcome screen
            st.markdown("Explore German Parliament documents with AI-powered insights")
            
            st.info("💡 Use the sidebar to start searching for documents.")
    
    def _display_executive_summary_welcome(self):
        """Display welcome screen based on executive summary structure"""
        self._render_shared_welcome_content()
    
    def _render_shared_welcome_content(self):
        """Shared welcome content used by both executive summary and full documentation"""
        # Platform Overview with Title
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: white;
            padding: 2rem 1.5rem;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
        ">
            <h1 style="margin: 0; font-size: 2rem; font-weight: 700; margin-bottom: 1rem;">
                🏛️ Bundestag.AI Lens
            </h1>
            <p style="margin: 0; font-size: 1.1rem; opacity: 0.95; line-height: 1.4;">
                <strong>Intelligent platform making German parliamentary information accessible to everyone.</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Disclaimer
        st.markdown("""
        <div style='background-color: #fff3cd; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #ffc107;'>
            <strong>⚠️ Note:</strong> This project & platform is for educational and research purposes. Please respect the Bundestag DIP API terms of service when using this application. The code was generated with GenAI support, hence don't use in production.
        </div>
        """, unsafe_allow_html=True)
        
        # Resource links
        st.markdown("""
        <div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 20px;'>
            <strong>Resources:</strong> 
            🏛️ <a href='https://dip.bundestag.de/' target='_blank'>Official DIP Portal</a> - Browse documents online | 
            📋 <a href='https://dip.bundestag.de/documents/informationsblatt_zur_dip_api.pdf' target='_blank'>API Documentation</a> - Technical details
        </div>
        """, unsafe_allow_html=True)
        
        # Who Benefits from This Platform
        st.markdown("### 👥 Who Benefits from This Platform")
        
        value_col1, value_col2, value_col3 = st.columns(3)
        
        with value_col1:
            st.markdown("""
            **👥 Citizens & Civil Society**
            - 50-page documents → 5-minute summaries
            - No legal expertise required
            - Direct access to government decisions
            - Easier democratic participation
            """)
        
        with value_col2:
            st.markdown("""
            **📰 Media & Researchers**
            - Rapid analysis of document volumes
            - Unbiased, standardized summaries
            - Automated legislative tracking
            - AI-powered fact extraction
            """)
        
        with value_col3:
            st.markdown("""
            **🏛️ Government & Administration**
            - Enhanced public access
            - Increased citizen participation
            - Reduced information office burden
            - Digital government demonstration
            """)
        
        # System Architecture & Data Flow
        st.markdown("## 🏗️ System Architecture & Data Flow")
        
        # Compact Three-Service Architecture Overview (moved up)
        arch_col1, arch_col2, arch_col3 = st.columns(3)
        
        with arch_col1:
            st.markdown("""
            <div style="
                background: #ffffff;
                border: 1px solid #bfdbfe;
                padding: 1rem;
                border-radius: 6px;
                text-align: center;
                height: 140px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                border-left: 4px solid #3b82f6;
                box-shadow: 0 2px 6px rgba(59, 130, 246, 0.1);
            ">
                <h4 style="color: #1e40af; margin: 0 0 0.3rem 0; font-weight: 600; font-size: 0.9rem;">🏛️ Data Source</h4>
                <h5 style="color: #1e40af; margin: 0 0 0.5rem 0; font-size: 0.85rem;">German Bundestag API</h5>
                <p style="margin: 0; font-size: 0.75rem; color: #3b82f6; line-height: 1.3;">
                    Official parliamentary documents
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with arch_col2:
            st.markdown("""
            <div style="
                background: #ffffff;
                border: 1px solid #bfdbfe;
                padding: 1rem;
                border-radius: 6px;
                text-align: center;
                height: 140px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                border-left: 4px solid #2563eb;
                box-shadow: 0 2px 6px rgba(37, 99, 235, 0.1);
            ">
                <h4 style="color: #1e40af; margin: 0 0 0.3rem 0; font-weight: 600; font-size: 0.9rem;">🧠 Intelligence Engine</h4>
                <h5 style="color: #1e40af; margin: 0 0 0.5rem 0; font-size: 0.85rem;">AI Analysis Service</h5>
                <p style="margin: 0; font-size: 0.75rem; color: #3b82f6; line-height: 1.3;">
                    Plain-language summaries & impact analysis
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with arch_col3:
            st.markdown("""
            <div style="
                background: #ffffff;
                border: 1px solid #bfdbfe;
                padding: 1rem;
                border-radius: 6px;
                text-align: center;
                height: 140px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                border-left: 4px solid #1d4ed8;
                box-shadow: 0 2px 6px rgba(29, 78, 216, 0.1);
            ">
                <h4 style="color: #1e40af; margin: 0 0 0.3rem 0; font-weight: 600; font-size: 0.9rem;">☁️ User Interface</h4>
                <h5 style="color: #1e40af; margin: 0 0 0.5rem 0; font-size: 0.85rem;">Web Platform</h5>
                <p style="margin: 0; font-size: 0.75rem; color: #3b82f6; line-height: 1.3;">
                    Real-time interactive features
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Compact Data Flow Diagram (moved down)
        st.markdown("""
        <div style="
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 6px;
            padding: 1.2rem;
            margin: 1rem 0;
            text-align: center;
        ">
            <h4 style="color: #1e40af; margin: 0 0 1rem 0; font-weight: 600; font-size: 1rem;">Data Flow Process</h4>
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.8rem;">
                <div style="flex: 1; min-width: 100px;">
                    <div style="background: #ffffff; border: 2px solid #3b82f6; border-radius: 6px; padding: 0.7rem; margin-bottom: 0.3rem;">
                        <div style="font-size: 1.2rem; margin-bottom: 0.3rem;">👤</div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: #1e40af;">User Query</div>
                    </div>
                </div>
                <div style="font-size: 1.2rem; color: #3b82f6;">→</div>
                <div style="flex: 1; min-width: 100px;">
                    <div style="background: #ffffff; border: 2px solid #2563eb; border-radius: 6px; padding: 0.7rem; margin-bottom: 0.3rem;">
                        <div style="font-size: 1.2rem; margin-bottom: 0.3rem;">☁️</div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: #1e40af;">Web Interface</div>
                    </div>
                </div>
                <div style="font-size: 1.2rem; color: #3b82f6;">→</div>
                <div style="flex: 1; min-width: 100px;">
                    <div style="background: #ffffff; border: 2px solid #1d4ed8; border-radius: 6px; padding: 0.7rem; margin-bottom: 0.3rem;">
                        <div style="font-size: 1.2rem; margin-bottom: 0.3rem;">🏛️</div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: #1e40af;">Bundestag API</div>
                    </div>
                </div>
                <div style="font-size: 1.2rem; color: #3b82f6;">→</div>
                <div style="flex: 1; min-width: 100px;">
                    <div style="background: #ffffff; border: 2px solid #1e40af; border-radius: 6px; padding: 0.7rem; margin-bottom: 0.3rem;">
                        <div style="font-size: 1.2rem; margin-bottom: 0.3rem;">🧠</div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: #1e40af;">AI Analysis</div>
                    </div>
                </div>
                <div style="font-size: 1.2rem; color: #3b82f6;">→</div>
                <div style="flex: 1; min-width: 100px;">
                    <div style="background: #ffffff; border: 2px solid #1e3a8a; border-radius: 6px; padding: 0.7rem; margin-bottom: 0.3rem;">
                        <div style="font-size: 1.2rem; margin-bottom: 0.3rem;">📊</div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: #1e40af;">Results</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Key System Statistics
        st.markdown("---")
        st.markdown("## 📊 Platform Capabilities")
        
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        
        with stat_col1:
            st.markdown("""
            <div style="
                background: #ffffff;
                border: 1px solid #dee2e6;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #6c757d;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 2rem; font-weight: 600; color: #495057; margin-bottom: 0.5rem;">1M+</div>
                <div style="color: #6c757d; font-weight: 500; font-size: 0.9rem;">Parliamentary Documents</div>
            </div>
            """, unsafe_allow_html=True)
        
        with stat_col2:
            st.markdown("""
            <div style="
                background: #ffffff;
                border: 1px solid #dee2e6;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #6c757d;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 2rem; font-weight: 600; color: #495057; margin-bottom: 0.5rem;">21</div>
                <div style="color: #6c757d; font-weight: 500; font-size: 0.9rem;">Electoral Periods</div>
            </div>
            """, unsafe_allow_html=True)
        
        with stat_col3:
            st.markdown("""
            <div style="
                background: #ffffff;
                border: 1px solid #dee2e6;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #6c757d;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 2rem; font-weight: 600; color: #495057; margin-bottom: 0.5rem;">5</div>
                <div style="color: #6c757d; font-weight: 500; font-size: 0.9rem;">Document Types</div>
            </div>
            """, unsafe_allow_html=True)
        
        with stat_col4:
            st.markdown("""
            <div style="
                background: #ffffff;
                border: 1px solid #dee2e6;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #198754;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <div style="font-size: 2rem; font-weight: 600; color: #495057; margin-bottom: 0.5rem;">99.9%</div>
                <div style="color: #6c757d; font-weight: 500; font-size: 0.9rem;">Uptime Reliability</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Quick Start Section
        st.markdown("---")
        st.markdown("## 🚀 Quick Start Guide")
        
        # Interactive quick start steps
        start_col1, start_col2, start_col3 = st.columns(3)
        
        with start_col1:
            st.markdown("""
            <div style="
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #0d6efd;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <h4 style="color: #495057; margin: 0 0 1rem 0; font-weight: 600;">1. Search</h4>
                <p style="margin: 0; font-size: 0.9rem; color: #6c757d; line-height: 1.4;">
                    Use the sidebar to select document type and enter keywords (e.g., "climate policy")
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with start_col2:
            st.markdown("""
            <div style="
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #0d6efd;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <h4 style="color: #495057; margin: 0 0 1rem 0; font-weight: 600;">2. Browse</h4>
                <p style="margin: 0; font-size: 0.9rem; color: #6c757d; line-height: 1.4;">
                    Review results in the interactive table and select documents of interest
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with start_col3:
            st.markdown("""
            <div style="
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 1.5rem;
                border-radius: 8px;
                text-align: center;
                border-left: 4px solid #0d6efd;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <h4 style="color: #495057; margin: 0 0 1rem 0; font-weight: 600;">3. Analyze</h4>
                <p style="margin: 0; font-size: 0.9rem; color: #6c757d; line-height: 1.4;">
                    Generate AI summaries and citizen impact analysis with one click
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Call-to-Action
        st.markdown("---")
        st.markdown("""
        <div style="
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 2rem;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #0d6efd;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            <h3 style="color: #495057; margin: 0 0 1rem 0; font-weight: 600;">Ready to Start?</h3>
            <p style="margin: 0 0 1.5rem 0; color: #6c757d; font-size: 1.1rem; line-height: 1.5;">
                Begin exploring German parliamentary documents with AI-powered insights. 
                No training required - just search and discover!
            </p>
            <p style="margin: 0; color: #6c757d; font-style: italic;">
                👈 Use the sidebar to begin your search journey, documents like Antwort (auf kleine Anfragen) or Gesetzesentwurf are well suited for AI Analysis
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    def _display_welcome_content_in_docs(self):
        """Display the welcome screen content within the documentation page"""
        self._render_shared_welcome_content()
    
    def _save_search_to_history(self, doc_type: str, filters: Dict[str, Any], num_results: int):
        """Save search parameters to history for suggestions"""
        search_entry = {
            'timestamp': datetime.now().isoformat(),
            'doc_type': doc_type,
            'filters': {k: v for k, v in filters.items() if v},  # Only non-empty filters
            'num_results': num_results
        }
        
        # Add to history (keep last 10 searches)
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []
        
        st.session_state.search_history.insert(0, search_entry)
        st.session_state.search_history = st.session_state.search_history[:10]
    
    def _display_search_history(self):
        """Display recent search history with quick repeat options"""
        if not st.session_state.get('search_history', []):
            return
        
        with st.sidebar.expander("🕒 Recent Searches", expanded=False):
            for i, search in enumerate(st.session_state.search_history[:5]):
                timestamp = datetime.fromisoformat(search['timestamp'])
                time_str = timestamp.strftime("%m/%d %H:%M")
                
                # Create a summary of the search
                search_summary = f"{search['doc_type'].title()}"
                if search['filters']:
                    filter_count = len([v for v in search['filters'].values() if v])
                    search_summary += f" ({filter_count} filters)"
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"🔍 {search_summary}")
                    st.caption(f"⏰ {time_str} • {search['num_results']} results")
                
                with col2:
                    if st.button("↻", key=f"repeat_search_{i}", help="Repeat this search"):
                        # This would trigger a repeat of the search
                        st.info("🔄 Search repeated!")
                
                if i < len(st.session_state.search_history) - 1:
                    st.markdown("---")
    
    def display_enhanced_error(self, error_type: str, message: str, suggestions: List[str] = None):
        """Display enhanced error messages with helpful suggestions"""
        if UI_ENHANCEMENTS_AVAILABLE:
            display_status_indicator("error", f"{error_type}: {message}")
            
            if suggestions:
                with st.expander("💡 Troubleshooting Suggestions", expanded=True):
                    for suggestion in suggestions:
                        st.markdown(f"• {suggestion}")
        else:
            st.error(f"{error_type}: {message}")
            if suggestions:
                st.info("Suggestions: " + " | ".join(suggestions))
    
    def display_search_analytics(self, results: Dict[str, Any]):
        """Display search analytics and insights"""
        if not results or not results.get("documents"):
            return
        
        documents = results["documents"]
        doc_type = results["doc_type"]
        
        # Analytics section
        with st.expander("📊 Search Analytics", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Found", f"{results['numFound']:,}")
            
            with col2:
                st.metric("Showing", len(documents))
            
            with col3:
                coverage = min(100, (len(documents) / results['numFound']) * 100) if results['numFound'] > 0 else 0
                st.metric("Coverage", f"{coverage:.1f}%")
            
            # Document type distribution (if applicable)
            if doc_type == "drucksache" and len(documents) > 1:
                doc_types = {}
                for doc in documents:
                    dtype = doc.get('drucksachetyp', 'Unknown')
                    doc_types[dtype] = doc_types.get(dtype, 0) + 1
                
                if len(doc_types) > 1:
                    st.markdown("**Document Type Distribution:**")
                    for dtype, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                        percentage = (count / len(documents)) * 100
                        st.progress(percentage / 100)
                        st.caption(f"{dtype}: {count} ({percentage:.1f}%)")
    
    
    
        
    def _get_cache_key(self, doc_type: str, filters: Dict[str, Any], limit: int) -> str:
        """Generate cache key for search results"""
        # Create a deterministic hash from search parameters
        cache_data = {
            'doc_type': doc_type,
            'filters': str(sorted(filters.items())),
            'limit': limit
        }
        return hashlib.md5(str(cache_data).encode()).hexdigest()
        
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached result is still valid"""
        if cache_key not in self._search_cache:
            return False
            
        cache_time = self._search_cache[cache_key].get('timestamp', 0)
        return time.time() - cache_time < self._cache_timeout
    
    def display_sidebar_search_form(self) -> tuple[str, Dict[str, Any], int, bool]:
        """Display condensed sidebar search form with all functionality"""
        # Condensed header
        st.sidebar.markdown("## 🔍 Search")
        
        # Compact documentation and history in single row
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("📚", help="Documentation", key="docs_btn"):
                st.session_state.show_full_documentation = True
                st.rerun()
        with col2:
            with st.popover("🕒", help="Recent searches"):
                if st.session_state.get('search_history', []):
                    for i, search in enumerate(st.session_state.search_history[:3]):
                        timestamp = datetime.fromisoformat(search['timestamp'])
                        time_str = timestamp.strftime("%m/%d %H:%M")
                        if st.button(f"{search['doc_type']} • {time_str}", key=f"quick_search_{i}"):
                            st.info("🔄 Search repeated!")
                else:
                    st.caption("No recent searches")
        
        # Compact document type selection
        doc_type_options = {
            "drucksache": "📋 Drucksachen",
            "vorgang": "⚙️ Vorgänge", 
            "plenarprotokoll": "🗣️ Plenarprotokolle",
            "person": "👤 Personen",
            "aktivitaet": "📅 Aktivitäten"
        }
        
        doc_type = st.sidebar.selectbox(
            "Document Type:",
            options=list(doc_type_options.keys()),
            format_func=lambda x: doc_type_options[x]
        )
        
        # Condensed search parameters
        filters = self._display_basic_search_params()
        
        # Advanced filters (collapsed by default)
        advanced_filters = self._display_advanced_filters(doc_type)
        filters.update(advanced_filters)
        
        # Set default limit
        limit = 15
        
        # Compact search button
        search_clicked = st.sidebar.button(
            "🔍 Search", 
            type="primary",
            use_container_width=True
        )
        
        if search_clicked:
            self._save_search_to_history(doc_type, filters, limit)
        
        return doc_type, filters, limit, search_clicked
    
    def _display_basic_search_params(self) -> Dict[str, Any]:
        """Display condensed basic search parameters"""
        filters = {}
        
        # Compact keyword search
        title_search = st.sidebar.text_input(
            "Keywords:",
            placeholder="e.g., Klimaschutz, Digitalisierung",
            key="title_search"
        )
        if title_search:
            filters["f.titel"] = [title_search]
        
        # Compact date range with presets
        date_preset = st.sidebar.selectbox(
            "Time Period:",
            options=["Custom", "Last 30 days", "Last 3 months", "Last year", "Current legislature"]
        )
        
        # Handle date presets
        from datetime import datetime, timedelta
        today = datetime.now().date()
        
        if date_preset == "Last 30 days":
            start_date = today - timedelta(days=30)
            end_date = today
        elif date_preset == "Last 3 months":
            start_date = today - timedelta(days=90)
            end_date = today
        elif date_preset == "Last year":
            start_date = today - timedelta(days=365)
            end_date = today
        elif date_preset == "Current legislature":
            start_date = datetime(2021, 10, 26).date()
            end_date = today
        else:
            # Custom date selection in compact layout
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.date_input("From:", value=None, key="start_date")
            with col2:
                end_date = st.date_input("To:", value=None, key="end_date")
        
        # Apply date filters
        if start_date:
            filters["f.datum.start"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            filters["f.datum.end"] = end_date.strftime("%Y-%m-%d")
        
        # Compact electoral period
        wahlperiode_options = {
            None: "All periods",
            21: "21st (2024-2029)",
            20: "20th (2021-2025)",
            19: "19th (2017-2021)",
            18: "18th (2013-2017)",
            17: "17th (2009-2013)",
            16: "16th (2005-2009)"
        }
        
        wahlperiode = st.sidebar.selectbox(
            "Electoral Period:",
            options=list(wahlperiode_options.keys()),
            format_func=lambda x: wahlperiode_options[x]
        )
        if wahlperiode:
            filters["f.wahlperiode"] = [wahlperiode]
        
        return filters
    
    def _display_advanced_filters(self, doc_type: str) -> Dict[str, Any]:
        """Display condensed advanced filters"""
        filters = {}
        
        # Compact advanced filters
        with st.sidebar.expander("⚙️ Advanced", expanded=False):
            if doc_type == "drucksache":
                filters.update(self._display_drucksache_filters())
            elif doc_type == "vorgang":
                filters.update(self._display_vorgang_filters())
            elif doc_type == "person":
                filters.update(self._display_person_filters())
            elif doc_type == "plenarprotokoll":
                filters.update(self._display_plenarprotokoll_filters())
            elif doc_type == "aktivitaet":
                filters.update(self._display_aktivitaet_filters())
        
        return filters
    
    def _display_drucksache_filters(self) -> Dict[str, Any]:
        """Display condensed Drucksachen filters"""
        filters = {}
        
        # Compact document type selection
        drucksachetyp_options = [
            "", "Antrag", "Antwort", "Gesetzentwurf", "Beschlussempfehlung", "Bericht", 
            "Große Anfrage", "Kleine Anfrage", "Entschließungsantrag", "Unterrichtung"
        ]
        drucksachetyp = st.selectbox(
            "Document Type:",
            options=drucksachetyp_options,
            format_func=lambda x: "All types" if x == "" else x
        )
        if drucksachetyp:
            filters["f.drucksachetyp"] = drucksachetyp
        
        # Compact document number
        dokumentnummer = st.text_input(
            "Document Number:",
            placeholder="e.g., 20/1234"
        )
        if dokumentnummer and "/" in dokumentnummer:
            filters["f.dokumentnummer"] = [dokumentnummer]
        
        # Compact author selection
        urheber_options = [
            "", "Bundesregierung", "Die Linke.", "SPD", "CDU/CSU", "FDP", 
            "Bündnis 90/Die Grünen", "AfD", "Bundesrat"
        ]
        urheber = st.selectbox(
            "Author:",
            options=urheber_options,
            format_func=lambda x: "All authors" if x == "" else x
        )
        if urheber:
            filters["f.urheber"] = [urheber]
        
        return filters
    
    def _display_vorgang_filters(self) -> Dict[str, Any]:
        """Display enhanced filters specific to Vorgänge with better UX"""
        filters = {}
        
        st.markdown("⚙️ **Procedure-Specific Filters:**")
        
        # Enhanced procedure type with predefined options
        vorgangstyp_options = [
            "", "Gesetzgebung", "Antrag", "Aktuelle Stunde", "Befragung", 
            "Große Anfrage", "Kleine Anfrage", "Petition", "Wahlprüfung", "Untersuchungsausschuss"
        ]
        vorgangstyp = st.selectbox(
            "Procedure Type:",
            options=vorgangstyp_options,
            format_func=lambda x: "Any procedure type" if x == "" else x,
            help="Select the type of parliamentary procedure"
        )
        if vorgangstyp:
            filters["f.vorgangstyp"] = [vorgangstyp]
            st.caption(f"⚙️ Procedure: {vorgangstyp}")
        
        # Enhanced initiative with common options
        initiative_options = [
            "", "Bundesregierung", "Bundesrat", "Bundestag", "Die Linke.", "SPD", 
            "CDU/CSU", "FDP", "Bündnis 90/Die Grünen", "AfD"
        ]
        initiative = st.selectbox(
            "Initiative:",
            options=initiative_options,
            format_func=lambda x: "Any initiator" if x == "" else x,
            help="Select who initiated the procedure"
        )
        if initiative:
            filters["f.initiative"] = [initiative]
            st.caption(f"🏛️ Initiated by: {initiative}")
        
        # Procedure status filter
        beratungsstand_options = [
            "", "Noch nicht beraten", "1. Beratung", "2. Beratung", "3. Beratung", 
            "Abgeschlossen", "Zurückgezogen", "Erledigt"
        ]
        beratungsstand = st.selectbox(
            "Consultation Status:",
            options=beratungsstand_options,
            format_func=lambda x: "Any status" if x == "" else x,
            help="Select the current status of the procedure"
        )
        if beratungsstand:
            filters["f.beratungsstand"] = [beratungsstand]
            st.caption(f"📊 Status: {beratungsstand}")
        
        return filters
    
    def _display_person_filters(self) -> Dict[str, Any]:
        """Display enhanced filters specific to Person searches with better UX"""
        filters = {}
        
        st.markdown("👤 **Person-Specific Filters:**")
        
        # Enhanced name search with separate fields
        col1, col2 = st.columns(2)
        with col1:
            vorname = st.text_input(
                "First Name:",
                placeholder="e.g., Angela",
                help="Search by first name"
            )
        with col2:
            nachname = st.text_input(
                "Last Name:",
                placeholder="e.g., Merkel",
                help="Search by last name"
            )
        
        if vorname:
            filters["f.vorname"] = [vorname]
            st.caption(f"👤 First name: {vorname}")
        if nachname:
            filters["f.nachname"] = [nachname]
            st.caption(f"👤 Last name: {nachname}")
        
        # Party affiliation
        partei_options = [
            "", "CDU", "CSU", "SPD", "Die Linke", "FDP", "Bündnis 90/Die Grünen", 
            "AfD", "parteilos", "fraktionslos"
        ]
        partei = st.selectbox(
            "Party Affiliation:",
            options=partei_options,
            format_func=lambda x: "Any party" if x == "" else x,
            help="Filter by political party"
        )
        if partei:
            filters["f.partei"] = [partei]
            st.caption(f"🏛️ Party: {partei}")
        
        return filters
    
    def _display_plenarprotokoll_filters(self) -> Dict[str, Any]:
        """Display enhanced filters specific to Plenarprotokolle"""
        filters = {}
        
        st.markdown("🗣️ **Session-Specific Filters:**")
        
        # Session number
        sitzungsnr = st.number_input(
            "Session Number:",
            min_value=1,
            value=None,
            help="Filter by specific session number"
        )
        if sitzungsnr:
            filters["f.sitzungsnr"] = [str(sitzungsnr)]
            st.caption(f"📋 Session: {sitzungsnr}")
        
        return filters
    
    def _display_aktivitaet_filters(self) -> Dict[str, Any]:
        """Display enhanced filters specific to Aktivitäten"""
        filters = {}
        
        st.markdown("📅 **Activity-Specific Filters:**")
        
        # Activity type
        aktivitaetsart_options = [
            "", "Rede", "Zwischenfrage", "Zwischenruf", "Wortmeldung", 
            "Tagesordnungspunkt", "Abstimmung"
        ]
        aktivitaetsart = st.selectbox(
            "Activity Type:",
            options=aktivitaetsart_options,
            format_func=lambda x: "Any activity type" if x == "" else x,
            help="Select the type of parliamentary activity"
        )
        if aktivitaetsart:
            filters["f.aktivitaetsart"] = [aktivitaetsart]
            st.caption(f"📅 Activity: {aktivitaetsart}")
        
        return filters
    
    def _display_full_documentation(self):
        """Display comprehensive documentation with welcome content and tabbed interface"""
        # Header with close button (no title)
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("✖️ Close", key="close_start_page", type="secondary"):
                st.session_state.show_full_documentation = False
                st.rerun()
        
        # Include the welcome screen content at the top
        self._display_welcome_content_in_docs()
        
        st.markdown("---")
        st.markdown("## 📖 Detailed Documentation")
        
        # Enhanced tabbed documentation
        tab1, tab2, tab3 = st.tabs(["🚀 Quick Start Guide", "📚 System Introduction", "🔍 Advanced Search Tips"])
        
        with tab1:
            self._display_quick_start_guide()
        
        with tab2:
            self._display_system_introduction()
        
        with tab3:
            self._display_advanced_search_tips()
    
    def _display_quick_start_guide(self):
        """Display comprehensive quick start guide"""
        st.markdown("""
        ## 🚀 Getting Started with Bundestag.AI Lens
        
        Welcome to the German Parliament Document Intelligence Platform! This guide will help you navigate and use all the features effectively.
        
        ### 📋 Step-by-Step Workflow
        """)
        
        # Interactive workflow with visual elements
        step1, step2, step3 = st.columns(3)
        
        with step1:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
                padding: 1.5rem;
                border-radius: 12px;
                text-align: center;
                border-left: 4px solid #2196f3;
                margin-bottom: 1rem;
            ">
                <h4 style="color: #1976d2; margin: 0 0 1rem 0;">🎯 Step 1: Search Setup</h4>
                <p style="margin: 0; font-size: 0.9rem;">Choose document type and enter keywords</p>
            </div>
            """, unsafe_allow_html=True)
        
        with step2:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
                padding: 1.5rem;
                border-radius: 12px;
                text-align: center;
                border-left: 4px solid #9c27b0;
                margin-bottom: 1rem;
            ">
                <h4 style="color: #7b1fa2; margin: 0 0 1rem 0;">🔍 Step 2: Execute Search</h4>
                <p style="margin: 0; font-size: 0.9rem;">Apply filters and run your search</p>
            </div>
            """, unsafe_allow_html=True)
        
        with step3:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
                padding: 1.5rem;
                border-radius: 12px;
                text-align: center;
                border-left: 4px solid #4caf50;
                margin-bottom: 1rem;
            ">
                <h4 style="color: #388e3c; margin: 0 0 1rem 0;">🧠 Step 3: AI Analysis</h4>
                <p style="margin: 0; font-size: 0.9rem;">Select documents for AI insights</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Detailed instructions
        st.markdown("""
        ### 📝 Detailed Instructions
        
        #### 1. Document Type Selection
        Choose from five main document types:
        - **📋 Drucksachen** - Parliamentary papers, bills, reports (recommended for beginners)
        - **⚙️ Vorgänge** - Legislative procedures and processes
        - **🗣️ Plenarprotokolle** - Plenary session transcripts
        - **👤 Personen** - Information about MPs and officials
        - **📅 Aktivitäten** - Parliamentary activities and events
        
        #### 2. Search Parameters
        **Basic Search:**
        - Enter keywords in the search field (e.g., "Klimaschutz", "Digitalisierung")
        - Use quotation marks for exact phrases
        - Set date ranges for recent documents
        - Select electoral periods (21st = current)
        
        **Advanced Filters:**
        - Document-specific filters (type, author, status)
        - Procedure-specific options (initiative, consultation status)
        - Person-specific searches (name, party affiliation)
        
        #### 3. Results & Analysis
        - Review results in the interactive table
        - Select up to 5 documents for AI analysis
        - Generate summaries and citizen impact insights
        - Export or save important findings
        """)
        
        # Tips section
        with st.expander("💡 Pro Tips for Better Results", expanded=False):
            st.markdown("""
            **🎯 Search Strategy:**
            - Start with broad keywords, then narrow down
            - Use the current electoral period (21st) for recent topics
            - Combine date filters with keyword searches
            - Try different document types for comprehensive coverage
            
            **🔍 Keyword Suggestions:**
            - **Climate**: Klimaschutz, Energiewende, Nachhaltigkeit
            - **Technology**: Digitalisierung, KI, Cybersicherheit
            - **Education**: Bildung, Schule, Universität
            - **Economy**: Wirtschaft, Arbeitsmarkt, Steuern
            - **Health**: Gesundheit, Krankenversicherung, Pandemie
            
            **⚡ Performance Tips:**
            - Limit results to 25 for optimal performance
            - Use specific filters to reduce large result sets
            - Clear selections between different searches
            """)
    
    def _display_system_introduction(self):
        """Display comprehensive system introduction (renamed from Architecture)"""
        st.markdown("""
        ## 📚 System Introduction & Architecture
        
        The Bundestag.AI Lens is a comprehensive platform that combines official German Parliament data with AI-powered analysis to provide citizens with accessible insights into legislative processes.
        """)
        
        # System overview with visual diagram
        st.markdown("""
        ### 🏗️ System Architecture Overview
        """)
        
        # Create visual architecture diagram
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 2rem;
            border-radius: 15px;
            margin: 1rem 0;
            border: 2px solid #dee2e6;
        ">
            <div style="text-align: center; font-family: monospace; line-height: 1.8;">
                <div style="background: #e3f2fd; padding: 0.5rem; border-radius: 8px; margin: 0.5rem 0; color: #1976d2; font-weight: bold;">
                    👤 User Interface (Streamlit Web App)
                </div>
                <div style="font-size: 1.5rem; color: #666;">⬇️</div>
                <div style="background: #f3e5f5; padding: 0.5rem; border-radius: 8px; margin: 0.5rem 0; color: #7b1fa2; font-weight: bold;">
                    🔍 Search Manager (Current Module)
                </div>
                <div style="font-size: 1.5rem; color: #666;">⬇️</div>
                <div style="background: #fff3e0; padding: 0.5rem; border-radius: 8px; margin: 0.5rem 0; color: #f57c00; font-weight: bold;">
                    🌐 Bundestag API Client
                </div>
                <div style="font-size: 1.5rem; color: #666;">⬇️</div>
                <div style="background: #e8f5e8; padding: 0.5rem; border-radius: 8px; margin: 0.5rem 0; color: #388e3c; font-weight: bold;">
                    🏛️ Official DIP API (dip.bundestag.de)
                </div>
                <div style="font-size: 1.5rem; color: #666;">⬇️</div>
                <div style="background: #fce4ec; padding: 0.5rem; border-radius: 8px; margin: 0.5rem 0; color: #c2185b; font-weight: bold;">
                    🧠 AI Analysis Service (OpenAI)
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Data flow process
        st.markdown("""
        ### 🔄 Complete Data Flow Process
        
        Our system follows a comprehensive 6-step process to deliver intelligent document analysis:
        """)
        
        # Interactive flow steps
        flow_col1, flow_col2 = st.columns(2)
        
        with flow_col1:
            st.markdown("""
            **📥 Input Phase:**
            1. **User Input Collection**
               - Document type selection
               - Keyword and filter specification
               - Parameter validation
            
            2. **API Request Formation**
               - Query optimization
               - Rate limiting application
               - Cache checking
            
            3. **Data Retrieval**
               - Official API communication
               - Response parsing
               - Error handling
            """)
        
        with flow_col2:
            st.markdown("""
            **📤 Output Phase:**
            4. **Data Processing**
               - Result formatting
               - Performance optimization
               - Table preparation
            
            5. **User Interaction**
               - Interactive table display
               - Document selection interface
               - Real-time feedback
            
            6. **AI Analysis** (Optional)
               - OpenAI integration
               - Summary generation
               - Citizen impact analysis
            """)
        
        # Key features section
        st.markdown("""
        ### ⚡ Key System Features
        """)
        
        feat_col1, feat_col2, feat_col3 = st.columns(3)
        
        with feat_col1:
            st.markdown("""
            **🚀 Performance**
            - Smart caching (5-min TTL)
            - Optimized pagination
            - Lazy loading
            - Memory management
            - Browser optimization
            """)
        
        with feat_col2:
            st.markdown("""
            **🛡️ Security**
            - Input validation
            - XSS protection
            - Rate limiting
            - Secure API keys
            - Error handling
            """)
        
        with feat_col3:
            st.markdown("""
            **🧠 Intelligence**
            - AI-powered summaries
            - Citizen impact analysis
            - Real-time processing
            - Multi-document analysis
            - Stream processing
            """)
        
        # Technical specifications
        with st.expander("🔧 Technical Specifications", expanded=False):
            st.markdown("""
            **Frontend Technology Stack:**
            - **Framework**: Streamlit (Python web framework)
            - **UI Components**: Native Streamlit + Custom CSS
            - **Caching**: Session state + LRU caches
            - **Performance**: DOM optimization, lazy loading
            
            **Backend Integration:**
            - **API Client**: Custom Bundestag DIP API wrapper
            - **Data Processing**: Pandas for data manipulation
            - **AI Service**: OpenAI GPT-4 integration
            - **Caching Strategy**: Multi-layer caching system
            
            **Performance Benchmarks:**
            - **API Response Time**: < 2 seconds typical
            - **Table Render Time**: < 1 second for 25 results
            - **Cache Hit Rate**: > 80% for repeated searches
            - **Memory Usage**: Optimized with automatic cleanup
            
            **Scalability Features:**
            - **Pagination**: Handles large result sets efficiently
            - **Async Operations**: Non-blocking UI updates
            - **Resource Management**: Automatic memory cleanup
            - **Error Recovery**: Graceful degradation on failures
            """)
    
    def _display_advanced_search_tips(self):
        """Display comprehensive advanced search tips"""
        st.markdown("""
        ## 🔍 Advanced Search Strategies & Resources
        
        Master the advanced features to find exactly what you're looking for in the German Parliament documents.
        """)
        
        # Search strategies section
        tip_col1, tip_col2 = st.columns(2)
        
        with tip_col1:
            st.markdown("""
            ### 🎯 Advanced Search Techniques
            
            **Exact Phrase Search:**
            - Use `"climate change"` for exact matches
            - Combine with filters for precision
            - Case-insensitive matching
            
            **Boolean Logic:**
            - Use multiple keywords (AND logic)
            - Broader terms first, then narrow
            - Try synonyms for better coverage
            
            **Date Range Strategies:**
            - Current period (21st): 2021-present
            - Previous period (20th): 2017-2021  
            - Historical searches: Earlier periods
            
            **Filter Combinations:**
            - Document type + keyword + date
            - Author + topic for targeted search
            - Status + procedure type for tracking
            """)
        
        with tip_col2:
            st.markdown("""
            ### 📊 Document Type Strategies
            
            **Drucksachen (Papers):**
            - Best for: Policy research, bill tracking
            - Filter by: Type, author, document number
            - Tip: Use "Gesetzentwurf" for bills
            
            **Vorgänge (Procedures):**
            - Best for: Process tracking, status updates
            - Filter by: Initiative, consultation status
            - Tip: Track legislation progress
            
            **Plenarprotokolle (Transcripts):**
            - Best for: Debate analysis, speeches
            - Filter by: Session number, date
            - Tip: Find specific debate topics
            
            **Personen (People):**
            - Best for: MP information, party affiliation
            - Filter by: Name, party, period
            - Tip: Track individual contributions
            """)
        
        # Popular search terms by category
        st.markdown("""
        ### 📋 Popular Search Terms by Category
        """)
        
        cat_col1, cat_col2, cat_col3 = st.columns(3)
        
        with cat_col1:
            st.markdown("""
            **🌍 Environment & Climate:**
            - Klimaschutz (Climate protection)
            - Energiewende (Energy transition)
            - Nachhaltigkeit (Sustainability)
            - Umweltschutz (Environmental protection)
            - Erneuerbare Energien (Renewable energy)
            """)
        
        with cat_col2:
            st.markdown("""
            **💻 Technology & Digital:**
            - Digitalisierung (Digitalization)
            - Künstliche Intelligenz (AI)
            - Cybersicherheit (Cybersecurity)
            - Datenschutz (Data protection)
            - Breitband (Broadband)
            """)
        
        with cat_col3:
            st.markdown("""
            **🏥 Health & Social:**
            - Gesundheit (Health)
            - Krankenversicherung (Health insurance)
            - Rente (Pension)
            - Arbeitsmarkt (Labor market)
            - Bildung (Education)
            """)
        
        # External resources section
        st.markdown("""
        ### 🌐 External Resources & Official Links
        """)
        
        resource_col1, resource_col2 = st.columns(2)
        
        with resource_col1:
            st.markdown("""
            **📚 Official Documentation:**
            - [🏛️ Official DIP Portal](https://dip.bundestag.de) - Browse documents directly
            - [📋 API Documentation](https://dip.bundestag.de/documents/informationsblatt_zur_dip_api.pdf) - Technical API details
            - [⚖️ Legal Framework](https://www.bundestag.de/parlament) - Parliamentary procedures
            - [🗳️ Electoral Information](https://www.bundestag.de/abgeordnete) - Current representatives
            """)
        
        with resource_col2:
            st.markdown("""
            **🔍 Research Resources:**
            - [📊 Parliamentary Statistics](https://www.bundestag.de/services/glossar) - Glossary & terms
            - [📰 Press Releases](https://www.bundestag.de/presse) - Latest parliamentary news
            - [🎥 Video Archive](https://www.bundestag.de/mediathek) - Debate recordings
            - [📱 Mobile Apps](https://www.bundestag.de/services/mobile) - Official mobile access
            """)
        
        # Performance and optimization tips
        with st.expander("⚡ Performance & Optimization Tips", expanded=False):
            st.markdown("""
            **🚀 Search Performance:**
            - **Limit Results**: Use 25 or fewer for optimal speed
            - **Specific Filters**: Reduce large result sets with targeted filters  
            - **Date Ranges**: Limit time periods for faster searches
            - **Clear Cache**: Refresh browser if experiencing issues
            
            **🎯 Result Quality:**
            - **Start Broad**: Begin with general terms, then refine
            - **Use Filters**: Combine multiple filters for precision
            - **Check Spelling**: German terms are case-sensitive
            - **Try Variants**: Test different keyword combinations
            
            **🧠 AI Analysis Optimization:**
            - **Select 1-5 Documents**: Optimal range for AI analysis
            - **Choose Diverse Sources**: Mix document types for comprehensive insights
            - **Review Carefully**: AI summaries complement, not replace, document review
            - **Use Citizen Impact**: Understand real-world implications of policies
            """)
    


class ResultsManager:
    """Manages the display and interaction with search results"""
    
    def __init__(self):
        logger.info("Initializing ResultsManager")
        # Import cache manager for proper memory management
        try:
            from .cache_manager import get_cache_manager, SessionStateManager
            logger.debug("Cache manager imported from relative path")
        except ImportError:
            # Fallback to absolute import
            from src.web.cache_manager import get_cache_manager, SessionStateManager
            logger.debug("Cache manager imported from absolute path")
        self._cache_manager = get_cache_manager()
        self._session_manager = SessionStateManager()
        
        # Performance optimization: Use LRU cache instead of unbounded dicts
        self._display_data_cache = {}  # Will be replaced by cache_manager
        self._df_cache = {}  # Will be replaced by cache_manager
        # CSS cache to avoid repeated injection
        self._css_injected = False
        # PERFORMANCE: Add timing metrics
        self._performance_metrics = {
            'last_render_time': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        logger.info("ResultsManager initialization complete")
    
    def perform_search(self, api_client, doc_type: str, filters: Dict[str, Any], limit: int) -> Optional[Dict[str, Any]]:
        """
        Perform the search using the API client
        
        Performance optimization: Limits API response to maximum 50 results to prevent
        fetching large datasets (e.g., 661+ results) that slow down the interface.
        The table displays all fetched results without scrollbar for better UX.
        """
        if not api_client:
            logger.warning("No API client available for search")
            return None
        
        logger.info(f"Performing search: doc_type={doc_type}, limit={limit}, filters={list(filters.keys())}")
        
        try:
            with st.spinner("Searching..."):
                # PERFORMANCE: Hard limit API response to 25 for optimal table performance
                api_limit = min(limit, 25)
                logger.debug(f"API limit set to {api_limit}")
                
                # Add rows parameter to limit API response
                api_filters = dict(filters)
                api_filters["rows"] = api_limit
                
                if doc_type == "drucksache":
                    logger.info("Searching Drucksachen")
                    response = api_client.get_drucksachen(**api_filters)
                elif doc_type == "vorgang":
                    logger.info("Searching Vorgänge")
                    response = api_client.get_vorgaenge(**api_filters)
                elif doc_type == "plenarprotokoll":
                    logger.info("Searching Plenarprotokolle")
                    response = api_client.get_plenarprotokolle(**api_filters)
                elif doc_type == "person":
                    logger.info("Searching Personen")
                    response = api_client.get_personen(**api_filters)
                elif doc_type == "aktivitaet":
                    logger.info("Searching Aktivitäten")
                    response = api_client.get_aktivitaeten(**api_filters)
                else:
                    logger.error(f"Unsupported document type: {doc_type}")
                    st.error(f"Unsupported document type: {doc_type}")
                    return None
                
                # Convert to list of dictionaries for easier handling
                # No need to slice since API already limited results
                documents = [doc.model_dump() for doc in response.documents]
                
                logger.info(f"Search completed: Found {response.numFound} total results, returning {len(documents)} documents")
                
                return {
                    "numFound": response.numFound,
                    "documents": documents,
                    "doc_type": doc_type,
                    "cursor": response.cursor,
                    "filters": filters,  # Store filters for analytics
                    "api_client": api_client  # Store client for analytics
                }
        
        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            st.error(f"Search failed: {str(e)}")
            return None
    
    def fetch_all_results_for_analytics(self, api_client, doc_type: str, filters: Dict[str, Any], max_results: int = 5000) -> List[Dict[str, Any]]:
        """Fetch all search results for analytics (up to max_results limit for performance)"""
        if not api_client:
            return []
        
        all_documents = []
        cursor = ""  # Start with empty cursor
        page_count = 0
        max_pages = 50  # Limit pages to prevent infinite loops
        total_found = 0
        
        try:
            with st.spinner("Fetching all results for comprehensive analytics..."):
                while len(all_documents) < max_results and page_count < max_pages:
                    # Prepare filters for this request
                    current_filters = {}
                    
                    # Copy original search filters (excluding cursor and any pagination-specific params)
                    for key, value in filters.items():
                        if key not in ["cursor"]:  # Exclude cursor from original filters
                            current_filters[key] = value
                    
                    # Add current cursor if we have one
                    if cursor:
                        current_filters["cursor"] = cursor
                    
                    # Make API request
                    try:
                        if doc_type == "drucksache":
                            response = api_client.get_drucksachen(**current_filters)
                        elif doc_type == "vorgang":
                            response = api_client.get_vorgaenge(**current_filters)
                        elif doc_type == "plenarprotokoll":
                            response = api_client.get_plenarprotokolle(**current_filters)
                        elif doc_type == "person":
                            response = api_client.get_personen(**current_filters)
                        elif doc_type == "aktivitaet":
                            response = api_client.get_aktivitaeten(**current_filters)
                        else:
                            break
                    except Exception as api_error:
                        # If we get an error with the cursor, try without it
                        if "cursor" in str(api_error).lower() and cursor:
                            st.warning(f"Cursor-based pagination failed: {str(api_error)}. Falling back to basic search.")
                            break
                        else:
                            raise api_error
                    
                    # Store total found from first response
                    if page_count == 0:
                        total_found = response.numFound
                    
                    # Convert documents to dictionaries
                    page_documents = [doc.model_dump() for doc in response.documents]
                    
                    if not page_documents:
                        break  # No more documents
                    
                    all_documents.extend(page_documents)
                    
                    # Update cursor for next page
                    new_cursor = getattr(response, 'cursor', None)
                    if not new_cursor or new_cursor == cursor or new_cursor == "*":
                        break  # No more pages or cursor hasn't changed
                    
                    cursor = new_cursor
                    page_count += 1
                    
                    # Progress update
                    if page_count % 5 == 0:
                        st.info(f"📄 Fetched {len(all_documents):,} documents so far...")
                
                # Final result message
                if len(all_documents) > 0:
                    if total_found > 0:
                        st.success(f"📊 Fetched {len(all_documents):,} documents for comprehensive analytics (from {total_found:,} total)")
                    else:
                        st.success(f"📊 Fetched {len(all_documents):,} documents for comprehensive analytics")
                else:
                    st.warning("⚠️ Could not fetch additional documents for analytics")
                    
                return all_documents[:max_results]  # Ensure we don't exceed max_results
        
        except Exception as e:
            st.error(f"Failed to fetch all results for analytics: {str(e)}")
            return []
    
    def fetch_sample_results_for_analytics(self, api_client, doc_type: str, filters: Dict[str, Any], sample_size: int = 1000) -> List[Dict[str, Any]]:
        """Fetch a representative sample of results for analytics when pagination fails"""
        if not api_client:
            return []
        
        try:
            # Remove cursor from filters for a fresh request
            clean_filters = {k: v for k, v in filters.items() if k != "cursor"}
            
            # Make a single larger request
            if doc_type == "drucksache":
                response = api_client.get_drucksachen(**clean_filters)
            elif doc_type == "vorgang":
                response = api_client.get_vorgaenge(**clean_filters)
            elif doc_type == "plenarprotokoll":
                response = api_client.get_plenarprotokolle(**clean_filters)
            elif doc_type == "person":
                response = api_client.get_personen(**clean_filters)
            elif doc_type == "aktivitaet":
                response = api_client.get_aktivitaeten(**clean_filters)
            else:
                return []
            
            # Take up to sample_size documents
            documents = [doc.model_dump() for doc in response.documents[:sample_size]]
            
            if documents:
                st.info(f"📊 Using sample of {len(documents):,} documents for analytics (from {response.numFound:,} total)")
            
            return documents
            
        except Exception as e:
            st.error(f"Failed to fetch sample results for analytics: {str(e)}")
            return []
    
    def display_search_results(self, results: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Display optimized search results with performance monitoring"""
        # PERFORMANCE: Start timing for monitoring
        import time
        start_time = time.time()
        
        if not results or not results["documents"]:
            # Enhanced no results message with suggestions
            st.markdown("""
            <div style="text-align: center; padding: 2rem; background-color: #f8f9fa; border-radius: 10px; border-left: 4px solid #ffc107;">
                <h3>🔍 No Results Found</h3>
                <p>We couldn't find any documents matching your search criteria.</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("💡 Search Suggestions", expanded=True):
                st.markdown("""
                **Try these tips to improve your search:**
                
                🎯 **Adjust Keywords:**
                - Use broader terms (e.g., "Klima" instead of "Klimaschutzgesetz")
                - Try synonyms or related terms
                - Remove quotation marks for broader matching
                
                📅 **Expand Time Range:**
                - Increase your date range
                - Try "All periods" for electoral period
                
                🔧 **Simplify Filters:**
                - Remove some advanced filters
                - Start with basic search only
                
                **📋 Popular Search Terms:**
                - Digitalisierung, Klimaschutz, Bildung, Wirtschaft, Corona
                """)
            return None
        
        # PERFORMANCE: Simple results header without CSS bloat
        total_results = results['numFound']
        actual_displayed = len(results['documents'])
        
        st.subheader("📊 Search Results")
        st.info(f"Found {total_results:,} total results (displaying {actual_displayed:,})")
        
        documents = results["documents"]
        doc_type = results["doc_type"]
        num_documents = len(documents)
        
        # Store doc_type in session state for table configuration
        st.session_state['current_doc_type'] = doc_type
        
        # PERFORMANCE CHANGE: Remove table record limitation - display all records without scrollbar
        # Performance: Use pagination for large datasets
        table_documents = documents
        
        # Show performance info for large datasets
        if num_documents > 1000:
            st.warning(f"📄 Very large dataset detected ({num_documents:,} documents). Using pagination for optimal performance.")
        elif num_documents > 500:
            st.info(f"📄 Large dataset ({num_documents:,} documents). Performance optimizations active.")
        elif num_documents > 100:
            st.success(f"📄 Medium dataset ({num_documents:,} documents). All records displayed.")
        
        # Use pagination for the limited set if still needed (when >25 of the first 50)
        # SIMPLIFIED: Remove pagination and scrolling components for performance
        # Just use direct 50-record limitation
        
        # Update documents variable to use the limited set for table display
        documents = table_documents
        
        # Create unique table identifier based on search criteria
        search_hash = hash(str(sorted(results.get('filters', {}).items())) + doc_type)
        table_key = f"search_table_{search_hash}"
        selection_key = f"selected_docs_{search_hash}"
        
        # Clean up old table data to prevent memory leaks
        self._cleanup_old_table_data(table_key)
        
        # Initialize selection state efficiently
        if selection_key not in st.session_state:
            st.session_state[selection_key] = set()
        
        # PERFORMANCE OPTIMIZATION: Cache both display data and DataFrame
        data_cache_key = f"display_data_{table_key}"
        df_cache_key = f"cached_df_{table_key}"
        
        # Only prepare display data if not cached
        if data_cache_key not in st.session_state:
            display_data = self._prepare_display_data(documents, doc_type)
            st.session_state[data_cache_key] = display_data
        else:
            display_data = st.session_state[data_cache_key]
        
        # Only create DataFrame if not cached
        if df_cache_key not in st.session_state:
            df = pd.DataFrame(display_data)
            st.session_state[df_cache_key] = df
        else:
            df = st.session_state[df_cache_key]
        
        if not df.empty:
            result = self._display_modern_table(df, documents, table_key, selection_key)
            
            # PERFORMANCE: Track render time
            render_time = time.time() - start_time
            self._performance_metrics['last_render_time'] = render_time
            
            # Show performance info for debugging
            if render_time > 2.0:
                st.caption(f"⏱️ Table rendered in {render_time:.2f}s (large dataset)")
            
            # PERFORMANCE: Display tabs only after successful table render
            if result is not None:  # Display tabs even if no documents are selected
                self._display_optimized_result_tabs()
            
            return result
        
        return None
    
    def _display_modern_table(self, df: pd.DataFrame, documents: List[Dict[str, Any]], 
                             table_key: str, selection_key: str) -> Optional[List[Dict[str, Any]]]:
        """High-performance Streamlit table with selection"""
        # Performance: Use pagination for large datasets
        from src.web.performance_utils import BrowserOptimizations
        
        total_rows = len(df)
        if total_rows == 0:
            st.info("No documents to display")
            return None
        
        # Initialize selection state
        if selection_key not in st.session_state:
            st.session_state[selection_key] = set()
        
        current_selections = st.session_state[selection_key]
        
        # Pagination for performance - upgraded to 1000 records
        if total_rows > 1000:
            start_idx, end_idx = BrowserOptimizations.create_pagination_controls(total_rows, items_per_page=1000)
            df_display = df.iloc[start_idx:end_idx].copy()
            documents_display = documents[start_idx:end_idx]
            page_offset = start_idx
        else:
            df_display = df.copy()
            documents_display = documents
            page_offset = 0
        
        # Performance optimizations
        BrowserOptimizations.add_performance_css()
        table_config = BrowserOptimizations.optimize_table_performance(len(df_display))
        
        st.caption(f"📋 Select documents ({total_rows} total, {len(df_display)} shown)")
        
        # Show selected count
        selected_count = len(current_selections)
        if selected_count > 0:
            st.info(f"✅ {selected_count} document(s) selected")
        
        # PERFORMANCE: Inject optimized styles only once per session
        if not self._css_injected:
            from static_styles import inject_styles_once
            inject_styles_once(st, "table_styles_injected")
            self._css_injected = True
        
        # Display enhanced table with tooltips and better title handling
        display_df = df_display.copy()
        
        # Store original titles for tooltips and create smart truncation
        if 'Title' in display_df.columns:
            original_titles = display_df['Title'].astype(str)
            # Smart truncation - keep more text for titles, truncate intelligently
            display_df['Title'] = original_titles.apply(self._smart_truncate_title)
            
        if 'Author' in display_df.columns:
            # Smart author truncation - only truncate if necessary
            display_df['Author'] = display_df['Author'].astype(str).apply(lambda x: self._smart_truncate_author(x))
        
        # Display table with click-to-expand functionality for long titles
        with st.expander("📋 Search Results Table", expanded=True):
            # Show column info
            col_info = st.empty()
            col_info.caption("💡 Tip: Title column shows more text now. Click rows below for full details.")
            
            # Use st.dataframe for better interaction (still performant but more features)
            st.dataframe(
                display_df,
                use_container_width=True,
                height=min(600, len(display_df) * 35 + 50) if len(display_df) <= 50 else 600,  # Dynamic height with scrolling for large datasets
                hide_index=True,  # Remove the first column with row count
                column_config={
                    "Row": st.column_config.NumberColumn("Row", width="small", help="Table row number") if 'Row' in display_df.columns else None,
                    "Title": st.column_config.TextColumn(
                        "Title",
                        help="Full document title - click to expand",
                        width="large"
                    ),
                    "Date": st.column_config.DateColumn("Date", width="small") if 'Date' in display_df.columns else None,
                    "Type": st.column_config.TextColumn("Type", width="small") if 'Type' in display_df.columns else None,
                    "Number": st.column_config.TextColumn("Number", width="small") if 'Number' in display_df.columns else None,
                    "Status": st.column_config.TextColumn("Status", width="small") if 'Status' in display_df.columns else None,
                    "Period": st.column_config.TextColumn("Period", width="small") if 'Period' in display_df.columns else None,
                    "Name": st.column_config.TextColumn("Name", width="medium") if 'Name' in display_df.columns else None,
                    "Author": st.column_config.TextColumn("Author", width="small") if 'Author' in display_df.columns else None
                }
            )
        
        # Analytics section below the table
        st.markdown("### 📊 Analytics")
        
        # Performance-optimized analytics with lazy loading
        if documents and len(documents) > 0:
            # Quick metrics (minimal DOM impact)
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Results", f"{len(documents):,}")
            
            with col2:
                # Efficient date counting using generator expression
                dated_count = sum(1 for doc in documents if doc.get('datum'))
                st.metric("With Dates", f"{dated_count:,}")
            
            with col3:
                # Memory-efficient author counting
                authors = set()
                for doc in documents[:100]:  # Limit to first 100 for performance
                    urheber = doc.get('urheber', [])
                    if urheber:
                        for urh in urheber:
                            if isinstance(urh, dict) and urh.get('bezeichnung'):
                                authors.add(urh['bezeichnung'])
                            elif isinstance(urh, str):
                                authors.add(urh)
                    # Check other author fields
                    for field in ['autor', 'initiative']:
                        if doc.get(field):
                            authors.add(doc.get(field))
                suffix = "+" if len(documents) > 100 else ""
                st.metric("Unique Authors", f"{len(authors)}{suffix}")
            
            with col4:
                # Efficient time range calculation
                dates = [doc.get('datum') for doc in documents[:100] if doc.get('datum')]
                if dates:
                    try:
                        import pandas as pd
                        parsed_dates = pd.to_datetime(dates, errors='coerce').dropna()
                        if not parsed_dates.empty:
                            time_span = (parsed_dates.max() - parsed_dates.min()).days
                            if time_span > 0:
                                st.metric("Time Span", f"{time_span} days")
                            else:
                                st.metric("Latest Date", parsed_dates.max().strftime('%Y-%m-%d'))
                        else:
                            st.metric("Time Span", "N/A")
                    except:
                        st.metric("Time Span", "N/A")
                else:
                    st.metric("Time Span", "N/A")
            
            # Expandable detailed analytics (lazy loaded to minimize DOM impact)
            with st.expander("📈 Detailed Analytics", expanded=False):
                
                # Only compute when expanded to save resources
                analytics_type = st.selectbox(
                    "Choose Analytics Type:",
                    ["Document Types", "Temporal Distribution", "Author Analysis"],
                    key="analytics_type_select"
                )
                
                if analytics_type == "Document Types":
                    # Efficient document type analysis
                    type_map = {}
                    for doc in documents[:500]:  # Limit for performance
                        doc_type = (doc.get('drucksachetyp') or 
                                   doc.get('vorgangstyp') or 
                                   doc.get('aktivitaetsart') or 'Other')
                        type_map[doc_type] = type_map.get(doc_type, 0) + 1
                    
                    if type_map:
                        # Lightweight bar chart
                        import pandas as pd
                        df = pd.DataFrame(list(type_map.items()), columns=['Type', 'Count'])
                        df = df.sort_values('Count', ascending=True).tail(8)  # Top 8 for readability
                        
                        st.bar_chart(df.set_index('Type')['Count'])
                        
                        if len(documents) > 500:
                            st.caption("📊 Analysis based on sample of 500 documents for optimal performance")
                
                elif analytics_type == "Temporal Distribution":
                    dates = [doc.get('datum') for doc in documents[:300] if doc.get('datum')]
                    if dates:
                        try:
                            import pandas as pd
                            df = pd.DataFrame({'date': pd.to_datetime(dates, errors='coerce')})
                            df = df.dropna()
                            
                            if not df.empty:
                                # Group by month for cleaner visualization
                                df['month'] = df['date'].dt.to_period('M')
                                monthly_counts = df.groupby('month').size()
                                
                                # Use streamlit's native chart for better performance
                                st.line_chart(monthly_counts.to_frame('Documents'))
                                
                                if len(documents) > 300:
                                    st.caption("📊 Analysis based on sample of 300 documents for optimal performance")
                            else:
                                st.info("No valid dates found for temporal analysis")
                        except Exception as e:
                            st.error(f"Temporal analysis failed: {str(e)}")
                    else:
                        st.info("No dates available for temporal analysis")
                
                elif analytics_type == "Author Analysis":
                    # Efficient author analysis with sampling
                    author_counts = {}
                    for doc in documents[:200]:  # Sample for performance
                        authors = []
                        
                        # Extract authors efficiently
                        urheber = doc.get('urheber', [])
                        if urheber:
                            for urh in urheber:
                                if isinstance(urh, dict) and urh.get('bezeichnung'):
                                    authors.append(urh['bezeichnung'])
                                elif isinstance(urh, str):
                                    authors.append(urh)
                        
                        # Add other author fields
                        for field in ['autor', 'initiative']:
                            if doc.get(field):
                                authors.append(doc.get(field))
                        
                        # Count authors
                        for author in authors:
                            if author:
                                author_counts[author] = author_counts.get(author, 0) + 1
                    
                    if author_counts:
                        # Show top 10 authors
                        import pandas as pd
                        df = pd.DataFrame(list(author_counts.items()), columns=['Author', 'Count'])
                        top_authors = df.nlargest(10, 'Count')
                        
                        st.bar_chart(top_authors.set_index('Author')['Count'])
                        
                        if len(documents) > 200:
                            st.caption("📊 Analysis based on sample of 200 documents for optimal performance")
                    else:
                        st.info("No author information available for analysis")
        
        else:
            st.info("📊 No documents available for analytics")
        
        # Selection interface below the analytics
        st.markdown("### 🎯 Document Selection")
        selected_documents = []
        
        # Show document selection with multiselect for current page
        if len(documents_display) > 0:
            self._display_document_selection_interface(documents_display, page_offset, selection_key)
            
            # Get current selections from session state
            current_selections = st.session_state.get(selection_key, set())
            
            # Get selected documents to return
            selected_documents = [documents[i] for i in current_selections if i < len(documents)]
            
        
        # Always return selected documents (empty list if none selected)
        # This ensures analytics and AI summaries can still be displayed
        return selected_documents
    
    def _display_document_selection_interface(self, documents_display, page_offset, selection_key):
        """Display the document selection interface below the table"""
        current_selections = st.session_state.get(selection_key, set())
        
        with st.container():
            st.write("Select documents for analysis:")
            
            # Create options for current page
            options = []
            option_map = {}
            
            for i, doc in enumerate(documents_display):
                actual_index = page_offset + i
                full_title = str(doc.get('titel', doc.get('title', 'No Title')))
                row_number = actual_index + 1  # 1-based row numbering for user-friendly reference
                
                # Extract type and author information
                doc_type_info = ""
                author_info = ""
                
                # Get document type based on document structure
                if 'drucksachetyp' in doc:
                    doc_type_info = doc.get('drucksachetyp', '')
                elif 'vorgangstyp' in doc:
                    doc_type_info = doc.get('vorgangstyp', '')
                elif 'aktivitaetsart' in doc:
                    doc_type_info = doc.get('aktivitaetsart', '')
                
                # Get author/urheber information
                author_info = self._safe_get_authors(doc)
                if not author_info:
                    # Fallback to other author fields
                    author_info = doc.get('autor', doc.get('initiative', ''))
                
                # Create enriched option label with table index, type and author
                option_parts = [f"#{row_number}"]
                # Add table index for easier reference
                option_parts.append(f"(Row {i + 1})")
                if doc_type_info:
                    option_parts.append(f"[{doc_type_info}]")
                if author_info:
                    # Truncate author if too long
                    author_display = author_info[:30] + "..." if len(author_info) > 30 else author_info
                    option_parts.append(f"({author_display})")
                option_parts.append(full_title)
                
                option_label = " ".join(option_parts)
                
                options.append(option_label)
                option_map[option_label] = actual_index
            
            # Enhanced multiselect with custom styling for full text visibility
            st.markdown("""
            <style>
            /* Enhanced dropdown styling for better title visibility with metadata */
            .stMultiSelect > div > div {
                min-width: 700px !important;
                max-width: 100% !important;
                width: 100% !important;
            }
            .stMultiSelect [data-testid="multiselect-selector"] {
                min-height: 60px;
                width: 100% !important;
            }
            .stMultiSelect [data-testid="multiselect-selector"] > div {
                flex-wrap: wrap;
                gap: 6px;
                width: 100%;
            }
            /* Style selected items - allow full text with metadata */
            .stMultiSelect [data-testid="multiselect-selector"] > div > div {
                background: linear-gradient(135deg, #e8f4fd 0%, #f0f8ff 100%);
                border: 1px solid #1f77b4;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 2px;
                max-width: 100% !important;
                white-space: normal !important;
                overflow: visible !important;
                text-overflow: unset !important;
                line-height: 1.4;
                word-wrap: break-word;
                font-size: 0.9rem;
            }
            /* Dropdown options styling - full width and height */
            .stMultiSelect [role="listbox"] {
                max-height: 500px !important;
                min-height: 200px;
                overflow-y: auto;
                width: 100% !important;
                min-width: 700px !important;
            }
            .stMultiSelect [role="option"] {
                padding: 12px 15px !important;
                border-bottom: 1px solid #eee;
                white-space: normal !important;
                word-wrap: break-word !important;
                line-height: 1.5;
                max-width: none !important;
                min-height: 50px;
                display: flex;
                align-items: flex-start;
                font-size: 0.9rem;
            }
            .stMultiSelect [role="option"]:hover {
                background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%) !important;
                transition: background 0.2s ease;
            }
            /* Highlight different parts of the option label */
            .stMultiSelect [role="option"] span:first-child {
                font-weight: 600;
                color: #0066cc;
                margin-right: 8px;
            }
            /* Ensure dropdown container respects full width */
            .stMultiSelect [data-testid="multiselect-dropdown"] {
                width: 100% !important;
                min-width: 700px !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Default selections
            default_selections = [
                opt for opt, idx in option_map.items() 
                if idx in current_selections
            ]
            
            # Enhanced multiselect with full width
            selected_options = st.multiselect(
                "Choose documents:",
                options=options,
                default=default_selections,
                key=f"multiselect_{selection_key}",
                help="🔍 Select documents for analysis. Format: #Number (Row X) [Type] (Author) Title"
            )
            
            # Update selection state
            new_selections = set(current_selections)
            
            # Remove current page selections
            page_indices = set(range(page_offset, page_offset + len(documents_display)))
            new_selections = new_selections - page_indices
            
            # Add new selections from current page
            for option in selected_options:
                if option in option_map:
                    new_selections.add(option_map[option])
            
            st.session_state[selection_key] = new_selections
    
    def _cleanup_old_table_data(self, current_table_key: str):
        """PERFORMANCE: Aggressive cleanup to prevent memory leaks"""
        keys_to_remove = []
        current_hash = current_table_key.split("_")[-1] if "_" in current_table_key else ""
        
        for key in list(st.session_state.keys()):
            # More aggressive cleanup patterns
            if (key.startswith(("search_table_", "selected_docs_", "cached_df_", 
                               "table_data_", "display_df_", "column_config_", "display_data_")) 
                and key != current_table_key 
                and not key.endswith(current_hash)):
                keys_to_remove.append(key)
        
        # PERFORMANCE: Batch removal to reduce session state operations
        for key in keys_to_remove:
            st.session_state.pop(key, None)  # Use pop to avoid KeyError
        
        # PERFORMANCE: Clear display data cache if it gets too large
        if len(self._display_data_cache) > 3:
            self._display_data_cache.clear()
    
    def _prepare_display_data(self, documents: List[Dict[str, Any]], doc_type: str) -> List[Dict[str, Any]]:
        """Prepare documents data for display in the table - OPTIMIZED"""
        # PERFORMANCE OPTIMIZATION: Use LRU cache with automatic eviction
        cache_key = self._cache_manager.get_cache_key(
            doc_type, len(documents), [d.get('id', '') for d in documents[:3]]
        )
        
        cached_data = self._cache_manager.display_cache.get(cache_key)
        if cached_data:
            self._performance_metrics['cache_hits'] += 1
            return cached_data
        
        self._performance_metrics['cache_misses'] += 1
        
        # PERFORMANCE: Use list comprehension with minimal dict operations
        display_data = self._create_optimized_display_data(documents, doc_type)
        
        # Cache the result for future use
        # Store in LRU cache with automatic eviction
        self._cache_manager.display_cache.set(cache_key, display_data)
        
        # PERFORMANCE: Limit cache size more aggressively
        # Cache management is now handled by LRU cache automatically
        # No need for manual eviction
        
        return display_data
    
    def _safe_get_authors(self, doc: Dict[str, Any]) -> str:
        """Safely extract author names from urheber field"""
        urheber = doc.get("urheber")
        if not urheber:
            return ""
        
        if not isinstance(urheber, (list, tuple)):
            return ""
            
        authors = []
        for u in urheber:
            if isinstance(u, dict) and u.get("bezeichnung"):
                authors.append(u["bezeichnung"])
        
        return ", ".join(authors)

    def _create_optimized_display_data(self, documents: List[Dict[str, Any]], doc_type: str) -> List[Dict[str, Any]]:
        """ULTRA-PERFORMANCE OPTIMIZED: Use generator for memory efficiency"""
        
        def generate_display_data():
            """Generator function for memory-efficient processing"""
            if doc_type == "drucksache":
                for i, doc in enumerate(documents):
                    yield {
                        "Row": i + 1,
                        "Type": doc.get("drucksachetyp", ""),
                        "Number": doc.get("dokumentnummer", ""),
                        "Date": doc.get("datum", "")[:10] if doc.get("datum") else "",
                        "Author": self._safe_get_authors(doc),
                        "Title": doc.get("titel", "")
                    }
            elif doc_type == "vorgang":
                for i, doc in enumerate(documents):
                    yield {
                        "Row": i + 1,
                        "Type": doc.get("vorgangstyp", ""),
                        "Status": doc.get("beratungsstand", ""),
                        "Period": doc.get("wahlperiode", ""),
                        "Author": self._safe_get_authors(doc),
                        "Title": doc.get("titel", "")
                    }
            elif doc_type == "plenarprotokoll":
                for i, doc in enumerate(documents):
                    yield {
                        "Row": i + 1,
                        "Number": doc.get("dokumentnummer", ""),
                        "Date": doc.get("datum", "")[:10] if doc.get("datum") else "",
                        "Title": doc.get("titel", "")
                    }
            elif doc_type == "person":
                for i, doc in enumerate(documents):
                    yield {
                        "Row": i + 1,
                        "Name": f"{doc.get('vorname', '')} {doc.get('nachname', '')}".strip(),
                        "Date": doc.get("aktualisiert", "")[:10] if doc.get("aktualisiert") else ""
                    }
            elif doc_type == "aktivitaet":
                for i, doc in enumerate(documents):
                    yield {
                        "Row": i + 1,
                        "Title": doc.get("titel", ""),
                        "Date": doc.get("datum", "")[:10] if doc.get("datum") else ""
                    }
        
        # PERFORMANCE: Process generator in batches for large datasets
        if len(documents) > 100:
            # Use batched processing for large datasets
            result = []
            batch_size = 50
            for batch_start in range(0, len(documents), batch_size):
                batch_end = min(batch_start + batch_size, len(documents))
                batch_docs = documents[batch_start:batch_end]
                # Process batch
                for item in generate_display_data():
                    result.append(item)
                    if len(result) >= batch_end:
                        break
            return result
        else:
            # Convert generator to list for small datasets
            return list(generate_display_data())
    
    def _show_performance_metrics(self):
        """Display performance metrics for debugging"""
        # Performance metrics removed for cleaner UI
        pass
    
    def _extract_urheber_bezeichnung(self, urheber_list: List[Dict[str, Any]]) -> str:
        """Extract bezeichnung from urheber list"""
        if not urheber_list:
            return ""
        
        # Get all bezeichnung values from the urheber list
        bezeichnungen = []
        for urheber in urheber_list:
            if isinstance(urheber, dict) and urheber.get("bezeichnung"):
                bezeichnungen.append(urheber["bezeichnung"])
        
        # Join multiple bezeichnungen with commas
        return ", ".join(bezeichnungen) if bezeichnungen else ""
    
    def _truncate_title(self, title: str, max_length: int = 100) -> str:
        """Truncate title if too long"""
        if len(title) > max_length:
            return title[:max_length] + "..."
        return title
    
    def _smart_truncate_title(self, title: str, max_length: int = 120) -> str:
        """Enhanced smart truncation for table display - preserves key information"""
        if not title or len(title) <= max_length:
            return title
        
        # Try to truncate at natural break points (punctuation, spaces)
        if max_length < len(title):
            # Look for good break points near the max length
            truncate_pos = max_length
            
            # Look backward for natural break points
            for i in range(min(max_length, len(title)) - 1, max(0, max_length - 20), -1):
                if title[i] in '.,;:-–— ':
                    truncate_pos = i + 1
                    break
            
            # Ensure we don't truncate too early
            if truncate_pos < max_length * 0.7:
                truncate_pos = max_length
                
            return title[:truncate_pos].rstrip() + "..."
        
        return title
    
    def _smart_truncate_dropdown_title(self, title: str, max_length: int = 90) -> str:
        """Smart truncation specifically for dropdown display"""
        if not title or len(title) <= max_length:
            return title
        
        # For dropdown, prioritize key terms at the beginning
        # Look for natural break points but prefer earlier truncation for readability
        truncate_pos = max_length
        
        # Look for break points in the latter part first
        for i in range(min(max_length - 5, len(title)), max(max_length - 25, 0), -1):
            if title[i] in '.,;: ':
                truncate_pos = i + 1
                break
        
        return title[:truncate_pos].rstrip() + "..."
    
    def _smart_truncate_author(self, author: str, max_length: int = 50) -> str:
        """Smart truncation for author names - prioritizes important information"""
        if not author or len(author) <= max_length:
            return author
        
        # For author names, try to preserve full names when possible
        # Split by comma to separate multiple authors
        if ',' in author:
            authors = author.split(',')
            result = []
            current_length = 0
            
            for auth in authors:
                auth = auth.strip()
                # Add ", " for subsequent authors
                additional_length = len(auth) + (2 if result else 0)
                
                if current_length + additional_length <= max_length:
                    result.append(auth)
                    current_length += additional_length
                else:
                    # If we have at least one author, add indicator of more
                    if result:
                        if current_length + 6 <= max_length:  # ", +X more"
                            remaining = len(authors) - len(result)
                            result.append(f"+{remaining} more")
                        else:
                            result.append("...")
                    else:
                        # First author is too long, truncate it
                        available = max_length - 3  # Reserve space for "..."
                        result.append(auth[:available] + "...")
                    break
            
            return ", ".join(result)
        else:
            # Single author, simple truncation
            return author[:max_length-3] + "..." if len(author) > max_length else author
    
    def _fast_extract_urheber(self, urheber_list: List[Dict[str, Any]]) -> str:
        """Fast optimized urheber extraction"""
        if not urheber_list:
            return ""
        
        # Use list comprehension for better performance
        bezeichnungen = [u.get("bezeichnung", "") for u in urheber_list if isinstance(u, dict) and u.get("bezeichnung")]
        return ", ".join(bezeichnungen)
    
    def _fast_format_date(self, date_str: str) -> str:
        """Fast date formatting without heavy imports"""
        if not date_str:
            return ""
        # Simple date formatting - avoid heavy datetime operations
        return date_str[:10] if len(date_str) >= 10 else date_str
    
    def _fast_truncate_title(self, title: str, max_length: int = 100) -> str:
        """Fast title truncation"""
        if not title:
            return ""
        return title[:max_length] + "..." if len(title) > max_length else title
    
    def display_action_buttons(self, selected_documents: List[Dict[str, Any]], doc_type: str, 
                             openai_available: bool = False) -> Dict[str, bool]:
        """PERFORMANCE: Streamlined action buttons without CSS bloat"""
        
        if not selected_documents:
            st.info("📋 Select documents from the table above to access analysis tools")
            return {}
        
        

        
        button_states = {}
        
        # PERFORMANCE: Simple AI analysis section without CSS bloat
        st.markdown("### 🧠 AI Analysis")
        
        if openai_available:
            button_states['get_summaries_streaming'] = st.button(
                "🧠 Start AI Analysis",
                key="get_summaries_streaming",
                type="primary",
                use_container_width=True,
                help="Generate AI summaries and citizen impact analysis"
            )
            
            st.info("📝 Generate AI-powered document analysis and insights")
            
        else:
            st.button(
                "🧠 Start AI Analysis", 
                key="get_summaries_streaming", 
                disabled=True,
                type="primary",
                use_container_width=True,
                help="AI analysis requires OpenAI configuration"
            )
            
            # Get more specific error information
            openai_status = st.session_state.get('openai_status', 'not_initialized')
            if 'error:' in str(openai_status):
                error_details = str(openai_status).replace('error: ', '')
                st.warning(f"⚙️ OpenAI integration not available: {error_details}")
            else:
                st.warning("⚙️ OpenAI integration not available. Please configure your API key.")
            
            button_states['get_summaries_streaming'] = False
        
        return button_states
    
    def _display_optimized_result_tabs(self):
        """Display AI summaries if available"""
        
        # Check if we have data to display
        has_summaries = bool(st.session_state.get('document_summaries'))
        
        # Show AI summaries if available
        if has_summaries:
            st.markdown("---")
            st.markdown("### 🧠 AI Analysis Results")
            self._display_ai_summaries_lazy()
    
    def _display_ai_summaries_lazy(self):
        """PERFORMANCE: Lazy load AI summaries to prevent browser freezing"""
        summaries = st.session_state.get('document_summaries', {})
        
        if not summaries:
            st.info("🧠 No AI summaries available yet. Select documents and generate summaries using the action buttons.")
            return
        
        # PERFORMANCE: Limit display and use expanders to prevent DOM overload
        st.markdown(f"**🧠 AI-Generated Summaries ({len(summaries)}):**")
        
        # PERFORMANCE: Only show first 5 summaries by default to prevent DOM bloat
        display_limit = 5
        summary_items = list(summaries.items())
        
        if len(summary_items) > display_limit:
            st.warning(f"⚠️ Showing {display_limit} of {len(summary_items)} summaries for optimal performance.")
            display_limit = len(summary_items)  # Show all summaries
        
        for i, (doc_id, summary_data) in enumerate(summary_items[:display_limit]):
            # PERFORMANCE: Use expanders to prevent all content loading at once
            title = summary_data.get('document', {}).get('titel', f'Document {doc_id}')
            title = title[:50] + "..." if len(title) > 50 else title
            
            with st.expander(f"📄 {title}", expanded=False):
                summary_text = summary_data.get('summary', 'No summary available')
                if len(summary_text) > 1000:
                    # PERFORMANCE: Truncate very long summaries
                    st.write(summary_text[:1000] + "...")
                    if st.button(f"Show full summary", key=f"expand_summary_{doc_id}"):
                        st.write(summary_text)
                else:
                    st.write(summary_text)
                
                # PERFORMANCE: Only show citizen impact if available and not too long
                citizen_impact = summary_data.get('citizen_impact')
                if citizen_impact and len(citizen_impact) < 500:
                    st.markdown("**🏛️ Citizen Impact:**")
                    st.write(citizen_impact)
                elif citizen_impact:
                    st.markdown("**🏛️ Citizen Impact:**")
                    st.write(citizen_impact[:300] + "...")
    
    
    # Remove the old method
    def _display_document_result_tabs(self):
        """DEPRECATED: Use _display_optimized_result_tabs instead"""
        pass
