import os
from datetime import datetime
from google.cloud import firestore
from google.cloud import storage
# from portfolio_generator.modules.report_generator import storage
import logging

logger = logging.getLogger(__name__)


class GCSUploader:
    """Handle uploads to Google Cloud Storage."""
    
    def __init__(self, bucket_name: str = "reportpdfhedgefundintelligence"):
        """
        Initialize GCS uploader.
        
        Args:
            bucket_name: Name of the GCS bucket
        """
        self.bucket_name = bucket_name
        self.storage_client = None
        
    def _get_client(self):
        """Get or create storage client."""
        if not self.storage_client:
            self.storage_client = storage.Client()
        return self.storage_client
        
    def upload_pdf(self, source_file_path: str, 
                   destination_blob_name: str = None) -> str:
        """
        Upload a PDF file to GCS.
        
        Args:
            source_file_path: Path to the local PDF file
            destination_blob_name: Optional custom destination path in GCS
            
        Returns:
            The GCS path of the uploaded file
        """
        try:
            client = self._get_client()
            bucket = client.bucket(self.bucket_name)
            
            # Generate destination path based on current date if not provided
            if not destination_blob_name:
                date_path = datetime.now().strftime("%Y/%m/%d")
                filename = os.path.basename(source_file_path)
                destination_blob_name = f"{date_path}/{filename}"
                
            blob = bucket.blob(destination_blob_name)
            
            # Set generation match precondition for new files
            generation_match_precondition = 0
            
            # Upload the file
            blob.upload_from_filename(
                source_file_path,
                if_generation_match=generation_match_precondition
            )
            
            logger.info(f"File {source_file_path} uploaded to {destination_blob_name}")
            
            # Return the full GCS path
            return f"gs://{self.bucket_name}/{destination_blob_name}"
            
        except Exception as e:
            logger.error(f"Failed to upload file to GCS: {e}")
            raise
        