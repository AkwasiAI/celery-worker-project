"""Firestore upload functionality for portfolio reports."""
import os
import json
from datetime import datetime
import asyncio
import google.api_core.exceptions
from portfolio_generator.modules.logging import log_info, log_warning, log_error, log_success

# Check if Firestore is available
FIRESTORE_AVAILABLE = False
try:
    from google.cloud import firestore
    from portfolio_generator.firestore_uploader import FirestoreUploader
    FIRESTORE_AVAILABLE = True
except ImportError:
    firestore = None
    FirestoreUploader = None
    log_error("FirestoreUploader could not be imported in report_upload.py. Firestore uploads will not work.")

async def upload_report_to_firestore(report_content, portfolio_json, doc_id=None):
    """Upload a report and portfolio data to Firestore.
    
    Args:
        report_content: The report content to upload
        portfolio_json: Portfolio JSON data to upload
        doc_id: Optional document ID for the report
        
    Returns:
        str: The document ID of the uploaded report, or None if upload failed
    """
    if not FIRESTORE_AVAILABLE:
        log_warning("Firestore upload requested but Firestore is not available")
        return None
        
    import tempfile
    import os
    
    try:
        # Initialize Firestore uploader
        uploader = FirestoreUploader()
        
        # Create temporary files for the report and portfolio data
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as report_file:
            report_file.write(report_content)
            report_path = report_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as portfolio_file:
            if isinstance(portfolio_json, str):
                portfolio_file.write(portfolio_json)
            else:
                json.dump(portfolio_json, portfolio_file)
            portfolio_path = portfolio_file.name
        
        try:
            # Upload both files using upload_portfolio_data
            log_info("Uploading investment portfolio report and data to Firestore...")
            report_success, weights_success = await asyncio.to_thread(
                uploader.upload_portfolio_data,
                report_path,
                portfolio_path
            )
            
            if report_success:
                # Get the document ID from the last uploaded report
                report_doc_id = uploader.last_uploaded_ids.get('reports')
                log_success(f"Successfully uploaded report to Firestore with document ID: {report_doc_id}")
                
                if weights_success:
                    portfolio_doc_id = uploader.last_uploaded_ids.get('portfolio_weights')
                    log_success(f"Successfully uploaded portfolio weights to Firestore with document ID: {portfolio_doc_id}")
                else:
                    log_warning("Failed to upload portfolio weights to Firestore")
                
                return report_doc_id
            else:
                log_warning("Failed to upload report to Firestore")
                return None
        finally:
            # Clean up temporary files
            try:
                os.unlink(report_path)
                os.unlink(portfolio_path)
            except Exception as cleanup_error:
                log_warning(f"Error cleaning up temporary files: {cleanup_error}")
            
    except Exception as e:
        log_error(f"Error uploading to Firestore: {e}")
        return None

