#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
import re
from celery_config import celery_app
import logging

# Import Firestore uploader and extend it with needed functionality
try:
    import sys
    import os
    # Try multiple import paths to find the firestore_uploader module
    try:
        from portfolio_generator.firestore_uploader import FirestoreUploader
    except ImportError:
        # Try relative import
        module_dir = os.path.dirname(__file__)
        sys.path.append(module_dir)
        from firestore_uploader import FirestoreUploader
    FIRESTORE_AVAILABLE = True
    
    # Extend FirestoreUploader with get_document and update_document methods
    class EnhancedFirestoreUploader(FirestoreUploader):
        def get_document(self, collection_name, document_id):
            """Retrieve a document by ID from a specified collection"""
            try:
                collection_ref = self.db.collection(collection_name)
                doc_ref = collection_ref.document(document_id)
                doc = doc_ref.get()
                if doc.exists:
                    return doc.to_dict()
                else:
                    print(f"Document {document_id} not found in collection {collection_name}")
                    return None
            except Exception as e:
                print(f"Error retrieving document: {str(e)}")
                return None
        
        def update_document(self, collection_name, document_id, update_data):
            """Update fields in an existing document"""
            try:
                collection_ref = self.db.collection(collection_name)
                doc_ref = collection_ref.document(document_id)
                doc_ref.update(update_data)
                return True
            except Exception as e:
                print(f"Error updating document: {str(e)}")
                return False
    
    print("✅ Firestore uploader module loaded and extended successfully.")
except ImportError as e:
    FIRESTORE_AVAILABLE = False
    print(f"⚠️ Firestore uploader not available. Reports will not be improved.\\n{e}")

# Try to import PerplexitySearch or create a stub
try:
    from portfolio_generator.web_search import PerplexitySearch
    PERPLEXITY_AVAILABLE = True
    print("✅ PerplexitySearch module loaded successfully.")
except ImportError:
    class PerplexitySearch:
        def __init__(self, *args, **kwargs):
            print("Warning: Using stub PerplexitySearch. Web search functionality is not available.")
            
        async def search(self, queries):
            print(f"Stub search for: {queries}")
            # Return a LIST of results, one for each query, matching the expected structure
            return [
                {
                    "query": query, 
                    "results": [{"content": f"Stub result for {query}"}]
                } 
                for query in queries
            ]
    PERPLEXITY_AVAILABLE = False
    print("⚠️ PerplexitySearch not available. Using stub implementation.")

# Logging functions
def log_error(message):
    print(f"\033[91m[ERROR] {message}\033[0m")
    
def log_warning(message):
    print(f"\033[93m[WARNING] {message}\033[0m")
    
def log_success(message):
    print(f"\033[92m[SUCCESS] {message}\033[0m")
    
def log_info(message):
    print(f"\033[94m[INFO] {message}\033[0m")

def format_search_results(search_results):
    """Format search results for use in prompts."""
    if not search_results:
        return ""
    
    # Filter results to only include those with actual content
    valid_results = [r for r in search_results 
                     if r.get("results") and len(r["results"]) > 0 and "content" in r["results"][0]]
    
    if not valid_results:
        log_warning("No valid search results to format - all results were empty or had errors")
        return ""
        
    formatted_text = "\n\nWeb Search Results (current as of 2025):\n"
    
    for i, result in enumerate(valid_results):
        query = result.get("query", "Unknown query")
        content = result["results"][0].get("content", "No content available")
        
        formatted_text += f"\n---Result {i+1}: {query}---\n{content}\n"
    
    log_info(f"Formatted {len(valid_results)} valid search results for use in prompts")
    return formatted_text

from portfolio_generator.gcs_video_context_generator import generate_context_from_latest_video

