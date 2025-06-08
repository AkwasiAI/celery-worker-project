from typing import Optional
import re

try:
    import weasyprint
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    import markdown
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

    

class MarkdownToPDFConverter:
    def __init__(self):
        self.check_dependencies()

    def check_dependencies(self):
        """Check if WeasyPrint is available"""
        if not WEASYPRINT_AVAILABLE:
            raise ImportError(
                "WeasyPrint and markdown are required. Install with: "
                "pip install weasyprint markdown"
            )

    def convert_weasyprint_with_links(self, markdown_content: str, output_path: str,
                                     custom_css: Optional[str] = None) -> bool:
        """Convert using WeasyPrint with guaranteed clickable links"""
        try:
            # Pre-process markdown to ensure proper link formatting
            processed_markdown = self._preprocess_markdown_links(markdown_content)

            # Convert markdown to HTML with better extensions
            md_parser = markdown.Markdown(extensions=[
                'tables',
                'fenced_code',
                'toc',
                'codehilite',
                'attr_list',
                'nl2br',
                'sane_lists'
            ])
            html_content = md_parser.convert(processed_markdown)

            # Post-process HTML to ensure all links have proper attributes
            html_content = self._ensure_clickable_links(html_content)

            # Enhanced CSS styling with proper link handling
            css_content = custom_css or self._generate_link_optimized_css()

            # Create complete HTML document with proper meta tags and link handling
            full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>{css_content}</style>
</head>
<body>
    <div class="document-container">
        {html_content}
    </div>
