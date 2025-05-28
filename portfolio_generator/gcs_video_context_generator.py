import os
import logging
import time
import tempfile
from typing import List, Optional, Tuple
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.cloud import storage

# Configuration constants
DEFAULT_MODEL = "gemini-2.5-pro-preview-05-06"
DEFAULT_VALID_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
DEFAULT_BUCKET_NAME = "screenrecordinghedgefundintelligence"
DEFAULT_BASE_PATH = "videos"
DEFAULT_CONTEXT_EXTRACTION_PROMPT = """
Analyze this video comprehensively and extract all relevant context. Focus on:

1. Key visual elements and scenes
2. Any text, data, or information displayed
3. Important actions or events that occur
4. Audio content if present (dialogue, narration, sounds)
5. Overall themes and main points
6. Timeline of events or progression
7. Any technical or domain-specific information

Provide a detailed summary that captures the essential context someone would need to understand what this video contains and its key information.
"""

def load_env():
    """Load environment variables."""
    load_dotenv()

def upload_video_file(file_path: str, display_name: Optional[str] = None) -> genai.types.File:
    """
    Upload a video file to Gemini Files API.
    
    Args:
        file_path: Path to the video file
        display_name: Optional display name for the file
        
    Returns:
        Uploaded file object
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")
    
    if not display_name:
        display_name = os.path.basename(file_path)
    
    logging.info(f"Uploading video file: {file_path}")
    
    try:
        # Use genai.Client for file upload
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        uploaded_file = client.files.upload(
            file=file_path,
            config={
                "display_name": display_name  # Use actual display name instead of "test"
            }
        )
        
        # Wait for file processing to complete - THIS IS CRITICAL!
        while uploaded_file.state == "PROCESSING":
            logging.info("Waiting for video processing to complete...")
            time.sleep(2)
            # Refresh file state via client
            uploaded_file = client.files.get(name=uploaded_file.name)
        
        if uploaded_file.state == "FAILED":
            raise Exception(f"Video processing failed: {uploaded_file.state}")
            
        logging.info(f"Video uploaded successfully: {uploaded_file.name} (state: {uploaded_file.state})")
        return uploaded_file
        
    except Exception as e:
        logging.error(f"Failed to upload video {file_path}: {e}")
        raise

def extract_context_from_video(
    uploaded_file: genai.types.File, 
    prompt: str = DEFAULT_CONTEXT_EXTRACTION_PROMPT,
    model_name: str = DEFAULT_MODEL
) -> Optional[str]:
    """
    Extract context from an uploaded video using Gemini.
    """
    try:
        # Initialize Gemini client
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        logging.info(f"Analyzing video: {uploaded_file.name}")
        
        # Generate content using the specified model
        response = client.models.generate_content(
            model=model_name,
            contents=[uploaded_file, prompt]
        )
        
        if response.text:
            logging.info(f"Successfully extracted context from {uploaded_file.name}")
            return response.text.strip()
        
        logging.warning(f"No context extracted from {uploaded_file.name}")
        return None
            
    except Exception as e:
        logging.error(f"Error extracting context from {uploaded_file.name}: {e}")
        return None

def cleanup_uploaded_file(uploaded_file: genai.types.File):
    """Clean up uploaded file from Gemini Files API."""
    try:
        # Use the client to delete the file
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        client.files.delete(name=uploaded_file.name)
        logging.info(f"Cleaned up uploaded file: {uploaded_file.display_name}")
    except Exception as e:
        logging.warning(f"Failed to cleanup file {uploaded_file.display_name}: {e}")

def get_latest_video_from_gcs(
    folder_id: str,
    bucket_name: str = DEFAULT_BUCKET_NAME,
    base_path: str = DEFAULT_BASE_PATH,
    valid_extensions: set = DEFAULT_VALID_VIDEO_EXTS
) -> Optional[Tuple[storage.Blob, str]]:
    """
    Get the latest video file from a GCS folder based on creation time.
    
    Args:
        folder_id: The folder ID (e.g., 'SrFrHmacE8wK82XH6Q8d')
        bucket_name: GCS bucket name
        base_path: Base path in bucket
        valid_extensions: Set of valid video extensions
        
    Returns:
        Tuple of (blob, local_temp_path) for the latest video, or None if not found
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        prefix = f"{base_path}/{folder_id}/"
        
        logging.info(f"Searching for videos in gs://{bucket_name}/{prefix}")
        
        # List all blobs in the folder
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        # Filter for video files
        video_blobs = [
            blob for blob in blobs
            if any(blob.name.lower().endswith(ext) for ext in valid_extensions)
            and blob.size > 0 
            and not blob.name.endswith('/')  # Exclude folder markers
        ]
        
        if not video_blobs:
            logging.warning(f"No video files found in gs://{bucket_name}/{prefix}")
            return None
        
        logging.info(f"Found {len(video_blobs)} video files")
        
        # Sort by creation time (most recent first)
        video_blobs.sort(key=lambda blob: blob.time_created, reverse=True)
        
        # Get the latest video
        latest_blob = video_blobs[0]
        
        logging.info(f"Latest video: {latest_blob.name} (created: {latest_blob.time_created})")
        
        # Download to temporary file
        temp_dir = tempfile.mkdtemp()
        filename = os.path.basename(latest_blob.name)
        temp_path = os.path.join(temp_dir, filename)
        
        logging.info(f"Downloading {latest_blob.name} to {temp_path}")
        latest_blob.download_to_filename(temp_path)
        
        return latest_blob, temp_path
        
    except Exception as e:
        logging.error(f"Error getting latest video from GCS: {e}")
        return None

