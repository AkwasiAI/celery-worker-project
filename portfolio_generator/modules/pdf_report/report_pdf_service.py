import os
import tempfile
from datetime import datetime
from typing import Dict, Optional
import logging

from .pdf_generator import PDFReportGenerator
from .gcs_uploader import GCSUploader

logger = logging.getLogger(__name__)


class ReportPDFService:
    """Main service to generate and upload PDF reports."""
    
    def __init__(self, bucket_name: str = "reportpdfhedgefundintelligence"):
        """
        Initialize the PDF report service.
        
        Args:
            bucket_name: GCS bucket name for uploads
        """
        self.pdf_generator = PDFReportGenerator()
        self.gcs_uploader = GCSUploader(bucket_name)
        
    def generate_and_upload_pdf(self, 
                               report_sections: Dict[str, str],
                               report_date: str = None,
                               upload_to_gcs: bool = True,
                               keep_local_copy: bool = False) -> Dict[str, str]:
        """
        Generate PDF from report sections and optionally upload to GCS.
        
        Args:
            report_sections: Dictionary of section_name -> section_content
            report_date: Optional report date string
            upload_to_gcs: Whether to upload to GCS (default: True)
            keep_local_copy: Whether to keep the local PDF file (default: False)
            
        Returns:
            Dictionary with 'local_path' and optionally 'gcs_path'
        """
        result = {}
        
        try:
            # Generate timestamp for filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Use temp directory if not keeping local copy
            if keep_local_copy:
                output_dir = os.getcwd()
            else:
                output_dir = tempfile.gettempdir()
                
            output_filename = os.path.join(
                output_dir, 
                f"investment_report_{timestamp}.pdf"
            )
            
            # Generate the PDF
            logger.info("Generating PDF report...")
            local_path = self.pdf_generator.generate_pdf(
                report_sections=report_sections,
                output_filename=output_filename,
                report_date=report_date
            )
            result['local_path'] = local_path
            
            # Upload to GCS if requested
            if upload_to_gcs:
                logger.info("Uploading PDF to Google Cloud Storage...")
                gcs_path = self.gcs_uploader.upload_pdf(local_path)
                result['gcs_path'] = gcs_path
                
            # Clean up local file if not keeping it
            if not keep_local_copy and os.path.exists(local_path):
                os.remove(local_path)
                logger.info("Temporary local PDF file removed")
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate/upload PDF report: {e}")
            raise


# Example usage and testing
if __name__ == "__main__":
    import argparse
    import sys
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Generate PDF report from markdown sections')
    parser.add_argument('--no-upload', action='store_true', help='Disable GCS upload (useful for testing without credentials)')
    parser.add_argument('--keep-local', action='store_true', default=True, help='Keep local copy of PDF')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Example report sections for testing
    dummy_report_sections = {
        "Latest Market News": """# Market Update
        
**Key Developments:**
- Energy markets showed volatility
- Shipping rates increased by 15%
- Commodity prices stabilized

## Energy Sector
The energy sector experienced significant movements...

## Shipping Industry
Tanker rates continue to climb due to...
""",
        "Executive Summary - Allocation": """## Portfolio Allocation Changes

Asset   Previous   Current   Change
STNG    12%        15%       +3%
SHEL    8%         10%       +2%
""",
        "Executive Summary - Insights": """### Key Insights

- Market conditions favor energy and shipping sectors
- Geopolitical tensions create opportunities
- Commodity super-cycle continues
"""
    }
    
    # Create service and generate PDF
    service = ReportPDFService()
    
    try:
        # Generate PDF with optional upload based on command line args
        result = service.generate_and_upload_pdf(
            report_sections=dummy_report_sections,
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            upload_to_gcs=not args.no_upload,  # Disable upload if --no-upload flag is used
            keep_local_copy=args.keep_local  # Keep local copy for inspection
        )
        
        print(f"\nSuccess! PDF generated: {result}")
        if 'gcs_path' in result:
            print(f"Uploaded to GCS: {result['gcs_path']}")
        else:
            print("PDF was not uploaded to GCS")
            
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
