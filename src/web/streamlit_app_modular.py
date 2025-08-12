"""
Modular Streamlit Application for Bundestag.AI Lens
Main application that orchestrates all components.
Enhanced with security features and input validation.
"""

import streamlit as st
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# ⚡ PERFORMANCE: Lazy imports for faster startup
def lazy_import_pandas():
    import pandas as pd
    return pd

def lazy_import_plotly():
    import plotly.express as px
    return px

def lazy_import_asyncio():
    import asyncio
    return asyncio

def lazy_import_datetime():
    from datetime import datetime
    return datetime

def lazy_import_json():
    import json
    return json

def lazy_import_time():
    import time
    return time

def lazy_import_random():
    import random
    return random

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ⚡ PERFORMANCE: Lazy imports for heavy modules
def lazy_import_api_client():
    from src.api.client import BundestagAPIClient
    return BundestagAPIClient

def lazy_import_helpers():
    from src.utils.helpers import format_date
    return format_date

def lazy_import_security():
    from src.security import validate_environment_security, SecurityMonitor
    return validate_environment_security, SecurityMonitor

# Import our modular components
try:
    from .openai_handler import OpenAIHandler
    from .ui_components import SummaryDisplayManager, AnalyticsDisplayManager
    from .search_manager import SearchManager, ResultsManager
    from .performance_utils import PerformanceMonitor, BrowserOptimizations
except ImportError:
    # Fallback to direct imports when running as main module
    from openai_handler import OpenAIHandler
    from ui_components import SummaryDisplayManager, AnalyticsDisplayManager
    from search_manager import SearchManager, ResultsManager
    try:
        from performance_utils import PerformanceMonitor, BrowserOptimizations
    except ImportError:
        # Create dummy classes if performance utils not available
        class PerformanceMonitor:
            def __init__(self): pass
            def start_monitoring(self): pass
            def check_performance_threshold(self, *args, **kwargs): return True
            def end_monitoring(self): return {}
        
        class BrowserOptimizations:
            @staticmethod
            def add_performance_css(): 
                """Dummy CSS performance function"""
                pass
            @staticmethod
            def get_optimized_plotly_config(): return {}
            @staticmethod
            def optimize_dataframe_display(df): return df
            @staticmethod
            def optimize_plotly_config(): return {}
            @staticmethod
            def optimize_table_performance(df_size): return {"use_container_width": True, "hide_index": True}
            @staticmethod
            def create_pagination_controls(total_items, items_per_page=1000): return (0, min(total_items, items_per_page))


