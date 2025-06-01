#!/usr/bin/env python
"""
Simple test script for PDF report generation without GCS upload.
This allows quick testing of the PDF formatting and layout.
"""

import logging
from datetime import datetime
from portfolio_generator.modules.pdf_report.pdf_generator import PDFReportGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_pdf_generation():
    """Generate a test PDF with various formatting examples to verify rendering."""
    logger.info("Starting PDF generation test...")
    
    # Create a test report with examples of all formatting elements
    test_report = {
        "Header Examples": """# Level 1 Header
## Level 2 Header
### Level 3 Header

This is regular paragraph text with no special formatting.

**This is bold text that should appear in bold font**
""",
        "List Examples": """## List Items
        
- First bullet point that should be indented
- Second bullet point with a longer text that might need wrapping to the next line to test proper alignment of wrapped text in bullet points
- Third bullet point with **some bold text** to test mixed formatting
""",
        "Table Examples - Markdown": """## Markdown Table Format
        
| Asset | Previous | Current | Change |
|-------|----------|---------|--------|
| STNG  | 12%      | 15%     | +3%    |
| SHEL  | 8%       | 10%     | +2%    |
| EQNR  | 5%       | 7%      | +2%    |
""",
        "Table Examples - Plain": """## Plain Text Table Format
        
Asset   Previous   Current   Change
STNG    12%        15%       +3%
SHEL    8%         10%       +2%
EQNR    5%         7%        +2%
""",
        "Mixed Content": """## Mixed Content Section
        
This section has a mix of text elements to verify combined rendering.

**Key Points:**
- Point one with important information
- Point two with critical data that may span multiple lines to test proper text wrapping in list items

Asset allocation changes:
STNG    12%        15%       +3%
SHEL    8%         10%       +2%

Additional paragraph after the table to see spacing.
"""
    }
    
    # Create PDF generator
    pdf = PDFReportGenerator()
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_report_{timestamp}.pdf"
    
    # Generate PDF
    try:
        pdf.generate_pdf(test_report, filename)
        logger.info(f"PDF successfully generated: {filename}")
        print(f"\nSuccess! PDF generated at: {filename}")
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_pdf_generation()
