"""
UI Components for Bundestag.AI Lens
Handles the display of summaries, exports, and other UI elements.
Refactored to focus only on streaming summaries and citizen impact analysis.
"""

import streamlit as st
import pandas as pd
import json
import html
from datetime import datetime
from typing import Dict, List, Any, Optional
import plotly.express as px

from src.utils.helpers import format_date


class SummaryDisplayManager:
    """Manages the display of AI summaries and related UI components"""
    
    def __init__(self):
        # Initialize modal state
        if 'show_summary_modal' not in st.session_state:
            st.session_state.show_summary_modal = False
        if 'modal_summary_data' not in st.session_state:
            st.session_state.modal_summary_data = None
        # Initialize citizen impact analysis state
        if 'citizen_impact_analysis' not in st.session_state:
            st.session_state.citizen_impact_analysis = {}
        if 'generating_citizen_impact' not in st.session_state:
            st.session_state.generating_citizen_impact = False
    
    def _sanitize_html_content(self, content: str) -> str:
        """Sanitize content for safe HTML display"""
        if not content:
            return ""
        # Escape HTML special characters to prevent XSS
        return html.escape(content)
    
    def render_markdown_content(self, content: str, content_type: str = "Content", expanded: bool = False) -> None:
        """Render content with proper markdown formatting in an eye-friendly manner"""
        if not content:
            st.info(f"No {content_type.lower()} available.")
            return
        
        # Generate content summary for better space management
        content_summary = self._generate_chunk_summary(content, max_length=200)
        
        # Use expander for better content organization with summary
        expander_label = f"📝 **{content_type}** - {content_summary}" if len(content) > 200 else f"📝 **{content_type}**"
        
        with st.expander(expander_label, expanded=expanded):
            # Check if content appears to be markdown formatted
            if self._is_markdown_content(content):
                # Render as markdown with HTML support for links
                st.markdown(content, unsafe_allow_html=True)
            else:
                # For longer content, show preview first then expandable full content
                if len(content) > 500:
                    # Show preview
                    preview = content[:300] + "..." if len(content) > 300 else content
                    st.markdown(f"**Preview:**")
                    st.markdown(f"```\n{preview}\n```")
                    
                    # Full content in nested expander
                    with st.expander("📖 View Full Content", expanded=False):
                        st.text_area(
                            f"{content_type} Content",
                            value=content,
                            height=400,
                            key=f"content_{content_type.lower().replace(' ', '_')}_{hash(content) % 10000}",
                            help=f"Complete {content_type.lower()} content",
                            disabled=True
                        )
                else:
                    # For shorter content, display directly
                    st.text_area(
                        f"{content_type} Content",
                        value=content,
                        height=min(300, len(content.split('\n')) * 20 + 50),
                        key=f"content_{content_type.lower().replace(' ', '_')}_{hash(content) % 10000}",
                        help=f"Generated {content_type.lower()} content",
                        disabled=True
                    )
    
    def _is_markdown_content(self, content: str) -> bool:
        """Check if content appears to be markdown formatted"""
        if not content:
            return False
        
        # Look for common markdown patterns
        markdown_indicators = [
            '# ',       # Headers
            '## ',      # Subheaders
            '### ',     # Sub-subheaders
            '**',       # Bold
            '*',        # Italic (but not too common to avoid false positives)
            '- ',       # Lists
            '1. ',      # Numbered lists
            '`',        # Code
            '```',      # Code blocks
            '[',        # Links
            '|',        # Tables
        ]
        
        # Count markdown indicators
        indicator_count = sum(1 for indicator in markdown_indicators if indicator in content)
        
        # If we find multiple indicators, it's likely markdown
        return indicator_count >= 2
    
    def _display_author_info(self, document: Dict[str, Any]):
        """Display author information in a consistent format"""
        if not document:
            return
        
        # Extract author information from different possible fields
        authors = []
        
        # Try urheber field first
        urheber = document.get('urheber', [])
        if urheber and isinstance(urheber, list):
            for urh in urheber:
                if isinstance(urh, dict):
                    bezeichnung = urh.get('bezeichnung', '')
                    if bezeichnung:
                        authors.append(bezeichnung)
        
        # Try autoren_anzeige field
        if not authors:
            autoren_anzeige = document.get('autoren_anzeige', [])
            if autoren_anzeige and isinstance(autoren_anzeige, list):
                for author in autoren_anzeige:
                    if isinstance(author, dict):
                        autor_titel = author.get('autor_titel', '')
                        if autor_titel:
                            authors.append(autor_titel)
        
        # Display author information if found
        if authors:
            authors_text = ", ".join(authors[:3])  # Limit to first 3 authors
            if len(authors) > 3:
                authors_text += f" (+{len(authors) - 3} more)"
            
            st.markdown(f"""
            <div style="
                background: #e3f2fd;
                border-left: 3px solid #1976d2;
                padding: 8px 12px;
                border-radius: 3px;
                margin: 8px 0;
                font-size: 13px;
                color: #1565c0;
            ">
                📝 <strong>Author(s):</strong> {authors_text}
            </div>
            """, unsafe_allow_html=True)
    
    def create_streaming_display_placeholders(self, num_documents: int, doc_type: str) -> Dict[str, Any]:
        """Create placeholders for streaming display of multiple document summaries"""
        
        # Custom styled header for streaming mode
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 12px;
            margin: 20px 0;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        ">
            <div style="
                color: white;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 8px;
            ">
                🤖 Processing Documents
            </div>
            <div style="
                color: rgba(255,255,255,0.9);
                font-size: 16px;
            ">
                Analyzing {num_documents} {doc_type} documents
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Overall progress
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create separate expandable sections for each document
        doc_placeholders = []
        
        for i in range(num_documents):
            # Separate expandable section for document processing (chunks)
            with st.expander(f"📄 Document {i+1} - Processing...", expanded=False):
                # Dedicated chunking progress section
                st.markdown("### 📊 Document Processing")
                chunking_status = st.empty()
                chunks_container = st.container()
            
            # Separate expandable section for AI Summary & Citizen Impact
            with st.expander(f"🤖 Document {i+1} - AI Analysis", expanded=True):
                # Static AI Summary section  
                st.markdown("### 🧠 AI Summary")
                summary_placeholder = st.empty()
                # Show initial loading state for AI Summary
                summary_placeholder.info("🔄 Generating AI Summary...")
                
                # Static Citizen impact section
                st.markdown("---")
                st.markdown("### 🏛️ Citizen Impact Analysis")
                citizen_impact_placeholder = st.empty()
                # Show initial loading state for Citizen Impact
                citizen_impact_placeholder.info("🔄 Generating Citizen Impact Analysis...")
                
            doc_placeholders.append({
                'summary': summary_placeholder,
                'citizen_impact': citizen_impact_placeholder,
                'chunking_status': chunking_status,
                'chunks_container': chunks_container,
                'doc_index': i,
                'chunk_placeholders': []  # Will be populated during chunking
            })
        
        return {
            'progress_bar': progress_bar,
            'status_text': status_text,
            'doc_placeholders': doc_placeholders
        }
    
    def update_streaming_progress(self, placeholders: Dict[str, Any], current: int, total: int, current_title: str = ""):
        """Update streaming progress display"""
        progress = current / total
        placeholders['progress_bar'].progress(progress)
        
        # Use custom styled progress message
        placeholders['status_text'].markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
            padding: 12px;
            border-radius: 6px;
            border-left: 3px solid #667eea;
            margin: 5px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        ">
            <div style="
                color: #2d3748;
                font-weight: 500;
                font-size: 14px;
            ">
                🔄 Processing {current}/{total}: {current_title[:60]}{"..." if len(current_title) > 60 else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def complete_streaming_display(self, placeholders: Dict[str, Any], successful: int, total: int):
        """Complete the streaming display"""
        placeholders['progress_bar'].progress(1.0)
        
        # Use eye-friendly neutral completion message (no bright green)
        placeholders['status_text'].markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #6c757d;
            margin: 10px 0;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            <div style="
                color: #495057;
                font-weight: bold;
                font-size: 16px;
            ">
                ✅ Completed {successful}/{total} summaries successfully
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def create_chunk_placeholders(self, doc_placeholder: Dict[str, Any], num_chunks: int) -> List[Any]:
        """Create organized placeholders for individual chunks with improved UX"""
        chunk_placeholders = []
        
        with doc_placeholder['chunks_container']:
            # Update the chunking status
            doc_placeholder['chunking_status'].info(f"📝 Processing document in {num_chunks} chunks for optimal analysis")
            
            # Create a collapsible section for all chunks
            with st.expander(f"🔍 **View Chunk Analysis** ({num_chunks} parts)", expanded=False):
                # Create individual chunk placeholders within the main expander
                for i in range(num_chunks):
                    st.markdown(f"#### 🧩 Chunk {i+1}")
                    chunk_placeholder = st.empty()
                    chunk_placeholders.append(chunk_placeholder)
                    if i < num_chunks - 1:  # Add separator except for last chunk
                        st.markdown("---")
        
        # Store chunk placeholders in the document placeholder
        doc_placeholder['chunk_placeholders'] = chunk_placeholders
        return chunk_placeholders
    
    def _calculate_content_height(self, content: str, base_height: int = 100) -> int:
        """Calculate appropriate height for content based on text length"""
        if not content:
            return base_height
        
        # Estimate lines needed (assuming ~80 characters per line)
        lines = len(content) // 80 + content.count('\n') + 1
        # Add some padding and ensure minimum height
        return max(base_height, min(400, lines * 25 + 20))
    
    def _format_text_content(self, content: str) -> str:
        """Format text content for HTML display with proper escaping and line breaks"""
        if not content:
            return ""
        
        # Escape HTML to prevent XSS and keep it simple for performance
        escaped_content = html.escape(content)
        
        # Only convert double newlines to paragraphs for better performance
        # Single newlines become spaces to avoid excessive BR tags
        paragraphs = escaped_content.split('\n\n')
        formatted_paragraphs = []
        
        for paragraph in paragraphs:
            # Replace single newlines with spaces within paragraphs
            cleaned_paragraph = paragraph.replace('\n', ' ').strip()
            if cleaned_paragraph:
                formatted_paragraphs.append(cleaned_paragraph)
        
        # Join paragraphs with double line breaks
        return '<br><br>'.join(formatted_paragraphs)
    
    def _generate_chunk_summary(self, content: str, max_length: int = 150) -> str:
        """Generate a brief summary of chunk content for display"""
        if not content:
            return "Empty chunk"
        
        # Clean the content for summary
        clean_content = content.replace('\n', ' ').strip()
        
        # Return truncated version with ellipsis if too long
        if len(clean_content) <= max_length:
            return clean_content
        else:
            return clean_content[:max_length] + "..."
    
    def update_chunk_placeholder(self, chunk_placeholder: Any, chunk_index: int, content: str, is_complete: bool = False):
        """Update chunk placeholder with clean, organized display"""
        if is_complete:
            # Create clean chunk summary display
            chunk_summary = self._generate_chunk_summary(content, max_length=200)
            
            with chunk_placeholder.container():
                # Show status and summary
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.success("✅ Complete")
                with col2:
                    st.markdown(f"**Summary:** {chunk_summary}")
                
                # Show full content in a clean expandable section
                with st.expander("📖 View Full Content", expanded=False):
                    # Check if content has markdown formatting
                    if self._is_markdown_content(content):
                        st.markdown(content, unsafe_allow_html=True)
                    else:
                        # Clean text display
                        st.text_area(
                            "Content",
                            value=content,
                            height=200,
                            disabled=True,
                            key=f"chunk_{chunk_index}_{hash(content) % 10000}"
                        )
        else:
            # Show processing status with progress indicator
            chunk_placeholder.info(f"⏳ Processing Chunk {chunk_index + 1}...")
    
    def update_final_summary_placeholder(self, doc_placeholder: Dict[str, Any], final_summary: str, document: Dict[str, Any] = None):
        """Update the main summary placeholder with AI summary in full text format"""
        with doc_placeholder['summary'].container():
            # Add author information if available
            if document:
                self._display_author_info(document)
            
            # Display the full summary directly with markdown formatting
            st.markdown(final_summary, unsafe_allow_html=True)
    
    def update_citizen_impact_placeholder(self, doc_placeholder: Dict[str, Any], citizen_impact: str, document: Dict[str, Any] = None, is_complete: bool = False):
        """Update the citizen impact placeholder with analysis in full text format"""
        if is_complete and citizen_impact:
            with doc_placeholder['citizen_impact'].container():
                # Add author information if available
                if document:
                    self._display_author_info(document)
                
                # Display the full citizen impact analysis directly with markdown formatting
                st.markdown(citizen_impact, unsafe_allow_html=True)
        else:
            # Show a simple loading message without complex styling during processing
            doc_placeholder['citizen_impact'].info("🔄 Generating Citizen Impact Analysis...")
    
    def show_summary_modal(self, summary_data: Dict[str, Any]):
        """Show summary in a modal dialog"""
        st.session_state.show_summary_modal = True
        st.session_state.modal_summary_data = summary_data
    
    def hide_summary_modal(self):
        """Hide the summary modal"""
        st.session_state.show_summary_modal = False
        st.session_state.modal_summary_data = None
    
    def render_summary_modal(self):
        """Render the summary modal if it should be shown"""
        if st.session_state.show_summary_modal and st.session_state.modal_summary_data:
            self._render_modal_overlay()
    
    def _render_modal_overlay(self):
        """Render the modal overlay with summary content"""
        summary_data = st.session_state.modal_summary_data
        document = summary_data.get('document', {})
        summary = summary_data.get('summary', '')
        full_text = summary_data.get('full_text', '')
        
        # Simple modal using native Streamlit components
        st.markdown("---")
        
        # Modal header with close button
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown("## 🤖 AI Generated Summary")
            st.caption(f"**Document:** {document.get('titel', 'Unknown Title')}")
        
        with col2:
            if st.button("✕ Close", key="close_modal_btn", help="Close modal", type="secondary"):
                self.hide_summary_modal()
                st.rerun()
        
        st.markdown("---")
        
        # Create tabs for different content
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Summary", "🏛️ Citizen Impact", "📖 Full Text", "📊 Details"])
        
        with tab1:
            st.markdown("### 🎯 AI Generated Summary")
            
            # Display the summary with proper markdown rendering
            self.render_markdown_content(summary, "Summary")
            
            st.markdown("---")
                
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                st.download_button(
                    label="📄 Download Summary",
                    data=summary,
                    file_name=f"summary_{document.get('id', 'unknown')}.txt",
                    mime="text/plain",
                    key="modal_download_summary",
                    use_container_width=True
                )
            
            with col2:
                # Get citizen impact for combined download
                doc_id = document.get('id', 'unknown')
                citizen_impact_data = st.session_state.citizen_impact_analysis.get(doc_id, {})
                citizen_impact = citizen_impact_data.get('analysis', '')
                
                combined_data = {
                    'document_info': document,
                    'ai_summary': summary,
                    'citizen_impact_analysis': citizen_impact,
                    'full_text': full_text,
                    'generated_at': summary_data.get('timestamp', '')
                }
                st.download_button(
                    label="📦 Download All",
                    data=json.dumps(combined_data, indent=2, ensure_ascii=False),
                    file_name=f"complete_data_{document.get('id', 'unknown')}.json",
                    mime="application/json",
                    key="modal_download_complete",
                    use_container_width=True
                )
            
            with col3:
                if st.button("🔄 Regenerate", key="modal_regenerate", use_container_width=True):
                    st.info("Regeneration functionality would be implemented here")
        
        with tab2:
            # Citizen Impact Analysis Tab
            doc_id = document.get('id', 'unknown')
            citizen_impact = st.session_state.citizen_impact_analysis.get(doc_id)
            
            if citizen_impact and citizen_impact.get('analysis'):
                st.markdown("### 🏛️ Citizen Impact Analysis")
                st.caption("*Automatically generated from the AI summary*")
                
                # Display the citizen impact analysis with proper markdown rendering
                self.render_markdown_content(citizen_impact.get('analysis', ''), "Citizen Impact Analysis")
                
                st.markdown("---")
                    
                
                # Download options for citizen impact
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📄 Download Analysis",
                        data=citizen_impact.get('analysis', ''),
                        file_name=f"citizen_impact_{doc_id}.txt",
                        mime="text/plain",
                        key="modal_download_citizen_impact",
                        use_container_width=True
                    )
                
                with col2:
                    if st.button("🔄 Regenerate Analysis", key="modal_regenerate_citizen", use_container_width=True):
                        st.info("Citizen impact regeneration functionality would be implemented here")
            
            else:
                st.info("No citizen impact analysis available for this document.")
                if st.button("🏛️ Generate Citizen Impact Analysis", key="modal_generate_citizen", use_container_width=True):
                    st.info("Citizen impact generation functionality would be implemented here")
        
        with tab3:
            if full_text:
                st.markdown("### 📖 Full Document Text")
                with st.expander("View Full Text", expanded=False):
                    st.text_area(
                        "Document Content",
                        value=full_text,
                        height=400,
                        key="modal_full_text_area",
                        help="Complete document text"
                    )
            else:
                st.info("Full text not available for this document.")
        
        with tab4:
            st.markdown("### 📊 Document Details")
            st.json({
                'document_id': document.get('id', 'Unknown'),
                'title': document.get('titel', 'Unknown'),
                'summary_length': len(summary),
                'citizen_impact_length': len(citizen_impact.get('analysis', '') if citizen_impact else ''),
                'full_text_length': len(full_text),
                'generated_at': summary_data.get('timestamp', 'Unknown')
            })
    
    def check_citizen_impact_requests(self) -> List[str]:
        """Check for pending citizen impact analysis requests and return doc IDs"""
        requests = []
        for key in st.session_state.keys():
            if key.startswith('request_citizen_impact_'):
                doc_id = key.replace('request_citizen_impact_', '')
                if st.session_state[key]:
                    requests.append(doc_id)
                    # Reset the request flag
                    st.session_state[key] = False
        return requests
    
    def store_citizen_impact_analysis(self, doc_id: str, analysis: str):
        """Store citizen impact analysis in session state"""
        if 'citizen_impact_analysis' not in st.session_state:
            st.session_state.citizen_impact_analysis = {}
        
        st.session_state.citizen_impact_analysis[doc_id] = {
            'analysis': analysis,
            'timestamp': datetime.now().isoformat()
        }
    
    def display_saved_summaries_tab(self, document_summaries: Dict[str, Any]):
        """Display saved summaries in a tab"""
        st.subheader("💾 Saved Summaries")
        
        if not document_summaries:
            st.info("No summaries have been generated yet. Generate some summaries to see them here.")
            return
        
        # Display summary statistics
        self._display_summary_statistics(document_summaries)
        
        # Display each summary
        for doc_id, summary_data in document_summaries.items():
            with st.expander(f"📄 Document {doc_id}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("**Summary Preview:**")
                    summary_preview = summary_data.get('summary', '')[:200] + "..." if len(summary_data.get('summary', '')) > 200 else summary_data.get('summary', '')
                    st.write(summary_preview)
                    
                    if summary_data.get('citizen_impact'):
                        st.markdown("**Citizen Impact Available:** ✅")
                    else:
                        st.markdown("**Citizen Impact Available:** ❌")
                
                with col2:
                    if st.button("👁️ View Details", key=f"view_details_{doc_id}"):
                        # Create modal data
                        modal_data = {
                            'document': {'id': doc_id, 'titel': f'Document {doc_id}'},
                            'summary': summary_data.get('summary', ''),
                            'full_text': summary_data.get('full_text', ''),
                            'timestamp': summary_data.get('timestamp', '')
                        }
                        self.show_summary_modal(modal_data)
                        st.rerun()
    
    def _display_summary_statistics(self, document_summaries: Dict[str, Any]):
        """Display statistics about the saved summaries"""
        total_summaries = len(document_summaries)
        summaries_with_citizen_impact = sum(1 for s in document_summaries.values() if s.get('citizen_impact'))
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Summaries", total_summaries)
        
        with col2:
            st.metric("With Citizen Impact", summaries_with_citizen_impact)
        
        with col3:
            st.metric("Completion Rate", f"{(summaries_with_citizen_impact/total_summaries*100):.1f}%" if total_summaries > 0 else "0%")


class AnalyticsDisplayManager:
    """Manages analytics and visualization components"""
    
    def __init__(self):
        pass
    
    def display_summary_analytics(self, document_summaries: Dict[str, Any]):
        """Display analytics for summaries"""
        if not document_summaries:
            st.info("No summaries available for analytics.")
            return
        
        st.subheader("📊 Summary Analytics")
        
        # Summary length distribution
        summary_lengths = [len(data.get('summary', '')) for data in document_summaries.values()]
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Summary length statistics
            if summary_lengths:
                avg_length = sum(summary_lengths) / len(summary_lengths)
                st.metric("Average Summary Length", f"{avg_length:.0f} chars")
                
                # Create histogram
                fig = px.histogram(
                    x=summary_lengths,
                    title="Summary Length Distribution",
                    labels={'x': 'Summary Length (characters)', 'y': 'Count'}
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Citizen impact availability
            with_impact = sum(1 for data in document_summaries.values() if data.get('citizen_impact'))
            without_impact = len(document_summaries) - with_impact
            
            if with_impact > 0 or without_impact > 0:
                fig = px.pie(
                    values=[with_impact, without_impact],
                    names=['With Citizen Impact', 'Without Citizen Impact'],
                    title="Citizen Impact Analysis Coverage"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    def display_analytics(self, results: Dict[str, Any]):
        """Display analytics for search results"""
        if not results or 'documents' not in results:
            st.info("No data available for analytics.")
            return
        
        documents = results["documents"]
        doc_type = results["doc_type"]
        
        st.subheader("📊 Search Results Analytics")
        
        # Basic metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Documents", len(documents))
        
        with col2:
            # Calculate date range if dates are available
            dates = [doc.get('datum') for doc in documents if doc.get('datum')]
            if dates:
                date_range = f"{min(dates)} to {max(dates)}"
                st.metric("Date Range", "Available")
                st.caption(date_range)
            else:
                st.metric("Date Range", "N/A")
        
        with col3:
            # Document type specific metrics
            if doc_type == "drucksache":
                types = [doc.get('drucksachetyp') for doc in documents if doc.get('drucksachetyp')]
                unique_types = len(set(types)) if types else 0
                st.metric("Document Types", unique_types)
            elif doc_type == "vorgang":
                types = [doc.get('vorgangstyp') for doc in documents if doc.get('vorgangstyp')]
                unique_types = len(set(types)) if types else 0
                st.metric("Process Types", unique_types)
            else:
                st.metric("Categories", "N/A")
        
        with col4:
            # Average title length
            titles = [doc.get('titel', '') for doc in documents]
            avg_title_length = sum(len(title) for title in titles) / len(titles) if titles else 0
            st.metric("Avg Title Length", f"{avg_title_length:.0f} chars")
        
        # Visualizations based on document type
        if doc_type == "drucksache":
            self._plot_drucksache_analytics(documents)
        elif doc_type == "vorgang":
            self._plot_vorgang_analytics(documents)
    
    def _plot_drucksache_analytics(self, documents: List[Dict[str, Any]]):
        """Create analytics plots for Drucksachen"""
        col1, col2 = st.columns(2)
        
        with col1:
            # Document type distribution
            doc_types = [doc.get('drucksachetyp', 'Unknown') for doc in documents]
            type_counts = {}
            for doc_type in doc_types:
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
            
            if type_counts:
                fig = px.bar(
                    x=list(type_counts.keys()),
                    y=list(type_counts.values()),
                    title="Document Type Distribution",
                    labels={'x': 'Document Type', 'y': 'Count'}
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Timeline if dates are available
            dates = [doc.get('datum') for doc in documents if doc.get('datum')]
            if dates:
                date_counts = {}
                for date in dates:
                    date_counts[date] = date_counts.get(date, 0) + 1
                
                sorted_dates = sorted(date_counts.keys())
                counts = [date_counts[date] for date in sorted_dates]
                
                fig = px.line(
                    x=sorted_dates,
                    y=counts,
                    title="Documents Over Time",
                    labels={'x': 'Date', 'y': 'Count'}
                )
                st.plotly_chart(fig, use_container_width=True)
    
    def _plot_vorgang_analytics(self, documents: List[Dict[str, Any]]):
        """Create analytics plots for Vorgänge"""
        col1, col2 = st.columns(2)
        
        with col1:
            # Process type distribution
            process_types = [doc.get('vorgangstyp', 'Unknown') for doc in documents]
            type_counts = {}
            for process_type in process_types:
                type_counts[process_type] = type_counts.get(process_type, 0) + 1
            
            if type_counts:
                fig = px.pie(
                    values=list(type_counts.values()),
                    names=list(type_counts.keys()),
                    title="Process Type Distribution"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Status distribution if available
            statuses = [doc.get('aktueller_stand', 'Unknown') for doc in documents if doc.get('aktueller_stand')]
            if statuses:
                status_counts = {}
                for status in statuses:
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                fig = px.bar(
                    x=list(status_counts.keys()),
                    y=list(status_counts.values()),
                    title="Process Status Distribution",
                    labels={'x': 'Status', 'y': 'Count'}
                )
                st.plotly_chart(fig, use_container_width=True)
