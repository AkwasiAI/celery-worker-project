import os
import tempfile
import base64
import logging
from typing import List, Optional

from dotenv import load_dotenv
from google.cloud import storage
import openai
import cv2
from PIL import Image
import numpy as np

# Optional: tiktoken for accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

def load_env():
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuration constants
default_bucket_name = "screenrecordinghedgefundintelligence"
default_base_path = "videos"
default_valid_video_exts = {".mp4", ".mov", ".avi", ".webm"}
default_frame_interval_seconds = 5
default_max_context_tokens_to_return = 3072
default_max_chunk_tokens_for_summarization = 1200
default_vision_model = "gpt-4.1"
default_summarization_model = "gpt-4.1-mini"
default_fps = 24

def encode_image_to_base64(frame: np.ndarray) -> str:
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')

def count_tokens(text: str, model: str = default_summarization_model) -> int:
    if TIKTOKEN_AVAILABLE:
        try:
            enc = tiktoken.encoding_for_model(model)
            return len(enc.encode(text))
        except Exception:
            pass
    # Fallback: rough estimate (1 token ≈ 4 chars for English)
    return max(1, len(text) // 4)

def call_openai_vision_api(image_b64: str, model: str) -> Optional[str]:
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert financial analyst."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this frame from a financial terminal screen recording. Describe key data points, text, charts, indicators, and overall information presented."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "low"}},
                    ],
                },
            ],
            max_tokens=256,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI Vision API error: {e}")
        return None

def call_openai_summarize_api(text: str, model: str) -> Optional[str]:
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert financial analyst."},
                {"role": "user", "content": f"Summarize the following extracted descriptions from a financial screen recording, focusing on key financial data, trends, and insights. Be concise.\n\n{text}"},
            ],
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI Summarization API error: {e}")
        return None

def _process_single_video_blob(blob, tmp_dir: str, frame_interval_seconds: int, max_chunk_tokens_for_summarization: int, vision_model: str, summarization_model: str) -> Optional[str]:
    video_contexts = []
    chunk = []
    chunk_token_count = 0
    temp_video_path = None
    try:
        # Download blob to temp file
        with tempfile.NamedTemporaryFile(delete=False, dir=tmp_dir, suffix=os.path.splitext(blob.name)[1]) as tmp_file:
            temp_video_path = tmp_file.name
            blob.download_to_filename(temp_video_path)
        cap = cv2.VideoCapture(temp_video_path)
        if not cap.isOpened():
            logging.error(f"Failed to open video: {blob.name}")
            return None
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 1e-2:
            fps = default_fps
        frame_interval = int(fps * frame_interval_seconds)
        frame_idx = 0
        success, frame = cap.read()
        while success:
            if frame_idx % frame_interval == 0:
                try:
                    image_b64 = encode_image_to_base64(frame)
                    desc = call_openai_vision_api(image_b64, vision_model)
                    if desc:
                        desc_tokens = count_tokens(desc, summarization_model)
                        if chunk_token_count + desc_tokens > max_chunk_tokens_for_summarization:
                            # Summarize current chunk
                            chunk_text = "\n".join(chunk)
                            summary = call_openai_summarize_api(chunk_text, summarization_model)
                            if summary:
                                video_contexts.append(summary)
                            chunk = []
                            chunk_token_count = 0
                        chunk.append(desc)
                        chunk_token_count += desc_tokens
                except Exception as e:
                    logging.error(f"Frame processing error in {blob.name}: {e}")
            success, frame = cap.read()
            frame_idx += 1
        # Summarize any remaining chunk
        if chunk:
            chunk_text = "\n".join(chunk)
            summary = call_openai_summarize_api(chunk_text, summarization_model)
            if summary:
                video_contexts.append(summary)
        cap.release()
        return "\n".join(video_contexts)
    except Exception as e:
        logging.error(f"Error processing video {blob.name}: {e}")
        return None
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
            except Exception as e:
                logging.warning(f"Failed to remove temp file {temp_video_path}: {e}")

def generate_context_from_gcs_folder(
    folder_id: str,
    frame_interval_seconds: int = default_frame_interval_seconds,
    max_context_tokens_to_return: int = default_max_context_tokens_to_return,
    max_chunk_tokens_for_summarization: int = default_max_chunk_tokens_for_summarization,
    vision_model: str = default_vision_model,
    summarization_model: str = default_summarization_model,
    bucket_name: str = default_bucket_name,
    base_path: str = default_base_path,
    valid_video_exts: set = default_valid_video_exts,
) -> str:
    """
    Processes all valid videos in a GCS folder, extracts and summarizes their content, and returns a combined context string.
    """
    load_env()
    logging.info(f"Starting context generation for folder_id: {folder_id}")
    client = storage.Client()
    prefix = f"{base_path}/{folder_id}/"
    try:
        blobs = list(client.list_blobs(bucket_name, prefix=prefix))
    except Exception as e:
        logging.error(f"Failed to list blobs in {bucket_name}/{prefix}: {e}")
        return ""
    video_blobs = [
        blob for blob in blobs
        if any(blob.name.lower().endswith(ext) for ext in valid_video_exts)
        and blob.size > 0
        and blob.name != prefix
    ]
    if not video_blobs:
        logging.warning(f"No valid video files found in {bucket_name}/{prefix}")
        # Return empty string so caller can proceed gracefully
        return ""
    all_contexts = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for blob in video_blobs:
            logging.info(f"Processing video: {blob.name}")
            context = _process_single_video_blob(
                blob,
                tmp_dir,
                frame_interval_seconds,
                max_chunk_tokens_for_summarization,
                vision_model,
                summarization_model,
            )
            if context:
                filename = os.path.basename(blob.name)
                all_contexts.append(f"\n\n==== Context from video: {filename} ====\n\n{context}")
            else:
                logging.warning(f"No context generated for video: {blob.name}")
    final_context = "\n".join(all_contexts)
    total_tokens = count_tokens(final_context, summarization_model)
    if total_tokens > max_context_tokens_to_return:
        logging.info(f"Final context exceeds {max_context_tokens_to_return} tokens; summarizing.")
        summary = call_openai_summarize_api(final_context, summarization_model)
        if summary:
            final_context = summary
        else:
            logging.error("Final summarization failed; returning truncated context.")
            # Truncate to token limit
            approx_chars = max_context_tokens_to_return * 4
            final_context = final_context[:approx_chars]
    return final_context
