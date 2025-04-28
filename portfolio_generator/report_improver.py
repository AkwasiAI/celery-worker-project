#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import time
from datetime import datetime
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

async def call_openai_to_improve(client, system_prompt, user_prompt, search_results=None, video_context=None, target_word_count=3000):
    """Make an API call to OpenAI to improve the report."""
    try:
        # Inject word count requirement into the user prompt
        word_count_instruction = f"\n\nPlease ensure the improved report is approximately {target_word_count} words (10,000 on Fridays, 3,000 otherwise). Be concise but thorough."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + word_count_instruction}
        ]
        
        # Add video context if provided
        if video_context and video_context.strip():
            messages.append({
                "role": "user",
                "content": (
                    "Here is extracted context from screen recording videos related to this report. "
                    "Use this information to inform and improve the report.\n\n" + video_context
                )
            })

        # Add web search results if available
        if search_results and search_results.strip():
            messages.append({"role": "user", "content": "Here is the latest information from web searches:\n\n" + search_results})
        
        log_info("Calling OpenAI API to improve report with high reasoning effort")
        response = client.chat.completions.create(
            model="o3-mini",  # You can adjust the model as needed
            messages=messages,
            reasoning_effort="high"
        )
        
        # Get the content
        improved_content = response.choices[0].message.content
        return improved_content
    
    except Exception as e:
        error_msg = f"Error calling OpenAI API to improve report: {e}"
        log_error(error_msg)
        raise RuntimeError(error_msg)

from portfolio_generator.gcs_video_context_generator import generate_context_from_gcs_folder