class BundestagStreamlitApp:
    """Main Streamlit application for Bundestag.AI Lens"""
    
    def __init__(self):
        """⚡ Fast startup with lazy initialization"""
        # Defer security checks until first interaction
        self._security_checked = False
        
        # Lazy-loaded components
        self.api_client = None
        self.openai_handler = None
        self._performance_monitor = None
        self._summary_display = None
        self._analytics_display = None
        self._search_manager = None
        self._results_manager = None
        
        # Fast startup initialization only
        self.init_session_state()
        self.setup_clients()  # Initialize client status
        self.configure_page_minimal()
        
        # Mark that components need initialization when accessed
        self._components_loaded = False
    
    def ensure_security_check(self):
        """Check security only when needed"""
        if not self._security_checked:
            validate_func, _ = lazy_import_security()
            security_issues = validate_func()
            if security_issues:
                for issue in security_issues:
                    st.warning(f"🔐 Security: {issue}")
            self._security_checked = True
    
    def ensure_components_loaded(self):
        """Load components only when first accessed"""
        if not self._components_loaded:
            self._performance_monitor = PerformanceMonitor()
            self._summary_display = SummaryDisplayManager()
            self._analytics_display = AnalyticsDisplayManager()
            self._search_manager = SearchManager()
            self._results_manager = ResultsManager()
            self._components_loaded = True
    
    # Property accessors for lazy loading
    @property
    def performance_monitor(self):
        if self._performance_monitor is None:
            self._performance_monitor = PerformanceMonitor()
        return self._performance_monitor
    
    @property
    def summary_display(self):
        if self._summary_display is None:
            self._summary_display = SummaryDisplayManager()
        return self._summary_display
    
    @property
    def analytics_display(self):
        if self._analytics_display is None:
            self._analytics_display = AnalyticsDisplayManager()
        return self._analytics_display
    
    @property
    def search_manager(self):
        if self._search_manager is None:
            self._search_manager = SearchManager()
        return self._search_manager
    
    @property
    def results_manager(self):
        if self._results_manager is None:
            self._results_manager = ResultsManager()
        return self._results_manager
    
    def configure_page_minimal(self):
        """⚡ Minimal page configuration for fast startup"""
        if 'page_configured' not in st.session_state:
            st.set_page_config(
                page_title="Bundestag.AI Lens",
                page_icon="🏛️",
                layout="wide",
                initial_sidebar_state="expanded"
            )
            st.session_state.page_configured = True
    
    def configure_page_full(self):
        """Full page configuration - load CSS when needed"""
        if 'full_css_loaded' not in st.session_state:
            # Add performance optimizations
            try:
                BrowserOptimizations.add_performance_css()
            except (AttributeError, NameError) as e:
                st.error(f"Performance CSS loading failed: {e}")
                # Continue without performance CSS
            
            # Essential CSS only
            st.markdown("""
            <style>
                .main-header {
                    font-size: 2.2rem;
                    color: #1f77b4;
                    text-align: center;
                    margin-bottom: 1.5rem;
                }
                .stButton > button {
                    background-color: #1f77b4;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 0.4rem 1.5rem;
                }
                .stButton > button:hover {
                    background-color: #155a8a;
                }
            </style>
            """, unsafe_allow_html=True)
            st.session_state.full_css_loaded = True
    
    def init_session_state(self):
        """Initialize session state variables with cleanup"""
        # PERFORMANCE: Clean up orphaned session state keys periodically
        from src.web.cache_manager import SessionStateManager
        
        # Clean orphaned keys on initialization
        if 'last_cleanup' not in st.session_state:
            removed_count = SessionStateManager.cleanup_orphaned_keys(st.session_state)
            st.session_state.last_cleanup = lazy_import_time().time()
            if removed_count > 0:
                print(f"Cleaned up {removed_count} orphaned session state keys")
        else:
            # Clean up every 5 minutes
            current_time = lazy_import_time().time()
            if current_time - st.session_state.last_cleanup > 300:
                removed_count = SessionStateManager.cleanup_orphaned_keys(st.session_state)
                st.session_state.last_cleanup = current_time
                if removed_count > 0:
                    print(f"Periodic cleanup: removed {removed_count} orphaned keys")
        
        # Initialize core session state variables
        session_vars = {
            'search_results': None,
            'selected_documents': [],
            'api_connection_status': None,
            'openai_status': None,
            'document_summaries': {},
            'show_architecture_modal': False,
            'show_api_guide_modal': False,
            'show_help_modal': False
        }
        
        for var, default_value in session_vars.items():
            if var not in st.session_state:
                st.session_state[var] = default_value
    
    def setup_clients(self):
        """⚡ Setup API clients with lazy loading"""
        # Setup Bundestag API client only when needed
        if self.api_client is None and 'api_connection_status' not in st.session_state:
            st.session_state.api_connection_status = "not_initialized"
        
        # Defer OpenAI setup until actually needed
        if 'openai_status' not in st.session_state:
            st.session_state.openai_status = "not_initialized"
    
    def ensure_api_client(self):
        """Initialize API client only when needed"""
        if self.api_client is None:
            try:
                BundestagAPIClient = lazy_import_api_client()
                self.api_client = BundestagAPIClient()
                st.session_state.api_connection_status = "connected"
            except Exception as e:
                st.session_state.api_connection_status = f"error: {str(e)}"
    
    def ensure_openai_client(self):
        """Initialize OpenAI client only when needed"""
        current_status = st.session_state.get('openai_status', 'not_initialized')
        
        # Only try to initialize if we don't have a working handler or status shows not initialized
        if (self.openai_handler is None or 
            not (self.openai_handler and self.openai_handler.is_available()) or
            current_status == "not_initialized"):
            
            # Get OpenAI API key
            openai_api_key = os.getenv('OPENAI_API_KEY')
            
            if not openai_api_key:
                try:
                    openai_api_key = st.secrets.get("OPENAI_API_KEY")
                except:
                    pass
            
            if openai_api_key:
                try:
                    self.openai_handler = OpenAIHandler(openai_api_key)
                    if self.openai_handler.is_available():
                        st.session_state.openai_status = "connected"
                    else:
                        st.session_state.openai_status = "error: Failed to initialize"
                except Exception as e:
                    st.session_state.openai_status = f"error: {str(e)}"
                    self.openai_handler = None
            else:
                st.session_state.openai_status = "error: No OpenAI API key found. Set OPENAI_API_KEY environment variable."
    
    def display_header(self):
        """Display the main header with connection status"""
        # Load full CSS when displaying UI
        self.configure_page_full()
        # Perform security check when UI is first shown
        self.ensure_security_check()
        
        # Connection status
        col1, col2 = st.columns(2)
        
        with col1:
            api_status = st.session_state.get('api_connection_status', 'not_initialized')
            if api_status == "connected":
                st.success("✅ Connected to Bundestag DIP API")
            elif api_status and "error" in str(api_status):
                st.error("❌ API Connection failed")
            elif api_status == "not_initialized":
                st.info("⚡ API Ready (will connect when needed)")
            else:
                st.info("🔄 Connecting to API...")
        
        with col2:
            openai_status = st.session_state.get('openai_status', 'not_initialized')
            if openai_status == "connected":
                st.success("🤖 OpenAI Connected")
            elif openai_status and "error" in str(openai_status):
                st.error("❌ OpenAI Connection failed")
            elif openai_status == "not_initialized":
                st.info("⚡ OpenAI Ready (will connect when needed)")
            else:
                st.info("🔄 Connecting to OpenAI...")
    
    def handle_search_and_results(self):
        """Handle search form and results display"""
        # Ensure API client is available
        self.ensure_api_client()
        
        # Search form in sidebar
        doc_type, filters, limit, search_clicked = self.search_manager.display_sidebar_search_form()
        
        # Perform search if requested
        if search_clicked and self.api_client:
            results = self.results_manager.perform_search(self.api_client, doc_type, filters, limit)
            if results:

                st.session_state.search_results = results
        
        # Display results and handle selection
        if st.session_state.search_results:
            # Performance optimization: Monitor large dataset operations
            num_results = len(st.session_state.search_results.get("documents", []))
            self.performance_monitor.check_performance_threshold(num_results, "table display")
            
            selected_documents = self.results_manager.display_search_results(st.session_state.search_results)
            
            # Always ensure we have selected_documents as a list (even if empty)
            if selected_documents is None:
                selected_documents = []
            
            # Performance optimization: Only update session state if selection actually changed
            if selected_documents:
                # Check if selection has changed to avoid unnecessary processing
                current_selection_ids = [doc.get('id', '') for doc in selected_documents]
                previous_selection_ids = [doc.get('id', '') for doc in st.session_state.get('selected_documents', [])]
                
                if current_selection_ids != previous_selection_ids:
                    st.session_state.selected_documents = selected_documents
                    
                    # Add performance warning for large selections
                    if len(selected_documents) > 20:
                        st.warning(f"⚠️ Large selection ({len(selected_documents)} documents) may impact performance. Consider selecting fewer documents for optimal experience.")
            else:
                # Clear selection if no documents selected
                if st.session_state.get('selected_documents'):
                    st.session_state.selected_documents = []
                
            # Always display action buttons and ensure OpenAI client is available
            self.ensure_openai_client()
            
            # Display action buttons (even if no documents selected)
            button_states = self.results_manager.display_action_buttons(
                selected_documents, 
                st.session_state.search_results["doc_type"],
                openai_available=self.openai_handler is not None and self.openai_handler.is_available()
            )
            
            # Handle button clicks
            if button_states:
                self.handle_action_buttons(button_states, selected_documents, st.session_state.search_results["doc_type"])
        else:
            # Display welcome screen when no search results
            self.search_manager.display_welcome_screen()
    
    def handle_action_buttons(self, button_states: Dict[str, bool], selected_documents: List[Dict[str, Any]], doc_type: str):
        """Handle clicks on action buttons - Only streaming summaries supported"""
        if button_states.get('get_summaries_streaming'):
            # Ensure OpenAI client is available
            self.ensure_openai_client()
            
            if self.openai_handler:
                # Run async streaming function
                asyncio = lazy_import_asyncio()
                asyncio.run(self.generate_summaries_for_selected_streaming(selected_documents, doc_type))
    
    async def generate_summaries_for_selected_streaming(self, documents: List[Dict[str, Any]], doc_type: str):
        """Generate OpenAI summaries for selected documents with real-time streaming"""
        if not self.openai_handler:
            st.error("OpenAI handler not available")
            return

        if not self.api_client:
            st.error("Bundestag API client not available")
            return

        if not self.openai_handler.async_client:
            st.error("OpenAI async client not available for streaming")
            return

        # Store summary display reference for access in OpenAI handler
        st.session_state.summary_display = self.summary_display

        # Create streaming display placeholders
        placeholders = self.summary_display.create_streaming_display_placeholders(len(documents), doc_type)

        summaries = []
        successful_count = 0

        for i, document in enumerate(documents):
            try:
                # Update progress
                current = i + 1
                title = document.get('titel', 'No title')
                self.summary_display.update_streaming_progress(placeholders, current, len(documents), title)

                # Get document placeholders
                doc_placeholder = placeholders['doc_placeholders'][i]

                # Log document processing start
                doc_id = document.get('id', 'unknown')

                # Fetch full text (empty string is returned if no text available)
                full_text = self.openai_handler._fetch_full_text(self.api_client, doc_id, doc_type)

                # Process document regardless of whether full text is available
                # If no full text, the system will generate summary based on metadata
                if full_text is not None and not full_text.startswith('Error'):
                    # Generate streaming summary (works with empty string for metadata-only processing)
                    summary = await self.openai_handler.generate_summary_streaming(
                        document, full_text, doc_type, 
                        doc_placeholder
                    )

                    if summary and not summary.startswith('Error'):
                        # Show citizen impact processing
                        self.summary_display.update_citizen_impact_placeholder(doc_placeholder, "", document, False)
                        
                        # Generate streaming citizen impact analysis
                        citizen_impact = await self.openai_handler.generate_citizen_impact_summary_streaming(
                            document, summary, doc_type,
                            doc_placeholder['citizen_impact']
                        )

                        # Update citizen impact display with final result
                        if citizen_impact and not citizen_impact.startswith('Error'):
                            self.summary_display.update_citizen_impact_placeholder(doc_placeholder, citizen_impact, document, True)
                            # Store in session state for later access
                            self.summary_display.store_citizen_impact_analysis(doc_id, citizen_impact)

                        # Store results
                        datetime = lazy_import_datetime()
                        summary_data = {
                            'doc_id': doc_id,
                            'document': document,
                            'summary': summary,
                            'citizen_impact': citizen_impact if not citizen_impact.startswith('Error') else '',
                            'full_text': full_text,
                            'timestamp': datetime.now().isoformat()
                        }

                        summaries.append(summary_data)
                        successful_count += 1

                        # Store in session state
                        if 'document_summaries' not in st.session_state:
                            st.session_state.document_summaries = {}
                        
                        datetime = lazy_import_datetime()
                        st.session_state.document_summaries[doc_id] = {
                            'summary': summary,
                            'citizen_impact': citizen_impact if not citizen_impact.startswith('Error') else '',
                            'full_text': full_text,
                            'document': document,
                            'timestamp': datetime.now().isoformat()
                        }

                    else:
                        doc_placeholder['summary'].error(f"Failed to generate summary: {summary}")

                else:
                    doc_placeholder['summary'].error(f"Failed to fetch document text: {full_text}")

            except Exception as e:
                error_msg = f"Error processing document {i+1}: {str(e)}"
                st.error(error_msg)
                doc_placeholder['summary'].error(error_msg)

        # Complete processing
        self.summary_display.complete_streaming_display(placeholders, successful_count, len(documents))

        st.success(f"✅ Streaming processing completed! {successful_count}/{len(documents)} summaries generated successfully")

        return summaries
    
    def check_and_handle_citizen_impact_requests(self):
        """Check for and handle citizen impact analysis requests"""
        requests = self.summary_display.check_citizen_impact_requests()
        
        if requests and self.openai_handler:
            for doc_id in requests:
                # Find the document and its data
                document_data = None
                ai_summary = ""
                doc_type = ""
                
                # Look for the document in session state
                for stored_doc_id, summary_data in st.session_state.document_summaries.items():
                    if stored_doc_id == doc_id:
                        ai_summary = summary_data.get('summary', '')
                        break
                
                # Find the document from current search results
                if st.session_state.search_results:
                    doc_type = st.session_state.search_results["doc_type"]
                    for doc in st.session_state.search_results["documents"]:
                        if str(doc.get('id')) == str(doc_id):
                            document_data = doc
                            break
                
                if document_data and ai_summary:
                    # Preserve current modal state before generation
                    modal_was_open = st.session_state.get('show_summary_modal', False)
                    modal_data = st.session_state.get('modal_summary_data', None)
                    
                    with st.spinner(f"🏛️ Generating citizen impact analysis for document {doc_id}..."):
                        try:
                            # Generate citizen impact analysis using the AI summary
                            citizen_impact = self.openai_handler.generate_citizen_impact_summary(
                                document_data, 
                                ai_summary, 
                                doc_type
                            )
                            
                            # Store the analysis
                            self.summary_display.store_citizen_impact_analysis(doc_id, citizen_impact)
                            
                            st.success(f"✅ Citizen impact analysis generated for document {doc_id}")
                            
                            # Explicitly restore modal state after generation
                            if modal_was_open and modal_data:
                                st.session_state.show_summary_modal = True
                                st.session_state.modal_summary_data = modal_data
                            
                            # Clear the preserve state flag 
                            if 'modal_preserve_state' in st.session_state:
                                del st.session_state.modal_preserve_state
                            
                            # Rerun to update the modal content
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Failed to generate citizen impact analysis: {str(e)}")
                            st.session_state.generating_citizen_impact = False
                            
                            # Restore modal state on error too
                            if modal_was_open and modal_data:
                                st.session_state.show_summary_modal = True
                                st.session_state.modal_summary_data = modal_data
                                
                            # Clear the preserve state flag on error
                            if 'modal_preserve_state' in st.session_state:
                                del st.session_state.modal_preserve_state
                else:
                    # No document data or AI summary available
                    if not document_data:
                        st.error(f"Document data not found for ID {doc_id}")
                    elif not ai_summary:
                        st.error(f"AI summary not available for document {doc_id}. Please generate a summary first.")
                    st.session_state.generating_citizen_impact = False
                    # Clear the preserve state flag
                    if 'modal_preserve_state' in st.session_state:
                        del st.session_state.modal_preserve_state
    
    def display_analytics_tab(self):
        """Analytics functionality has been removed to improve performance"""
        st.info("📊 Analytics functionality has been temporarily disabled to improve performance with large datasets.")
    
    def plot_drucksache_analytics(self, documents: List[Dict[str, Any]]):
        """Analytics functionality has been removed to improve performance"""
        st.info("📊 Drucksache analytics have been temporarily disabled to improve performance with large datasets.")
    
    def plot_urheber_analytics(self, documents: List[Dict[str, Any]]):
        """Analytics functionality has been removed to improve performance"""
        st.info("📊 Urheber analytics have been temporarily disabled to improve performance with large datasets.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.spinner("Analyzing Urheber distribution..."):
                # Performance: Use list comprehension with flattening for better efficiency
                urheber_list = []
                
                # Batch processing for better performance
                batch_size = 500
                total_batches = (len(documents) - 1) // batch_size + 1
                
                if total_batches > 1:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                
                for batch_idx in range(total_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, len(documents))
                    batch = documents[start_idx:end_idx]
                    
                    if total_batches > 1:
                        progress = (batch_idx + 1) / total_batches
                        progress_bar.progress(progress)
                        status_text.text(f"Processing batch {batch_idx + 1}/{total_batches}...")
                    
                    # Process batch
                    for doc in batch:
                        urheber = doc.get('urheber', [])
                        if urheber:
                            for urh in urheber:
                                if isinstance(urh, dict) and urh.get('bezeichnung'):
                                    urheber_list.append(urh['bezeichnung'])
                                elif isinstance(urh, str):
                                    urheber_list.append(urh)
                
                if total_batches > 1:
                    progress_bar.progress(1.0)
                    status_text.text("Processing complete!")
                
                if urheber_list:
                    # Performance: Use Counter for faster counting
                    from collections import Counter
                    urheber_counts = Counter(urheber_list)
                    pd = lazy_import_pandas()
                    urheber_counts = pd.Series(urheber_counts).sort_values(ascending=False)
                    
                    # Limit categories for performance - reduced thresholds
                    if len(urheber_counts) > 10:
                        top_urheber = urheber_counts.head(8)
                        others_count = urheber_counts.tail(len(urheber_counts) - 8).sum()
                        if others_count > 0:
                            top_urheber['Others'] = others_count
                        urheber_counts = top_urheber
                    
                    # Optimized Plotly config
                    config = BrowserOptimizations.optimize_plotly_config()
                    config.update({
                        'displayModeBar': False,
                        'staticPlot': False,
                        'doubleClick': False
                    })
                    
                    px = lazy_import_plotly()
                    fig = px.pie(
                        values=urheber_counts.values,
                        names=urheber_counts.index,
                        title=f"Urheber Distribution ({len(documents):,} documents)" + 
                              (f" from {original_count:,} total" if original_count != len(documents) else ""),
                        hole=0.3  # Make it a donut chart for better readability
                    )
                    
                    # Performance optimizations
                    fig.update_traces(
                        textposition='inside', 
                        textinfo='percent+label',
                        hovertemplate='%{label}<br>Count: %{value}<br>Percentage: %{percent}<extra></extra>',
                        marker_line_width=0
                    )
                    
                    fig.update_layout(
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                        margin=dict(t=50, b=50, l=50, r=50),
                        height=400
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, config=config)
                else:
                    st.info("No urheber data available for visualization")
        
        with col2:
            # Show urheber statistics with bar chart
            if urheber_list:
                st.metric("Total Urheber Entries", f"{len(urheber_list):,}")
                st.metric("Unique Urheber", len(set(urheber_list)))
                
                # Create bar chart for top urheber
                pd = lazy_import_pandas()
                top_urheber = pd.Series(urheber_list).value_counts()
                
                # Limit to top 10 for the bar chart
                top_10_urheber = top_urheber.head(10)
                
                # Optimized Plotly config for bar chart
                config = BrowserOptimizations.optimize_plotly_config()
                config.update({
                    'displayModeBar': False,
                    'staticPlot': False,
                    'doubleClick': False
                })
                
                px = lazy_import_plotly()
                fig_bar = px.bar(
                    x=top_10_urheber.values,
                    y=top_10_urheber.index,
                    orientation='h',
                    title="Top 10 Urheber by Document Count",
                    labels={'x': 'Number of Documents', 'y': 'Urheber'},
                    color=top_10_urheber.values,
                    color_continuous_scale='Blues'
                )
                
                # Update layout for better readability
                fig_bar.update_layout(
                    showlegend=False,
                    margin=dict(t=50, b=30, l=150, r=30),
                    height=400,
                    xaxis_title="Document Count",
                    yaxis_title="",
                    coloraxis_showscale=False
                )
                
                # Add value labels on bars
                fig_bar.update_traces(
                    texttemplate='%{x:,.0f}',
                    textposition='outside',
                    hovertemplate='%{y}<br>Documents: %{x:,.0f}<extra></extra>'
                )
                
                st.plotly_chart(fig_bar, use_container_width=True, config=config)
            else:
                st.info("No urheber statistics available")
        
        # Add Urheber timeseries chart below
        st.markdown("#### 📊 Urheber Distribution Over Time")
        self._plot_urheber_timeseries(documents)
    
    def _plot_urheber_timeseries(self, documents: List[Dict[str, Any]]):
        """Create a stacked bar chart showing Urheber distribution over time"""
        
        # Performance optimization: Handle large datasets - reduced thresholds
        original_count = len(documents)
        if original_count > 1000:  # Reduced threshold
            st.warning(f"⚠️ Large dataset detected ({original_count:,} documents). Using optimized sampling for better performance.")
            documents = self._sample_documents_for_visualization(documents, max_size=800)  # Reduced sample size
            st.info(f"📊 Using representative sample of {len(documents):,} documents for visualization")
        
        # Performance: Batch processing for better efficiency
        data_rows = []
        batch_size = 200  # Process in smaller batches
        total_batches = (len(documents) - 1) // batch_size + 1
        
        if total_batches > 1:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(documents))
            batch = documents[start_idx:end_idx]
            
            if total_batches > 1:
                progress = (batch_idx + 1) / total_batches
                progress_bar.progress(progress)
                status_text.text(f"Processing batch {batch_idx + 1}/{total_batches}...")
            
            # Process batch efficiently
            for doc in batch:
                # Get date
                date_str = doc.get('datum')
                if not date_str:
                    continue
                    
                try:
                    pd = lazy_import_pandas()
                    date = pd.to_datetime(date_str)
                except:
                    continue
                
                # Get urheber
                urheber_list = doc.get('urheber', [])
                if not urheber_list:
                    continue
                
                # Extract urheber names
                for urh in urheber_list:
                    if isinstance(urh, dict) and urh.get('bezeichnung'):
                        urheber_name = urh['bezeichnung']
                    elif isinstance(urh, str):
                        urheber_name = urh
                    else:
                        continue
                    
                    data_rows.append({
                        'date': date,
                        'urheber': urheber_name
                    })
        
        # Clear progress indicators
        if total_batches > 1:
            progress_bar.progress(1.0)
            status_text.text("Processing complete!")
            
        if not data_rows:
            st.info("No date and urheber information available for timeseries chart")
            return
        
        # Performance check: Limit data complexity - reduced thresholds
        if len(data_rows) > 5000:  # Reduced from 10000
            st.warning(f"⚠️ Very large dataset ({len(data_rows):,} data points). Further sampling applied.")
            # Sample data points while maintaining temporal distribution
            data_rows = self._sample_data_points(data_rows, max_points=4000)  # Reduced from 8000
        
        with st.spinner("Creating visualization..."):
            # Performance: Create DataFrame more efficiently
            pd = lazy_import_pandas()
            df = pd.DataFrame(data_rows)
            df['year_month'] = df['date'].dt.to_period('M')
            
            # Performance: Use more efficient aggregation
            grouped = df.groupby(['year_month', 'urheber']).size().reset_index(name='count')
            
            # Get top urheber to avoid too many categories - reduced further
            top_urheber = df['urheber'].value_counts().head(6).index.tolist()  # Reduced from 8 to 6
            
            # Filter to top urheber and group others
            grouped['urheber_display'] = grouped['urheber'].apply(
                lambda x: x if x in top_urheber else 'Others'
            )
            
            # Reaggregate after grouping others
            final_grouped = grouped.groupby(['year_month', 'urheber_display'])['count'].sum().reset_index()
            
            # Convert period to string for plotting
            final_grouped['month_str'] = final_grouped['year_month'].astype(str)
            
            # Performance: Create pivot table more efficiently
            pivot_df = final_grouped.pivot(index='month_str', columns='urheber_display', values='count').fillna(0)
            
            if pivot_df.empty:
                st.info("Insufficient data for timeseries visualization")
                return
            
            # Performance optimization: Limit time series complexity - reduced further
            if len(pivot_df) > 48:  # More than 4 years of monthly data
                st.info(f"📊 Large time range detected ({len(pivot_df)} months). Showing recent data for optimal performance.")
                pivot_df = pivot_df.tail(48)  # Show last 4 years
            
            # Optimized Plotly config
            config = BrowserOptimizations.optimize_plotly_config()
            config.update({
                'displayModeBar': False,
                'staticPlot': False,
                'scrollZoom': False,
                'doubleClick': False
            })
            
            # Create stacked bar chart with performance optimizations
            px = lazy_import_plotly()
            fig = px.bar(
                pivot_df.reset_index(),
                x='month_str',
                y=pivot_df.columns.tolist(),
                title=f"Urheber Distribution Over Time ({len(data_rows):,} document entries" + 
                      (f" from {original_count:,} total" if original_count != len(documents) else "") + ")",
                labels={'month_str': 'Month', 'value': 'Number of Documents', 'variable': 'Urheber'},
                height=450  # Reduced height for better performance
            )
            
            # Update layout for better readability and performance
            fig.update_layout(
                xaxis_title="Month",
                yaxis_title="Number of Documents",
                legend_title="Urheber",
                barmode='stack',
                xaxis={'tickangle': 45},
                margin=dict(t=50, b=100, l=50, r=50),
                # Performance optimizations
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,  # Move legend below chart
                    xanchor="center",
                    x=0.5
                )
            )
            
            # Performance: Optimize trace rendering
            fig.update_traces(
                hovertemplate='%{x}<br>%{fullData.name}: %{y}<br>Total: %{y}<extra></extra>',
                marker_line_width=0.5
            )
            
            # Show only every nth x-axis label to avoid clutter and improve performance
            if len(pivot_df) > 15:  # Reduced threshold
                fig.update_layout(
                    xaxis={'tickmode': 'linear', 'dtick': max(1, len(pivot_df) // 8)}  # Reduced to ~8 labels max
                )
            
            st.plotly_chart(fig, use_container_width=True, config=config)
        
        # Show summary statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Documents with Date & Urheber", f"{len(data_rows):,}")
        
        with col2:
            months_span = pivot_df.index.nunique()
            st.metric("Months Covered", months_span)
        
        with col3:
            urheber_count = final_grouped['urheber_display'].nunique()
            st.metric("Urheber Categories", urheber_count)
    
    def _sample_documents_for_visualization(self, documents: List[Dict[str, Any]], max_size: int) -> List[Dict[str, Any]]:
        """Intelligently sample documents for visualization while maintaining distribution"""
        if len(documents) <= max_size:
            return documents
        
        # Use stratified sampling based on date to maintain temporal distribution
        try:
            # Create DataFrame for sampling
            pd = lazy_import_pandas()
            df = pd.DataFrame(documents)
            
            # Convert dates and extract year-month for stratification
            df['datum_parsed'] = pd.to_datetime(df['datum'], errors='coerce')
            df = df.dropna(subset=['datum_parsed'])
            
            if df.empty:
                # Fallback to random sampling if no valid dates
                random = lazy_import_random()
                return random.sample(documents, max_size)
            
            # Group by year-month for stratified sampling
            df['year_month'] = df['datum_parsed'].dt.to_period('M')
            
            # Calculate sample size per stratum
            strata_counts = df['year_month'].value_counts()
            total_ratio = max_size / len(df)
            
            sampled_indices = []
            for stratum, count in strata_counts.items():
                stratum_df = df[df['year_month'] == stratum]
                sample_size = max(1, int(count * total_ratio))
                sample_size = min(sample_size, len(stratum_df))
                
                if sample_size > 0:
                    sampled_indices.extend(
                        stratum_df.sample(n=sample_size, random_state=42).index.tolist()
                    )
            
            # Return sampled documents
            return [documents[i] for i in sampled_indices[:max_size]]
            
        except Exception as e:
            # Fallback to random sampling if stratified sampling fails
            st.warning(f"Stratified sampling failed, using random sampling: {str(e)}")
            random = lazy_import_random()
            return random.sample(documents, max_size)
    
    def _sample_data_points(self, data_rows: List[Dict], max_points: int) -> List[Dict]:
        """Sample data points while maintaining temporal distribution"""
        if len(data_rows) <= max_points:
            return data_rows
        
        try:
            # Convert to DataFrame for easier sampling
            pd = lazy_import_pandas()
            df = pd.DataFrame(data_rows)
            df['year_month'] = df['date'].dt.to_period('M')
            
            # Stratified sampling by month
            strata_counts = df['year_month'].value_counts()
            total_ratio = max_points / len(df)
            
            sampled_data = []
            for stratum, count in strata_counts.items():
                stratum_df = df[df['year_month'] == stratum]
                sample_size = max(1, int(count * total_ratio))
                sample_size = min(sample_size, len(stratum_df))
                
                if sample_size > 0:
                    sampled_data.extend(
                        stratum_df.sample(n=sample_size, random_state=42).to_dict('records')
                    )
            
            return sampled_data[:max_points]
            
        except Exception:
            # Fallback to simple random sampling
            random = lazy_import_random()
            return random.sample(data_rows, max_points)
    
    def plot_vorgang_analytics(self, documents: List[Dict[str, Any]]):
        """Create analytics plots for Vorgänge"""
        st.markdown("### ⚖️ Vorgänge Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            types = [doc.get('vorgangstyp', 'Unknown') for doc in documents]
            pd = lazy_import_pandas()
            type_counts = pd.Series(types).value_counts()
            
            px = lazy_import_plotly()
            fig = px.bar(
                x=type_counts.values,
                y=type_counts.index,
                orientation='h',
                title=f"Procedure Types ({len(documents):,} procedures)"
            )
            fig.update_xaxes(title="Number of Procedures")
            fig.update_yaxes(title="Procedure Type")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            statuses = [doc.get('beratungsstand', 'Unknown') for doc in documents]
            pd = lazy_import_pandas()
            status_counts = pd.Series(statuses).value_counts()
            
            px = lazy_import_plotly()
            fig = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title=f"Status Distribution ({len(documents):,} procedures)"
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
    
    def run(self):
        """⚡ Main application runner with optimized startup"""
        # Fast startup indicator
        if 'app_fully_loaded' not in st.session_state:
            with st.spinner("⚡ Starting application (optimized for speed)..."):
                lazy_import_time().sleep(0.1)  # Minimal delay to show message
            st.session_state.app_fully_loaded = True
        
        # Check if we should display documentation pages
        page = st.query_params.get("page", None)
        
        if page == "architecture":
            self.display_architecture_page()
            return
        elif page == "api_docs":
            self.display_api_docs_page()
            return
        
        # Always render the modals first (this is crucial!)
        self.summary_display.render_summary_modal()
        
        # Render documentation modals from search manager
        self.search_manager.render_documentation_modals()
        
        self.display_header()
        
        # Main search and results handling
        self.handle_search_and_results()
        
        # Display additional tabs if available
        if st.session_state.search_results:
            self.display_result_tabs()
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #666;'>
            <small>
                Bundestag.AI Lens with AI Summaries | 
                <a href='https://dip.bundestag.de' target='_blank'>Official DIP Portal</a> | 
                Built with Streamlit & OpenAI
            </small>
        </div>
        """, unsafe_allow_html=True)
    
    def display_architecture_page(self):
        """Display the architecture documentation page"""
        # Add CSS to fix header and scroll bar issues
        st.markdown("""
        <style>
            /* Fix scroll bar and header issues for documentation pages */
            .main .block-container {
                padding-top: 1rem !important;
                max-height: none !important;
                overflow: visible !important;
            }
            
            /* Ensure proper scrolling for content */
            .stApp {
                overflow-y: scroll !important;
                height: 100vh !important;
                overflow-x: hidden !important;
            }
            
            /* Fix header positioning and prevent it from interfering */
            .main-header {
                position: relative !important;
                z-index: 1 !important;
                margin-bottom: 1rem !important;
            }
            
            /* Ensure content area is properly scrollable */
            .element-container {
                overflow: visible !important;
                position: relative !important;
            }
            
            /* CRITICAL: Fix Streamlit header interference */
            div[data-testid="stHeader"] {
                position: relative !important;
                height: auto !important;
                z-index: 0 !important;
                overflow: visible !important;
            }
            
            /* Prevent header hover effects from affecting scroll */
            header[data-testid="stHeader"] {
                position: relative !important;
                height: auto !important;
                overflow: visible !important;
                z-index: 0 !important;
            }
            
            /* Force scroll bar to always be visible */
            html, body {
                overflow-y: scroll !important;
                height: 100% !important;
            }
            
            /* Prevent any elements from hiding scroll bar */
            * {
                scrollbar-width: auto !important;
            }
            
            /* Fix for webkit browsers */
            ::-webkit-scrollbar {
                width: 16px !important;
                background: #f1f1f1 !important;
            }
            
            ::-webkit-scrollbar-thumb {
                background: #c1c1c1 !important;
                border-radius: 10px !important;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: #a8a8a8 !important;
            }
            
            /* Ensure main content doesn't interfere with scroll */
            .main {
                overflow: visible !important;
                height: auto !important;
            }
            
            /* Fix any iframe or embedded content */
            iframe {
                overflow: visible !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<h1 class="main-header">🏗️ Architecture & Data Flow Documentation</h1>', unsafe_allow_html=True)
        
        # Back to main app button
        if st.button("← Back to Main App", key="back_to_main_arch"):
            st.query_params.clear()
            st.rerun()
        
        st.markdown("---")
        
        try:
            from pathlib import Path
            docs_path = Path(__file__).parent.parent.parent / "docs" / "ARCHITECTURE_AND_DATAFLOW.md"
            
            if docs_path.exists():
                with open(docs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                st.markdown(content)
            else:
                st.error("Architecture documentation file not found")
                st.info("Expected location: `docs/ARCHITECTURE_AND_DATAFLOW.md`")
                
        except Exception as e:
            st.error(f"Error loading architecture documentation: {str(e)}")
    
    def display_api_docs_page(self):
        """Display the API documentation page"""
        # Add CSS to fix header and scroll bar issues
        st.markdown("""
        <style>
            /* Fix scroll bar and header issues for documentation pages */
            .main .block-container {
                padding-top: 1rem !important;
                max-height: none !important;
                overflow: visible !important;
            }
            
            /* Ensure proper scrolling for content */
            .stApp {
                overflow-y: scroll !important;
                height: 100vh !important;
                overflow-x: hidden !important;
            }
            
            /* Fix header positioning and prevent it from interfering */
            .main-header {
                position: relative !important;
                z-index: 1 !important;
                margin-bottom: 1rem !important;
            }
            
            /* Ensure content area is properly scrollable */
            .element-container {
                overflow: visible !important;
                position: relative !important;
            }
            
            /* CRITICAL: Fix Streamlit header interference */
            div[data-testid="stHeader"] {
                position: relative !important;
                height: auto !important;
                z-index: 0 !important;
                overflow: visible !important;
            }
            
            /* Prevent header hover effects from affecting scroll */
            header[data-testid="stHeader"] {
                position: relative !important;
                height: auto !important;
                overflow: visible !important;
                z-index: 0 !important;
            }
            
            /* Force scroll bar to always be visible */
            html, body {
                overflow-y: scroll !important;
                height: 100% !important;
            }
            
            /* Prevent any elements from hiding scroll bar */
            * {
                scrollbar-width: auto !important;
            }
            
            /* Fix for webkit browsers */
            ::-webkit-scrollbar {
                width: 16px !important;
                background: #f1f1f1 !important;
            }
            
            ::-webkit-scrollbar-thumb {
                background: #c1c1c1 !important;
                border-radius: 10px !important;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: #a8a8a8 !important;
            }
            
            /* Ensure main content doesn't interfere with scroll */
            .main {
                overflow: visible !important;
                height: auto !important;
            }
            
            /* Fix any iframe or embedded content */
            iframe {
                overflow: visible !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<h1 class="main-header">📖 API Documentation</h1>', unsafe_allow_html=True)
        
        # Back to main app button
        if st.button("← Back to Main App", key="back_to_main_api"):
            st.query_params.clear()
            st.rerun()
        
        st.markdown("---")
        
        try:
            from pathlib import Path
            docs_path = Path(__file__).parent.parent.parent / "docs" / "README.md"
            
            # Default API documentation content
            content = """
# API Documentation

## Bundestag DIP API Integration

This application integrates with the German Bundestag DIP (Dokumentations- und Informationssystem für Parlamentsmaterialien) API to provide access to parliamentary documents.

### Supported Document Types

1. **Drucksachen** (Parliamentary Documents)
   - Bills, motions, reports, and other official documents
   - Full text search available
   - Metadata includes date, electoral period, authors

2. **Vorgänge** (Procedures)
   - Legislative procedures and processes
   - Links to related documents
   - Status and progress information

3. **Plenarprotokolle** (Plenary Protocols)
   - Minutes of parliamentary sessions
   - Speaker information and timestamps
   - Full text of debates

4. **Personen** (People)
   - Members of parliament information
   - Role and committee memberships
   - Contact information

5. **Aktivitäten** (Activities)
   - Parliamentary activities and events
   - Committee meetings and hearings
   - Public events

### Search Features

- **Text Search**: Search in titles and content
- **Date Filtering**: Filter by date ranges
- **Electoral Period**: Filter by specific Wahlperioden
- **Author Filtering**: Find documents by specific authors
- **Document Type**: Filter by document categories

### AI Features

- **Smart Summaries**: OpenAI-powered document summarization
- **Citizen Impact Analysis**: Analysis of how documents affect citizens
- **Real-time Streaming**: Live updates during AI processing
- **Multi-document Processing**: Batch processing capabilities

### Performance Optimizations

- **Caching**: Intelligent caching of API responses
- **Pagination**: Efficient handling of large result sets
- **Streaming**: Real-time content delivery
- **Virtualization**: Optimized table rendering for large datasets

### Security Features

- **Input Validation**: All user inputs are validated
- **XSS Prevention**: Safe rendering of markdown content
- **Rate Limiting**: API usage optimization
- **Environment Security**: Secure configuration management

### Usage Examples

#### Basic Search
```python
# Search for documents about climate protection
filters = {"f.titel": ["Klimaschutz"]}
results = api_client.get_drucksachen(**filters)
```

#### Advanced Filtering
```python
# Search for government bills from the 21st electoral period
filters = {
    "f.drucksachetyp": "Gesetzentwurf",
    "f.urheber": ["Bundesregierung"],
    "f.wahlperiode": [21]
}
results = api_client.get_drucksachen(**filters)
```

#### AI-Powered Analysis
Use the web interface to:
1. Search for documents using various filters
2. Select documents of interest
3. Generate AI summaries with citizen impact analysis
4. Export results for further analysis
"""
            
            # Try to read from file if it exists
            if docs_path.exists():
                try:
                    with open(docs_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    content = file_content
                except:
                    pass  # Use default content if file reading fails
            
            st.markdown(content)
            
        except Exception as e:
            st.error(f"Error loading API documentation: {str(e)}")
    
    def display_result_tabs(self):
        """Display result tabs for AI summaries and analytics"""
        # These tabs are now integrated into the document selection area in search_manager
        # This method is kept for backward compatibility and future extensions
        pass


def main():
    """Main function to run the Streamlit app"""
    app = BundestagStreamlitApp()
    app.run()


if __name__ == "__main__":
    main()
