import os
import json
from datetime import datetime
import glob
from portfolio_generator.comprehensive_portfolio_generator import generate_portfolio_json

try:
    from portfolio_generator.firestore_uploader import FirestoreUploader
except ImportError:
    FirestoreUploader = None

from portfolio_generator.report_improver import FIRESTORE_AVAILABLE, EnhancedFirestoreUploader

async def save_improved_weights(openai_client, assets_list, current_date, output_dir="output", original_report_id=None):
    """
    Call generate_portfolio_json, save improved weights as a new file with status 'improved',
    set is_latest true, mark older files as false, and upload as a new Firestore document.
    """
    import uuid
    from datetime import datetime
    # Generate improved portfolio JSON
    improved_json_str = await generate_portfolio_json(openai_client, assets_list, current_date)
    improved_json = json.loads(improved_json_str) if isinstance(improved_json_str, str) else improved_json_str
    improved_json["status"] = "improved"
    improved_json["is_latest"] = True
    if original_report_id:
        improved_json["original_report_id"] = original_report_id

    os.makedirs(output_dir, exist_ok=True)
    # Mark all old weights files as is_latest false
    for f in glob.glob(os.path.join(output_dir, "portfolio_weights_*.json")):
        try:
            with open(f, "r+") as oldf:
                data = json.load(oldf)
                if data.get("is_latest"):
                    data["is_latest"] = False
                    oldf.seek(0)
                    oldf.truncate()
                    json.dump(data, oldf, indent=2)
        except Exception:
            pass

    # Upload to Firestore using FirestoreUploader.upload_file (after marking old files as not latest, before saving locally)
    import traceback
    new_doc_id = None
    print(f"[DEBUG] FIRESTORE_AVAILABLE: {FIRESTORE_AVAILABLE}")
    print(f"[DEBUG] FirestoreUploader: {FirestoreUploader}")
    if FIRESTORE_AVAILABLE:
        if FirestoreUploader is None:
            print("[ERROR] FirestoreUploader is None despite FIRESTORE_AVAILABLE being True.")
            print("[DEBUG] Attempting to re-import FirestoreUploader for diagnostic purposes...")
            try:
                from portfolio_generator.firestore_uploader import FirestoreUploader as FirestoreUploaderTest
                print(f"[DEBUG] Re-imported FirestoreUploader: {FirestoreUploaderTest}")
            except Exception as import_ex:
                print(f"[ERROR] Re-import failed: {import_ex}")
                traceback.print_exc()
            raise RuntimeError("FIRESTORE_AVAILABLE is True but FirestoreUploader could not be imported. Please check your Firestore installation.")
        try:
            print("[INFO] Instantiating FirestoreUploader...")
            uploader = FirestoreUploader()
            print("[INFO] FirestoreUploader instantiated successfully.")
            # Save to a temp file for upload
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as tmpf:
                json.dump(improved_json, tmpf)
                tmpf_path = tmpf.name
            print(f"[INFO] Temporary file for upload created at: {tmpf_path}")
            result = uploader.upload_file(tmpf_path, doc_type='portfolio_weights', file_format='json', is_latest=True)
            print(f"[INFO] Upload result: {result}")
            # Try to fetch and print the latest doc ID
            try:
                # Query for latest doc with this filename
                basename = os.path.basename(tmpf_path)
                print(f"[DEBUG] Querying Firestore for uploaded file with basename: {basename}")
                # Get the doc by filename
                # Try with new filter() syntax first
                try:
                    docs = list(uploader.collection.filter('filename', '==', basename).order_by('timestamp', direction='DESCENDING').limit(1).stream())
                except AttributeError:
                    # Fall back to older where() syntax
                    print("Using older Firestore where() method - consider upgrading google-cloud-firestore")
                    docs = list(uploader.collection.where('filename', '==', basename).order_by('timestamp', direction='DESCENDING').limit(1).stream())
                if docs:
                    print(f"[INFO] Uploaded improved weights to Firestore as document: {docs[0].id}")
                else:
                    print(f"[INFO] Uploaded improved weights to Firestore, but could not fetch document ID.")
            except Exception as ex:
                print(f"[WARNING] Uploaded weights but failed to retrieve Firestore doc ID: {ex}")
                traceback.print_exc()
        except Exception as e:
            print(f"[ERROR] Failed to upload improved weights to Firestore: {e}")
            traceback.print_exc()

    # Save improved weights file
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    improved_path = os.path.join(output_dir, f"portfolio_weights_improved_{timestamp}.json")
    with open(improved_path, "w") as outf:
        json.dump(improved_json, outf, indent=2)
    return improved_path