async def _run_improvement_logic(document_id: str, report_date: str = None, annotations: list = None, timestamp: str = None, video_url: str = None, weight_changes: list = None, position_count: int = None, manual_upload: dict = None, chat_history: list = None):
    # Step 0a: Generate video context from GCS or use provided video URL
    try:
        # Store the video URL in the context even if we don't process it yet
        video_url_context = f"Video URL: {video_url}\n" if video_url else ""
        
        # Generate context from the latest video in GCS
        video_context = generate_context_from_latest_video(document_id)
        
        if video_context:
            log_info(f"Video context successfully generated for document_id {document_id}. Context length: {len(video_context)} characters.")
        else:
            log_info(f"No video context generated for document_id {document_id}.")
            
        # Add the video URL to the context if it was provided
        if video_url:
            log_info(f"Adding video URL to context: {video_url}")
            video_context = f"{video_url_context}\n{video_context}"
    except Exception as e:
        log_warning(f"Failed to generate video context for document_id {document_id}: {e}")
        # Still include the video URL even if context generation failed
        video_context = video_url_context if video_url else ""
    # --- Extract scratchpad feedback and upload to Firestore ---
    video_feedback_section = f"=====VideoFeedback=====\n{video_context}"
    portfolio_feedback_section = "=====PortfolioFeedback=====\n"
    
    # Add report date if available
    if report_date:
        portfolio_feedback_section += f"Report Date: {report_date}\n\n"
    if annotations:
        for i, anno in enumerate(annotations, 1):
            text = anno.get("original_text") or anno.get("text", "")
            comment = anno.get("comment", "")
            sentiment = anno.get("sentiment", "")
            portfolio_feedback_section += f"--- Feedback {i} ---\n"
            if text:
                portfolio_feedback_section += f"Text: {text}\n"
            if comment:
                portfolio_feedback_section += f"Comment: {comment}\n"
            if sentiment:
                portfolio_feedback_section += f"Sentiment: {sentiment}\n"
    if weight_changes:
        portfolio_feedback_section += "\n--- Weight Changes ---\n"
        for i, wc in enumerate(weight_changes, 1):
            asset = wc.get("assetName") or wc.get("asset_name", "")
            ticker = wc.get("ticker", "")
            old_w = wc.get("oldWeight") or wc.get("old_weight", "")
            new_w = wc.get("newWeight") or wc.get("new_weight", "")
            portfolio_feedback_section += f"{i}. {asset} ({ticker}): {old_w} -> {new_w}\n"
    # Add manual upload info if available
    if manual_upload:
        manual_upload_section = "=====ManualUpload=====\n"
        upload_type = manual_upload.get("type", "unknown")
        file_type = manual_upload.get("fileType", "unknown")
        manual_upload_section += f"Type: {upload_type}\nFile Type: {file_type}\n"
        portfolio_feedback_section += f"\n{manual_upload_section}\n"
    
    # Add chat history if available
    if chat_history and len(chat_history) > 0:
        chat_history_section = "=====ChatHistory=====\n"
        for msg in chat_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            msg_timestamp = msg.get("timestamp", "")
            chat_history_section += f"[{role} - {msg_timestamp}]\n{content}\n\n"
        portfolio_feedback_section += f"\n{chat_history_section}\n"
    
    scratchpad_text = f"{video_feedback_section}\n\n{portfolio_feedback_section}"
    try:
        uploader = EnhancedFirestoreUploader()
        col = uploader.db.collection("alternative-portfolio-scratchpad")
        # Mark previous scratchpad docs as not latest
        for doc in col.where("is_latest", "==", True).stream():
            col.document(doc.id).update({"is_latest": False})
        
        # Upload the new scratchpad
        col.document(document_id).set({
            "scratchpad": scratchpad_text,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "is_latest": True
        })
        log_success(f"Uploaded scratchpad feedback for document {document_id} to 'alternative-portfolio-scratchpad'.")
    except Exception as e:
        log_error(f"Failed to upload scratchpad to Firestore: {e}")
        raise RuntimeError(f"Failed to upload scratchpad: {e}")
    return {
        "message": "Scratchpad feedback uploaded successfully.",
        "document_id": document_id,
        "scratchpad_text": scratchpad_text
    }