async def generate_and_upload_alternative_report(report_content, current_report_firestore_id, openai_client=None):
    """
    Generate and upload an alternative report to Firestore, benchmarking the current report against the previous report.
    - report_content: The newly generated report content (markdown string)
    - current_report_firestore_id: The Firestore docId of the just-uploaded report
    - openai_client: Optional OpenAI client (if not provided, will create one)
    """
    if not FIRESTORE_AVAILABLE:
        log_warning("Alternative report generation requested but Firestore is not available")
        return None
        
    try:
        # Initialize OpenAI client if not provided
        if not openai_client:
            from openai import OpenAI
            openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Verify Firestore is actually available before proceeding
        if not FIRESTORE_AVAILABLE:
            log_warning("Skipping alternative report generation: Firestore is not available")
            return None
            
        try:    
            # Initialize Firestore uploader - consistent with other functions
            uploader = FirestoreUploader()
            db = uploader.db
            
            # Get the current report details
            portfolios_ref = uploader.collection  # This uses the 'portfolios' collection
            current_report = portfolios_ref.document(current_report_firestore_id).get()
        except google.api_core.exceptions.NotFound as e:
            # Handle specifically the database not found error
            log_warning(f"Skipping alternative report generation: Firestore database not found - {e}")
            return None
        except Exception as e:
            # Handle other Firestore client errors
            log_warning(f"Skipping alternative report generation: Firestore error - {e}")
            return None
        
        if not current_report.exists:
            log_warning(f"Current report {current_report_firestore_id} not found in Firestore")
            return None
            
        # Query for the previous report (the latest report before the current one)
        # Modified query to avoid requiring composite index
        query = portfolios_ref.where('doc_type', '==', 'report').where('is_latest', '==', True)
        
        # Get all the latest reports and filter in application code to avoid index requirement
        latest_reports = list(query.stream())
        previous_reports = [doc for doc in latest_reports if doc.id != current_report_firestore_id]
        
        # Sort the results manually by docId
        previous_reports.sort(key=lambda doc: doc.id, reverse=True)
        
        # Limit to 1 result
        if len(previous_reports) > 1:
            previous_reports = previous_reports[:1]
        
        # At this point, previous_reports contains the filtered and sorted results
        if not previous_reports:
            log_warning("No previous report found to generate alternative report")
            return None
            
        previous_doc = previous_reports[0]
        previous_data = previous_doc.to_dict()
        previous_content = previous_data.get('content', '')
        previous_date = previous_data.get('created_at', datetime.utcnow())
        
        if not previous_content:
            log_warning("Previous report has no content")
            return None
            
        # Generate the alternative report
        log_info("Generating alternative report using OpenAI...")
        
        prompt = f"""
        You are a world-class investment analyst. You have been given two versions of an investment portfolio report:
        1. The previous report (from {previous_date})
        2. The current report (just generated)
        
        Your task is to create an ALTERNATIVE version of the current report that takes a different but equally valid perspective
        on the same market data and portfolio positions.
        
        Requirements for the alternative report:
        1. It should have the EXACT SAME SECTIONS as the current report
        2. It should maintain approximately the same length and detail level
        3. It should take some positions that contrast with the current report while remaining plausible
        4. It should identify 2-3 assets where your view differs from the current report
        5. All data and market facts should remain accurate and consistent with reality
        6. The tone should be professional, analytical, and balanced
        7. Format in markdown with proper headers, bullet points, and tables
        
        Previous report excerpt (first 2000 chars):
        {previous_content[:2000]}
        
        Current report (full):
        {report_content}
        
        Generate a complete alternative report that follows the same structure but offers a distinct perspective:
        """
        
        # Make the API call
        response = await asyncio.to_thread(
            openai_client.chat.completions.create,
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=4000
        )
        
        # Extract the generated content
        alternative_report = response.choices[0].message.content
        
        # Access Firestore collections for alternatives
        alt_collection = db.collection('report-alternatives')
        
        # First, mark all existing alternative reports as not latest
        alt_query = alt_collection.where('doc_type', '==', 'report-alternative').where('is_latest', '==', True)
        alt_docs = list(alt_query.stream())
        log_info(f"Number of existing report-alternative docs to update: {len(alt_docs)}")
        
        if not alt_docs:
            log_info("No existing 'report-alternative' documents found to update.")
        else:
            for alt_doc in alt_docs:
                log_info(f"Marking alt doc {alt_doc.id} as not latest")
                try:
                    alt_collection.document(alt_doc.id).update({'is_latest': False})
                except Exception as update_exc:
                    log_warning(f"Failed to update alt doc {alt_doc.id}: {update_exc}")

        # Add the new alternative report
        alt_doc_ref = alt_collection.document()
        upload_data = {
            'content': alternative_report,
            'doc_type': 'report-alternative',
            'file_format': 'markdown',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'is_latest': True,
            'alternative_report_Id': alt_doc_ref.id,
            'source_report_id': current_report_firestore_id,
            'previous_report_id': previous_doc.id,
            'previous_report_date': previous_date,
            'created_at': datetime.utcnow()
        }
        
        log_info(f"Uploading alternative report to Firestore")
        alt_doc_ref.set(upload_data)
        log_success(f"Alternative report uploaded to Firestore with doc ID: {alt_doc_ref.id}")
        
        # Import the portfolio generator to use generate_alternative_portfolio_weights
        from portfolio_generator.modules.portfolio_generator import generate_alternative_portfolio_weights
        
        # Generate and upload alternative portfolio weights
        try:
            weights_query = alt_collection.where('doc_type', '==', 'portfolio-weights-alternative').where('is_latest', '==', True)
            existing_weights = list(weights_query.stream())
            
            if existing_weights:
                for wdoc in existing_weights:
                    alt_collection.document(wdoc.id).update({'is_latest': False})
                    
            orig_query = reports_ref.where('doc_type', '==', 'portfolio_weights').where('is_latest', '==', True)
            orig_docs = list(orig_query.stream())
            
            if orig_docs:
                orig = orig_docs[0]
                raw = orig.to_dict().get('content', {})
                
                if isinstance(raw, dict):
                    orig_data = raw
                else:
                    try:
                        orig_data = json.loads(raw)
                    except Exception:
                        orig_data = {}
                        
                assets = orig_data.get('data', {}).get('assets', [])
                report_date = orig_data.get('data', {}).get('report_date', '')
            else:
                assets, report_date = [], ''
                
            # Generate alternative portfolio weights
            alt_weights_json = await generate_alternative_portfolio_weights(openai_client, assets, alternative_report)
            
            # Upload to Firestore
            alt_weights_ref = alt_collection.document()
            weights_payload = {
                'content': alt_weights_json,
                'doc_type': 'portfolio-weights-alternative',
                'file_format': 'json',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'is_latest': True,
                'alternative_weights_id': alt_weights_ref.id,
                'source_report_id': current_report_firestore_id,
                'source_weights_id': orig.id if orig_docs else None,
                'created_at': datetime.utcnow()
            }
            
            log_info("Uploading alternative portfolio weights")
            alt_weights_ref.set(weights_payload)
            log_success(f"Alternative portfolio weights uploaded with id: {alt_weights_ref.id}")
            
        except Exception as w_err:
            log_error(f"Failed to upload alternative portfolio weights: {w_err}")
            
        return alt_doc_ref.id
        
    except Exception as e:
        log_error(f"Failed to upload alternative report: {e}")
        import traceback
        traceback.print_exc()
        return None
