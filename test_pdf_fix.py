#!/usr/bin/env python
"""
Test script for PDF report generation with problematic content.
This tests the improved sanitization and table rendering.
"""

import logging
from datetime import datetime
from portfolio_generator.modules.pdf_report.pdf_generator import PDFReportGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test with known problematic content
test_sections = {
    "Table Test": """## Table Test
    
| Asset | Weight | Change |
|-------|--------|--------|
| AAPL  | 8%     | +2%    |
| MSFT  | 7%     | +1%    |

STNG    15%    +18.5%    Outperform
SHEL    10%    +12.3%    Neutral
""",
    "Special Chars": """# Special Characters
    
Testing "smart quotes" and • bullets
Em dash — and ellipsis…
""",
    "Mixed Content": """## Mixed Content
    
Here's a section with a mix of content types:

**Key Points:**
- Bullet point one with normal text
- Second bullet • with special character
- Third point with "quoted text" and percentages (20%)

Plain text table:
Asset   Weight   Performance   Rating
XYZ     8%       +5.2%         Buy
ABC     12%      -2.3%         Hold
"""
}

def test_pdf_generation():
    """Generate a test PDF with problematic content."""
    logger.info("Starting PDF generation test...")
    
    # Create PDF generator
    generator = PDFReportGenerator()
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_pdf_fix_{timestamp}.pdf"
    
    # Generate PDF
    try:
        output = generator.generate_pdf(
            report_sections=test_sections,
            output_filename=filename,
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        logger.info(f"PDF successfully generated: {output}")
        print(f"\nSuccess! PDF generated at: {output}")
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_pdf_generation()