async def _run_improvement_logic(document_id: str, annotations: list, weight_changes: list, position_count: int = None):
    from datetime import datetime
    today = datetime.now().strftime('%A')
    target_word_count = 10000 if today == 'Friday' else 3000
    """
    Asynchronous function containing the core logic for the improvement task.
    Args:
        document_id: The Firestore document ID of the report to improve
        annotations: List of annotation objects containing text snippets, comments, and sentiment
        weight_changes: List of weight change objects with asset name, ticker, old weight, and new weight
        position_count: The required number of portfolio positions to enforce in the improved report (optional)
    Returns:
        Dict containing success message, document ID, and runtime information
    """
    log_info(f"Starting improvement task for document ID: {document_id} ({len(annotations)} annotations, {len(weight_changes)} weight changes).")
    start_time = time.time()

    # --- Step 0a: Generate video context from GCS ---
    try:
        video_context = generate_context_from_gcs_folder(document_id)
        if video_context:
            log_info(f"Video context successfully generated for document_id {document_id}. Context length: {len(video_context)} characters.")
        else:
            log_info(f"No video context generated for document_id {document_id}.")
    except Exception as e:
        log_warning(f"Failed to generate video context for document_id {document_id}: {e}")
        video_context = ""

    # --- Configuration Checks ---
    if not FIRESTORE_AVAILABLE:
        raise RuntimeError("Firestore is not configured in the worker.")
    
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OpenAI API key is missing.")

    # Initialize clients
    firestore_uploader = EnhancedFirestoreUploader()
    openai_client = OpenAI(api_key=openai_api_key)
    
    # Initialize PerplexitySearch if available
    search_client = None
    perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
    if PERPLEXITY_AVAILABLE and perplexity_api_key:
        try:
            search_client = PerplexitySearch(api_key=perplexity_api_key)
            log_info("PerplexitySearch client initialized.")
        except Exception as e:
            log_warning(f"Failed to initialize PerplexitySearch client: {e}. Proceeding without web search.")

    # --- Step 0: Upload Feedback Request to Firestore ---
    feedback_collection = "portfolios"  # The FirestoreUploader uses this collection by default
    # Ensure each annotation includes 'original_text' for traceability
    processed_annotations = []
    for anno in annotations:
        processed = dict(anno)
        # If 'original_text' is missing but 'text' is present, copy it
        if 'original_text' not in processed and 'text' in processed:
            processed['original_text'] = processed['text']
        processed_annotations.append(processed)

    feedback_data = {
        'document_id': document_id,
        'annotations': processed_annotations,
        'weight_changes': weight_changes,
        'timestamp': datetime.utcnow().isoformat()
    }
    try:
        import tempfile
        import json
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as tmp_feedback:
            json.dump(feedback_data, tmp_feedback)
            tmp_feedback_path = tmp_feedback.name
        # Upload feedback as 'report_feedback'
        firestore_uploader.upload_file(tmp_feedback_path, doc_type='report_feedback', file_format='json', is_latest=True)
        log_success(f"Uploaded feedback request for document {document_id} to Firestore as 'report_feedback'.")
    except Exception as e:
        log_warning(f"Failed to upload feedback request to Firestore: {e}")

    # --- Step 1: Fetch Original Report from Firestore ---
    original_report_content = None
    report_collection = "portfolios"  # Replace with your actual collection name
    report_content_field = 'content'  # Field name containing the report content
    
    try:
        log_info(f"Fetching original report '{document_id}' from Firestore collection '{report_collection}'...")
        original_report_data = firestore_uploader.get_document(report_collection, document_id)
        
        if not original_report_data:
            raise ValueError(f"Report document {document_id} not found.")
        
        if report_content_field not in original_report_data:
             raise KeyError(f"Expected field '{report_content_field}' missing in document {document_id}.")
        
        original_report_content = original_report_data[report_content_field]
        log_success(f"Successfully fetched original report content (length: {len(original_report_content)} chars).")
    
    except Exception as e:
        log_error(f"Failed to fetch document '{document_id}' from Firestore: {e}")
        raise

    # --- Step 2: Perform Web Searches (Optional) ---
    formatted_search_results = ""
    position_count_instruction = ""
    if position_count is not None:
        position_count_instruction = f"\n\nCRITICAL REQUIREMENT: The improved report MUST contain exactly {position_count} portfolio positions in the summary table and all related sections. Do NOT add or remove positions beyond this count."

    if search_client:
        try:
            current_month_year = datetime.now().strftime("%B %Y")
            feedback_themes_for_search = []  # Derived from annotations
            
            # Extract themes from annotations for targeted search queries
            if annotations:
                for anno in annotations:
                    # Use 'original_text' if present, else fallback to 'text'
                    text_snippet = anno.get('original_text') or anno.get('text') or ''
                    comment = anno.get('comment', '')
                    sentiment = anno.get('sentiment', '')
                    if text_snippet and comment:
                        # Include sentiment in combined text for keyword extraction and in the query
                        combined_text = f"{text_snippet} {comment} {sentiment}".strip()
                        keywords = [w for w in re.findall(r'\b[A-Za-z][A-Za-z0-9]{2,}\b', combined_text) 
                                   if w.lower() not in {'the', 'and', 'for', 'this', 'that', 'with', 'have', 'from'}]
                        if keywords:
                            # Add sentiment to the search query if present
                            sentiment_phrase = f" Sentiment: {sentiment}" if sentiment else ""
                            query = f"Latest financial market analysis {' '.join(keywords[:3])}{sentiment_phrase} {current_month_year}"
                            feedback_themes_for_search.append(query)

            # Add queries for assets with weight changes
            weight_change_tickers = [wc['ticker'] for wc in weight_changes if 'ticker' in wc]
            asset_queries = [f"Latest analysis for asset {ticker} {current_month_year}" for ticker in weight_change_tickers]

            # Base queries for general context
            base_queries = [
                f"Latest global economic outlook {current_month_year}",
                f"Current market trends in shipping and energy {current_month_year}",
                f"Financial market forecast next quarter {current_month_year}"
            ]
            
            # Combine queries and remove duplicates
            search_queries = list(set(base_queries + feedback_themes_for_search + asset_queries))
            
            log_info(f"Performing {len(search_queries)} web searches for updated context...")
            search_results = await search_client.search(search_queries[:7])  # Limit number of queries
            
            formatted_search_results = format_search_results(search_results)
            
            if not formatted_search_results:
                log_warning("No valid search results obtained. Report will be improved without current data.")
        except Exception as e:
            log_warning(f"Web search failed: {e}. Proceeding without search results.")

    # --- Step 3: Prepare Prompt and Call OpenAI for Improvement ---
    log_info("Preparing OpenAI prompt for report improvement based on annotations and weight changes...")

    # Format annotations for the prompt
    formatted_annotations = "No specific textual annotations provided."
    if annotations:
        formatted_annotations = "Specific User Feedback Annotations:\n"
        for i, anno in enumerate(annotations):
            formatted_annotations += f"\n--- Annotation {i+1} ---\n"
            # Use 'original_text' if present, else fallback to 'text'
            text_snippet = anno.get('original_text') or anno.get('text')
            if text_snippet:
                formatted_annotations += f"Text Snippet from Report: \"{text_snippet}\"\n"
            if 'comment' in anno:
                formatted_annotations += f"User Comment: \"{anno['comment']}\"\n"
            if 'sentiment' in anno:
                formatted_annotations += f"Sentiment: {anno['sentiment']}\n"
        formatted_annotations += "--- End of Annotations ---\n"

    # Format weight changes for the prompt
    formatted_weight_changes = "No specific portfolio weight changes requested."
    if weight_changes:
        formatted_weight_changes = "Requested Portfolio Weight Changes:\n"
        
        # Calculate total of new weights for informational purposes
        total_new_weight = sum(wc.get('newWeight', 0) for wc in weight_changes)
        formatted_weight_changes += f"(Note: Sum of requested new weights in this list is {total_new_weight}%)\n"
        
        for i, wc in enumerate(weight_changes):
            asset_name = wc.get('assetName', 'Unknown Asset')
            ticker = wc.get('ticker', 'N/A')
            old_weight = wc.get('oldWeight', 'N/A')
            new_weight = wc.get('newWeight', 'N/A')
            formatted_weight_changes += f"- Asset: {asset_name} ({ticker}) | Change Weight From: {old_weight}% To: {new_weight}%\n"
        
        formatted_weight_changes += "--- End of Weight Changes ---\n"

    # Define the system prompt
    system_prompt = """
You are an expert financial analyst and report generator. You must produce a JSON object representing the portfolio weights and rationale for each asset, following these strict standards:

**Portfolio Asset Table Requirements:**
- Each asset must include:
    - asset_name (string)
    - category (string)
    - region (string, must be present and accurate)
    - weight (float, can be negative for shorts)
    - horizon (string, must be one of: '6-12M', '3-6M', '12-18M', '12+')
    - recommendation (string, must be 'Long' or 'Short')
    - rationale (string, must be concise, data-driven, and not generic or filler text)
- Do NOT use other horizon terms such as 'short-term', 'long-term', '1m', '1Q', etc. ONLY use the allowable values above.
- Region must be specific and accurate (e.g. 'Global', 'United States', 'Emerging Markets').
- Rationale must be specific, reference consensus or Orasis view, and avoid generic or junk language.
- Recommendations must be 'Long' or 'Short', never other terms.
- The output JSON must match the following gold standard format:

```
{
    "status": "success",
    "data": {
        "report_date": "April 5, 2025",
        "assets": [
            {
                "asset_name": "Brent Crude Oil",
                "category": "Commodity",
                "region": "Global",
                "weight": 16.44,
                "horizon": "6-12M",
                "recommendation": "Long",
                "rationale": "Global oil demand rising to 103.9 Mb/d vs supply 104.5 Mb/d (2025)…"
            },
            ...
        ],
        "summary": {
            "by_category": {"Commodity": 41.1, ...},
            "by_region": {"Global": 65.8, ...},
            "by_recommendation": {"Long": 113.7, "Short": -13.7}
        }
    }
}
```

- If the model produces any value for 'horizon' outside the allowed set, replace it with the closest valid value.
- If rationale is generic or junk, rewrite it to be data-driven and specific.
- If region is missing or clearly wrong, infer the correct region from the asset or report context.

**ALWAYS follow this JSON structure exactly.**
"""

    # Construct the user prompt including original report, annotations, and weight changes
    user_prompt = f"""
Please generate the portfolio weights and rationale as a JSON object according to the above standards, based on the following inputs:

**Original Report Content:**
--- START ORIGINAL REPORT ---
{original_report_content}
--- END ORIGINAL REPORT ---

**User Feedback (Annotations):**
{formatted_annotations}

**Requested Portfolio Weight Changes:**
{formatted_weight_changes}

**Instructions:**
1.  Review all inputs and ensure the output strictly matches the provided JSON gold standard.
2.  Only use allowable values for horizon and recommendation. If you see 'short-term', 'long-term', or other variants, convert them to the closest valid value.
3.  The region must be present and accurate for each asset.
4.  The rationale must be specific, data-driven, and reference consensus or Orasis view.
5.  Output ONLY the JSON object, and nothing else.
{position_count_instruction}
"""

    # Call OpenAI to improve the report
    improved_report_content = await call_openai_to_improve(
        openai_client,
        system_prompt,
        user_prompt,
        formatted_search_results
    )

    # --- Step 4: Post-process and Save Improved Report to Firestore ---
    try:
        log_info(f"Saving improved report back to Firestore document '{document_id}'...")

        # --- Post-processing for horizon, region, rationale ---
        import json as _json
        try:
            improved_json = _json.loads(improved_report_content)
            allowed_horizons = {"6-12M", "3-6M", "12-18M", "12+"}
            for asset in improved_json.get("data", {}).get("assets", []):
                # Coerce horizon
                horizon = asset.get("horizon", "").strip()
                if horizon not in allowed_horizons:
                    # Try to map common variants to allowed values
                    horizon_map = {
                        "short-term": "3-6M",
                        "short": "3-6M",
                        "long-term": "12+",
                        "long": "12+",
                        "1m": "3-6M",
                        "1q": "3-6M",
                        "12M+": "12+",
                        "12M": "12+",
                        "12-18m": "12-18M",
                        "6m": "6-12M",
                        "3-6m": "3-6M",
                        "6-12m": "6-12M",
                        "12-18M": "12-18M",
                        "6-12M": "6-12M",
                        "3-6M": "3-6M",
                        "12+": "12+"
                    }
                    asset["horizon"] = horizon_map.get(horizon.lower(), "6-12M")
                # Region check
                if not asset.get("region") or asset["region"].lower() in {"", "unknown", "n/a"}:
                    # Try to infer from asset_name or set to 'Global'
                    asset["region"] = "Global"
                # Rationale check
                rationale = asset.get("rationale", "").strip()
                if not rationale or rationale.lower() in {"junk", "n/a", "none", "generic"}:
                    asset["rationale"] = "Rationale not provided. Please see consensus and Orasis view."
            # Compose improved markdown report with 'Summary of Changes' (annotations and weight changes)
            summary_lines = ["# Summary of Changes\n"]
            if annotations:
                summary_lines.append("## Annotations Applied:")
                for i, anno in enumerate(annotations, 1):
                    comment = anno.get('comment', '')
                    text = anno.get('text', '')
                    sentiment = anno.get('sentiment', '')
                    summary_lines.append(f"{i}. Comment: {comment}\n   Text: {text}\n   Sentiment: {sentiment}")
            if weight_changes:
                summary_lines.append("\n## Weight Changes Applied:")
                for i, wc in enumerate(weight_changes, 1):
                    asset = wc.get('assetName') or wc.get('asset_name', '')
                    old_weight = wc.get('oldWeight', wc.get('old_weight', ''))
                    new_weight = wc.get('newWeight', wc.get('new_weight', ''))
                    summary_lines.append(f"{i}. {asset}: {old_weight} -> {new_weight}")
            summary_section = "\n".join(summary_lines)
            improved_markdown_report = f"{summary_section}\n\n{original_report_content}"
            improved_report_content = improved_markdown_report
        except Exception as e:
            log_warning(f"Post-processing failed: {e}")

        # Prepare data to update in Firestore
        update_data = {
            report_content_field: improved_report_content,  # Update the main content field (markdown+json)
            'last_improved_timestamp': datetime.utcnow(),
            # Store full annotations and weight changes for history
            'last_feedback_annotations': annotations,
            'last_weight_changes_requested': weight_changes,
            'status': 'Improved'  # Update status field
        }
        
        success = firestore_uploader.update_document(report_collection, document_id, update_data)
        
        if success:
            log_success(f"Successfully updated document '{document_id}' in Firestore.")
        else:
            log_error(f"Failed to update document '{document_id}' in Firestore.")
            raise RuntimeError("Firestore update failed")

        # --- Save improved weights as a new file with status 'improved' and is_latest true ---
        try:
            from portfolio_generator.report_improver_add_weights import save_improved_weights
            # Use improved_json from above if available, else parse again
            assets_list = [asset for asset in improved_json.get("data", {}).get("assets", [])]
            improved_weights_path = await save_improved_weights(openai_client, assets_list, datetime.utcnow().strftime("%Y-%m-%d"))
            log_success(f"Saved improved portfolio weights to {improved_weights_path}")
        except Exception as e:
            log_warning(f"Failed to save improved weights file: {e}")
    except Exception as e:
        log_error(f"Failed to save improved report to Firestore: {e}")
        raise

    # Task Completion
    runtime = time.time() - start_time
    log_success(f"Improvement task for document {document_id} completed successfully in {runtime:.2f} seconds.")
    
    return {
        "message": "Report improved successfully based on annotations and weight changes.",
        "document_id": document_id,
        "runtime_seconds": round(runtime, 2)
    }

# Celery task implementation (moved to tasks.py)
# The implementation is in tasks.py but this function can be called directly for testing
async def improve_report(document_id: str, annotations: list, weight_changes: list):
    """
    Direct function to improve a report based on annotations and weight changes.
    This can be called directly for testing or used by the Celery task.
    """
    return await _run_improvement_logic(document_id, annotations, weight_changes)