def process_latest_video_from_gcs(
    folder_id: str,
    prompt: str = DEFAULT_CONTEXT_EXTRACTION_PROMPT,
    model_name: str = DEFAULT_MODEL,
    bucket_name: str = DEFAULT_BUCKET_NAME,
    base_path: str = DEFAULT_BASE_PATH,
    cleanup: bool = True
) -> Optional[dict]:
    """
    Process the latest video from a GCS folder and extract context.
    
    Args:
        folder_id: The folder ID (e.g., 'SrFrHmacE8wK82XH6Q8d')
        prompt: Custom prompt for context extraction
        model_name: Gemini model to use
        bucket_name: GCS bucket name
        base_path: Base path in bucket
        cleanup: Whether to cleanup uploaded files after processing
        
    Returns:
        Dictionary with video info and extracted context, or None if failed
    """
    temp_path = None
    uploaded_file = None
    
    try:
        # Get the latest video from GCS
        result = get_latest_video_from_gcs(folder_id, bucket_name, base_path)
        if not result:
            return None
        
        blob, temp_path = result
        
        # Upload to Gemini Files API
        uploaded_file = upload_video_file(temp_path, os.path.basename(blob.name))
        
        # Extract context
        context = extract_context_from_video(uploaded_file, prompt, model_name)
        
        return {
            'gcs_path': f"gs://{bucket_name}/{blob.name}",
            'filename': os.path.basename(blob.name),
            'size_bytes': blob.size,
            'created_time': blob.time_created,
            'context': context,
            'success': context is not None
        }
        
    except Exception as e:
        logging.error(f"Error processing latest video: {e}")
        return {
            'gcs_path': None,
            'filename': None,
            'size_bytes': None,
            'created_time': None,
            'context': None,
            'success': False,
            'error': str(e)
        }
        
    finally:
        # Cleanup
        if uploaded_file and cleanup:
            cleanup_uploaded_file(uploaded_file)
        
        if temp_path and os.path.exists(temp_path):
            try:
                # Clean up temp file and directory
                os.remove(temp_path)
                os.rmdir(os.path.dirname(temp_path))
            except Exception as e:
                logging.warning(f"Failed to cleanup temp file {temp_path}: {e}")

def generate_context_from_latest_video(
    folder_id: str,
    prompt: str = DEFAULT_CONTEXT_EXTRACTION_PROMPT,
    model_name: str = DEFAULT_MODEL,
    bucket_name: str = DEFAULT_BUCKET_NAME,
    base_path: str = DEFAULT_BASE_PATH
) -> str:
    """
    Generate context from the latest video in a GCS folder.
    This is the main function that replaces the original generate_context_from_gcs_folder.
    
    Args:
        folder_id: The folder ID (e.g., 'SrFrHmacE8wK82XH6Q8d')
        prompt: Custom prompt for context extraction
        model_name: Gemini model to use
        bucket_name: GCS bucket name
        base_path: Base path in bucket
        
    Returns:
        Extracted context as string, or empty string if failed
    """
    load_env()
    
    logging.info(f"Processing latest video from folder: {folder_id}")
    
    result = process_latest_video_from_gcs(
        folder_id, prompt, model_name, bucket_name, base_path
    )
    
    if not result or not result.get('success'):
        logging.error(f"Failed to process latest video from folder: {folder_id}")
        return ""
    
    filename = result.get('filename', 'unknown')
    context = result.get('context', '')
    
    return f"\n==== Context from latest video: {filename} ====\n\n{context}"

def process_video_file(
    file_path: str, 
    prompt: str = DEFAULT_CONTEXT_EXTRACTION_PROMPT,
    model_name: str = DEFAULT_MODEL,
    cleanup: bool = True
) -> Optional[str]:
    """
    Process a single video file and extract context.
    
    Args:
        file_path: Path to the video file
        prompt: Custom prompt for context extraction
        model_name: Gemini model to use
        cleanup: Whether to cleanup uploaded file after processing
        
    Returns:
        Extracted context as string, or None if failed
    """
    uploaded_file = None
    try:
        uploaded_file = upload_video_file(file_path)
        context = extract_context_from_video(uploaded_file, prompt, model_name)
        return context
        
    finally:
        if uploaded_file and cleanup:
            cleanup_uploaded_file(uploaded_file)

