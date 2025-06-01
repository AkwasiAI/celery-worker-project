from portfolio_generator.modules.pdf_report.pdf_generator import PDFReportGenerator

sections = {
    "Problem Table": """## The Problematic Content

| Asset | Weight | Change |
|-------|--------|--------|
| AAPL  | 8%     | +2%    |
| MSFT  | 7%     | +1%    |

STNG    15%    +18.5%    Outperform
SHEL    10%    +12.3%    Neutral
""",
    "Special Characters": "Testing • bullets and \"quotes\""
}

gen = PDFReportGenerator()
output = gen.generate_pdf(sections)
print(f"SUCCESS! PDF at: {output}")
