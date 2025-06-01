#!/usr/bin/env python
"""
Test script for the full PDF report service with GCS upload (optional).
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from portfolio_generator.modules.pdf_report.report_pdf_service import ReportPDFService

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_report_service():
    """Test the full report service including PDF generation and optional GCS upload."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test PDF report generation and upload')
    parser.add_argument('--no-upload', action='store_true', 
                        help='Disable GCS upload (for testing without credentials)')
    parser.add_argument('--keep-local', action='store_true',
                        help='Keep local PDF file after upload')
    args = parser.parse_args()
    
    logger.info("Starting PDF report service test...")
    
    # Create test report data
    test_report = {
        "Executive Summary": """# Executive Summary

This report provides an overview of the current investment portfolio performance 
and recommendations for the next quarter.

**Key Performance Indicators:**
- Total return: +12.5%
- Benchmark comparison: +3.2% over benchmark
- Risk-adjusted return (Sharpe): 1.8
""",
        "Portfolio Analysis": """## Portfolio Analysis

The portfolio currently consists of the following asset allocation:

Asset Class    Current    Target    Difference
Equities       65%        60%       +5%
Fixed Income   25%        30%       -5%
Alternatives   10%        10%       0%

### Sector Breakdown

Sector         Weight     Performance
Energy         15%        +18.5%
Technology     25%        +22.3%
Healthcare     20%        +8.7%
Financials     15%        +5.2%
Consumer       15%        +7.8%
Other          10%        +4.1%
""",
        "Recommendations": """## Investment Recommendations

Based on current market conditions and portfolio performance, we recommend the 
following adjustments:

- **Reduce** exposure to Technology by 5%
- **Increase** allocation to Healthcare by 3%
- **Increase** allocation to Fixed Income by 2%

### Specific Actions

| Action | Ticker | Current % | Target % | Change |
|--------|--------|-----------|----------|--------|
| Sell   | AAPL   | 8%        | 6%       | -2%    |
| Sell   | MSFT   | 7%        | 4%       | -3%    |
| Buy    | JNJ    | 5%        | 7%       | +2%    |
| Buy    | PFE    | 3%        | 4%       | +1%    |
| Buy    | AGG    | 15%       | 17%      | +2%    |
"""
    }
    
    # Generate timestamp for report ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_id = f"TEST_REPORT_{timestamp}"
    
    # Initialize the PDF service
    pdf_service = ReportPDFService()
    
    # Generate and optionally upload the PDF
    try:
        result = pdf_service.generate_and_upload_pdf(
            report_sections=test_report,
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            upload_to_gcs=not args.no_upload,
            keep_local_copy=args.keep_local
        )
        
        if args.no_upload:
            logger.info(f"PDF successfully generated at: {result['local_path']}")
            print(f"\nSuccess! PDF generated at: {result['local_path']}")
        else:
            logger.info(f"PDF successfully generated and uploaded. GCS URL: {result.get('gcs_path', 'Not uploaded')}")
            print(f"\nSuccess! PDF generated at: {result['local_path']}")
            if 'gcs_path' in result:
                print(f"Uploaded to GCS: {result['gcs_path']}")
            else:
                print("PDF was not uploaded to GCS")
            
    except Exception as e:
        logger.error(f"Error in PDF generation/upload process: {e}")
        print(f"\nError: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(test_report_service())