def process_video_directory(
    directory_path: str,
    prompt: str = DEFAULT_CONTEXT_EXTRACTION_PROMPT,
    model_name: str = DEFAULT_MODEL,
    valid_extensions: set = DEFAULT_VALID_VIDEO_EXTS,
    cleanup: bool = True
) -> List[dict]:
    """
    Process all video files in a directory and extract context.
    
    Args:
        directory_path: Path to directory containing video files
        prompt: Custom prompt for context extraction
        model_name: Gemini model to use
        valid_extensions: Set of valid video file extensions
        cleanup: Whether to cleanup uploaded files after processing
        
    Returns:
        List of dictionaries with filename and extracted context
    """
    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    
    # Find all video files
    video_files = []
    for ext in valid_extensions:
        video_files.extend(directory.glob(f"*{ext}"))
        video_files.extend(directory.glob(f"*{ext.upper()}"))
    
    if not video_files:
        logging.warning(f"No video files found in {directory_path}")
        return []
    
    results = []
    
    for video_file in video_files:
        logging.info(f"Processing video: {video_file.name}")
        
        try:
            context = process_video_file(
                str(video_file), 
                prompt, 
                model_name, 
                cleanup
            )
            
            results.append({
                'filename': video_file.name,
                'filepath': str(video_file),
                'context': context,
                'success': context is not None
            })
            
        except Exception as e:
            logging.error(f"Failed to process {video_file.name}: {e}")
            results.append({
                'filename': video_file.name,
                'filepath': str(video_file),
                'context': None,
                'success': False,
                'error': str(e)
            })
    
    return results

def generate_combined_context(
    video_paths: List[str],
    prompt: str = DEFAULT_CONTEXT_EXTRACTION_PROMPT,
    model_name: str = DEFAULT_MODEL,
    cleanup: bool = True
) -> str:
    """
    Process multiple video files and combine their contexts.
    
    Args:
        video_paths: List of paths to video files
        prompt: Custom prompt for context extraction
        model_name: Gemini model to use
        cleanup: Whether to cleanup uploaded files after processing
        
    Returns:
        Combined context from all videos
    """
    contexts = []
    
    for video_path in video_paths:
        if not os.path.exists(video_path):
            logging.warning(f"Video file not found: {video_path}")
            continue
            
        context = process_video_file(video_path, prompt, model_name, cleanup)
        
        if context:
            filename = os.path.basename(video_path)
            contexts.append(f"\n==== Context from video: {filename} ====\n\n{context}")
        else:
            logging.warning(f"No context extracted from {video_path}")
    
    return "\n".join(contexts)

# Example usage functions
def main():
    """Example usage of the video context extractor."""
    load_env()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example 1: Process latest video from GCS folder (NEW - Main use case)
    folder_id = "SrFrHmacE8wK82XH6Q8d"  # Your folder ID
    context = generate_context_from_latest_video(folder_id)
    print("Latest Video Context:", context)
    
    # Example 2: Process latest video with custom financial prompt
    # financial_prompt = """
    # Extract all financial data, charts, and key metrics shown in this video.
    # Focus on:
    # - Stock prices and movements
    # - Trading volumes
    # - Market indicators
    # - Financial news or announcements
    # - Any numerical data or statistics
    # - Screen recordings of trading platforms or financial terminals
    # """
    # 
    # context = generate_context_from_latest_video(folder_id, financial_prompt)
    # print("Financial Context:", context)
    
    # Example 3: Get detailed info about the latest video
    # result = process_latest_video_from_gcs(folder_id)
    # if result and result['success']:
    #     print(f"Processed: {result['filename']}")
    #     print(f"Size: {result['size_bytes']} bytes")
    #     print(f"Created: {result['created_time']}")
    #     print(f"GCS Path: {result['gcs_path']}")
    #     print(f"Context: {result['context'][:200]}...")
    
    # ===== LOCAL FILE EXAMPLES (for reference) =====
    # Example 4: Process a single local video file
    # context = process_video_file("path/to/your/video.mp4")
    # print("Extracted Context:", context)
    
    # Example 5: Process all videos in a local directory
    # results = process_video_directory("path/to/video/directory")
    # for result in results:
    #     print(f"File: {result['filename']}")
    #     print(f"Success: {result['success']}")
    #     if result['context']:
    #         print(f"Context: {result['context'][:200]}...")
    #     print("-" * 50)

if __name__ == "__main__":
    main()