</body>
</html>"""

            # Generate PDF with specific options for link preservation
            font_config = FontConfiguration()

            # Create HTML document with base URL for relative links
            html_doc = HTML(string=full_html, base_url="file://")

            # Write PDF with options that preserve links
            html_doc.write_pdf(
                output_path,
                font_config=font_config,
                presentational_hints=True,
                optimize_images=True
            )

            print(f"Successfully converted to PDF: {output_path}")

            # Verify links were preserved
            self._verify_pdf_links(output_path)

            return True

        except Exception as e:
            print(f"WeasyPrint conversion failed: {e}")
            return False

    def _preprocess_markdown_links(self, markdown_content: str) -> str:
        """Pre-process markdown to ensure proper link formatting"""
        # Ensure all URLs are properly formatted
        def fix_url(match):
            text = match.group(1)
            url = match.group(2).strip()

            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://', 'mailto:', 'ftp://')):
                if '@' in url:
                    url = 'mailto:' + url
                else:
                    url = 'https://' + url

            return f'[{text}]({url})'

        # Fix markdown links
        markdown_content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', fix_url, markdown_content)

        # Convert bare URLs to markdown links
        def convert_bare_url(match):
            url = match.group(0)
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return f'[{url}]({url})'

        # Only convert URLs that aren't already in markdown links
        lines = markdown_content.split('\n')
        processed_lines = []

        for line in lines:
            # Skip lines that already contain markdown links
            if '](' not in line:
                # Convert bare URLs
                line = re.sub(r'https?://[^\s<>"]+', convert_bare_url, line)
            processed_lines.append(line)

        return '\n'.join(processed_lines)

    def _ensure_clickable_links(self, html_content: str) -> str:
        """Ensure all links in HTML have proper attributes for PDF clickability"""
        # Add target and rel attributes to all links
        def enhance_link(match):
            opening_tag = match.group(1)
            link_content = match.group(2)

            # Extract href
            href_match = re.search(r'href=["\']([^"\']+)["\']', opening_tag)
            if not href_match:
                return match.group(0)  # Return original if no href found

            href = href_match.group(1)

            # Ensure proper attributes for PDF links
            enhanced_tag = opening_tag
            if 'target=' not in enhanced_tag:
                enhanced_tag = enhanced_tag.replace('>', ' target="_blank">')
            if 'rel=' not in enhanced_tag:
                enhanced_tag = enhanced_tag.replace('>', ' rel="noopener">')

            return f'{enhanced_tag}{link_content}</a>'

        # Process all anchor tags
        html_content = re.sub(r'(<a[^>]*>)(.*?)</a>', enhance_link, html_content, flags=re.DOTALL)

        return html_content

    def _verify_pdf_links(self, pdf_path: str) -> None:
        """Verify that the PDF contains clickable links"""
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                link_count = 0

                for page in pdf_reader.pages:
                    if '/Annots' in page:
                        annots = page['/Annots']
                        for annot in annots:
                            annot_obj = annot.get_object()
                            if '/A' in annot_obj and '/URI' in annot_obj['/A']:
                                link_count += 1

                if link_count > 0:
                    print(f"PDF contains {link_count} clickable links")
                else:
                    print(" Warning: No clickable links detected in PDF")

        except ImportError:
            print("Install PyPDF2 to verify links: pip install PyPDF2")
        except Exception as e:
            print(f"Could not verify PDF links: {e}")

    def _generate_link_optimized_css(self) -> str:
        """Generate CSS specifically optimized for clickable links in PDF"""
        return """
        @page {
            margin: 2cm;
            size: A4;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333333;
            margin: 0;
            padding: 0;
            background-color: white;
            font-size: 12pt;
        }

        .document-container {
            max-width: none;
            margin: 0 auto;
            padding: 0;
        }

        /* CRITICAL: Explicit link styling for PDF preservation */
        a {
            color: #0066cc;
            text-decoration: underline;
            text-decoration-thickness: 1px;
            text-underline-offset: 2px;
            font-weight: normal;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }

        a:link {
            color: #0066cc;
        }

        a:visited {
            color: #551a8b;
        }

        a:hover {
            color: #004499;
        }

        /* Force link visibility in print */
        @media print {
            a {
                color: #0066cc !important;
                text-decoration: underline !important;
            }

            a:link {
                color: #0066cc !important;
            }

            a:visited {
                color: #551a8b !important;
            }
        }

        /* Headings */
        h1 {
            color: #1a1a1a;
            font-size: 28pt;
            font-weight: bold;
            margin: 24pt 0 16pt 0;
            padding-bottom: 8pt;
            border-bottom: 2pt solid #0066cc;
            page-break-after: avoid;
        }

        h2 {
            color: #1a1a1a;
            font-size: 22pt;
            font-weight: bold;
            margin: 20pt 0 12pt 0;
            padding-bottom: 4pt;
            border-bottom: 1pt solid #cccccc;
            page-break-after: avoid;
        }

        h3 {
            color: #1a1a1a;
            font-size: 18pt;
            font-weight: bold;
            margin: 16pt 0 8pt 0;
            page-break-after: avoid;
        }

        h4 {
            color: #1a1a1a;
            font-size: 16pt;
            font-weight: bold;
            margin: 12pt 0 6pt 0;
            page-break-after: avoid;
        }

        /* Paragraphs */
        p {
            margin: 0 0 12pt 0;
            orphans: 2;
            widows: 2;
        }

        /* Lists */
        ul, ol {
            margin: 12pt 0;
            padding-left: 24pt;
        }

        li {
            margin-bottom: 6pt;
        }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 16pt 0;
            page-break-inside: avoid;
        }

        th {
            background-color: #f5f5f5;
            color: #333333;
            font-weight: bold;
            padding: 8pt 12pt;
            text-align: left;
            border: 1pt solid #cccccc;
        }

        td {
            padding: 8pt 12pt;
            border: 1pt solid #cccccc;
            vertical-align: top;
        }

        tr:nth-child(even) {
            background-color: #fafafa;
        }

        /* Code */
        code {
            background-color: #f5f5f5;
            color: #d73a49;
            padding: 2pt 4pt;
            border-radius: 3pt;
            font-family: 'Courier New', Courier, monospace;
            font-size: 10pt;
        }

        pre {
            background-color: #f8f8f8;
            color: #333333;
            padding: 12pt;
            border-radius: 4pt;
            margin: 16pt 0;
            font-family: 'Courier New', Courier, monospace;
            font-size: 10pt;
            line-height: 1.4;
            overflow: auto;
            page-break-inside: avoid;
        }

        pre code {
            background: none;
            color: inherit;
            padding: 0;
        }

        /* Blockquotes */
        blockquote {
            border-left: 3pt solid #0066cc;
            padding: 0 0 0 12pt;
            margin: 16pt 0 16pt 12pt;
            color: #666666;
            font-style: italic;
        }

        /* Horizontal rules */
        hr {
            border: none;
            border-top: 1pt solid #cccccc;
            margin: 24pt 0;
        }

        /* Strong and emphasis */
        strong, b {
            font-weight: bold;
            color: #1a1a1a;
        }

        em, i {
            font-style: italic;
        }
        """

    def convert(self, markdown_content: str, output_path: str,
                custom_css: Optional[str] = None) -> bool:
        """
        Convert markdown to PDF with clickable links using WeasyPrint

        Args:
            markdown_content: The markdown content to convert
            output_path: Path where the PDF should be saved
            custom_css: Optional custom CSS to override default styling

        Returns:
            bool: True if conversion successful, False otherwise
        """
        return self.convert_weasyprint_with_links(markdown_content, output_path, custom_css)