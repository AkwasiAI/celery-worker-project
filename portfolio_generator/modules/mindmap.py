import os
import re
import uuid
import json
import logging
from collections import Counter
from typing import Dict, List, Any, Optional
import re
import string

# Make sure you have these installed:
# pip install pypdf langchain-google-genai langchain

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser # To get string output from LLM
from langchain_core.runnables import RunnableLambda # To integrate custom Python functions into a chain

# --- Logger Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Clear existing handlers to prevent duplicate output if run multiple times
if logger.handlers:
    for handler in logger.handlers:
        logger.removeHandler(handler)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
# --------------------

API_KEY = os.environ.get("GEMINI_API_KEY")

class MindmapGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm = None
        self.configure_llm()

    def configure_llm(self) -> bool:
        """Configure LangChain's ChatGoogleGenerativeAI with API key and error handling."""
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            logger.error("Invalid API key provided.")
            return False

        try:
            os.environ["GOOGLE_API_KEY"] = self.api_key
            
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-05-20", temperature=0.3)

            test_response = self.llm.invoke("Test connection").content
            if test_response:
                logger.info(f"Successfully connected with {self.llm.model}.")
                return True
            else:
                logger.error("LLM test query returned no content.")
                return False

        except Exception as e:
            logger.error(f"Failed to configure LangChain's ChatGoogleGenerativeAI: {e}", exc_info=True)
            return False

    def extract_text_from_pdf(self, pdf_file, page_limit: Optional[int] = None) -> Optional[str]:
        """Extract text content from a PDF file with improved error handling."""
        try:
            from pypdf import PdfReader # Import here to avoid issues if pypdf is not installed
            pdf_reader = PdfReader(pdf_file)
            text = ""
            total_pages = len(pdf_reader.pages)
            pages_to_process = min(page_limit or total_pages, total_pages)

            logger.info(f"Processing {pages_to_process} out of {total_pages} pages.")

            for i, page in enumerate(pdf_reader.pages[:pages_to_process]):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        page_text = self._clean_text(page_text)
                        text += f"--- Page {i+1} ---\n{page_text}\n\n"
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {i+1}: {e}")
                    continue

            return text.strip() if text.strip() else None

        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}", exc_info=True)
            return None

    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\-\.,!?;:()\[\]{}\'/"%]', ' ', text)
        text = ' '.join(text.split())
        return text

    def calculate_text_weights(self, text: str) -> Dict[str, float]:
        """Calculate importance weights for different parts of the text."""
        words = text.lower().split()
        word_freq = Counter(words)

        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}

        filtered_freq = {word: freq for word, freq in word_freq.items()
                        if word not in stop_words and len(word) > 2}

        max_freq = max(filtered_freq.values()) if filtered_freq else 1
        weights = {word: freq / max_freq for word, freq in filtered_freq.items()}

        return weights

    def generate_mindmap_json_lc(self, text: str, include_weights: bool = True) -> Optional[List[Dict[str, Any]]]:
        """
        Generate a mindmap in JSON format using LangChain components.
        This now focuses on clean, unnumbered output without explicit citations.
        """
        if not self.llm:
            logger.error("LLM not configured properly.")
            return None

        try:
            weights = self.calculate_text_weights(text) if include_weights else {}
            top_terms = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:20]

            max_chars = 100000 
            truncated_text = text
            if len(text) > max_chars:
                truncated_text = text[:max_chars] + "...\n[Text truncated for processing]"
                logger.warning(f"Input text truncated to {max_chars} characters.")

            weight_info = ""
            if include_weights and top_terms:
                weight_info = f"""
Key terms identified (with importance weights):
{', '.join([f"{term}({weight:.2f})" for term, weight in top_terms[:10]])}

Please consider these high-weight terms as particularly important when creating the mindmap.
"""

            mindmap_prompt = PromptTemplate.from_template(f"""
Create a highly concise and hierarchical markdown mindmap from the following text.
Focus on the main concepts, key points, and their relationships.
{weight_info}

Use this exact format with weights:
# Single Main Topic (This is the central idea for the entire document) [weight: 1.0]
## Major Section/Subtopic [weight: 0.9]
### Key Area/Semantic Grouping (e.g., "Red Sea/Hormuz Tensions", "Oil Price Concerns") [weight: 0.8]
- Very concise, atomic point 1 [weight: 0.6]
- Very concise, atomic point 2 [weight: 0.7]
### Another Key Area/Grouping [weight: 0.7]
- Atomic point A [weight: 0.5]
- Atomic point B [weight: 0.55]
## Another Major Section/Subtopic [weight: 0.85]
- Direct concise point [weight: 0.6]

Rules:
1.  **Single Root Node:** Start with ONE single `#` for the main overarching topic of the entire text. All other content branches from this. This will be the central node of the mind map.
2.  **Hierarchy Levels:**
    *   Use `##` for major sections/subtopics.
    *   Use `###` for detailed sections or semantic groupings that logically cluster related atomic points (e.g., "Impact on Oil Markets", "US-China Tariffs").
    *   Use `-` for very concise, atomic bullet points. These should be the most granular pieces of information.
3.  **Conciseness:** Keep all node text (especially bullet points) extremely brief and to the point. Aim for keywords, short phrases, or single sentences only. Aim for a mximum limit of 10 words
4.  **Weights:** Add `[weight: X.X]` after each item, where X.X is a float from 0.0-1.0. Higher weights for more important/central concepts.
5.  **No Numbering:** DO NOT include any numbering (e.g., "1.", "1.1.", "1.1.1.") in the mindmap titles or points.
6.  **No Citations:** DO NOT include any citation URLs or references within the markdown. Focus purely on the summarized content.
7.  **Logical Flow:** Ensure clear logical hierarchy and relationships between topics.

Text to analyze:
{{text}}

Return only the markdown mindmap with weights, no other text.
""")

            mindmap_chain = (
                mindmap_prompt
                | self.llm.bind()
                | StrOutputParser()
                | RunnableLambda(self.parse_markdown_to_json)
            )

            json_output = mindmap_chain.invoke({"text": truncated_text})

            if json_output:
                logger.info("Successfully generated mindmap JSON via LangChain.")
            return json_output

        except Exception as e:
            logger.error(f"Failed to generate mindmap via LangChain: {e}", exc_info=True)
            return None

    def parse_markdown_to_json(self, markdown: str) -> List[Dict]:
        """
        Convert markdown mindmap with weights into JSON format.
        This version correctly handles varying header levels and populates
        semantic types for frontend rendering.
        """
        lines = markdown.strip().splitlines()
        result_nodes = []
        # Stack stores (reference_to_node, markdown_level_of_node)
        stack = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            try:
                node_text_raw = ""
                current_markdown_level = 0
                node_type = "unknown" # Default, will be refined

                # Regex to match headers like '# Title', '## Title', '### Title'
                # and capture the hashes and the text
                hash_match = re.match(r"^(#+)\s(.+)$", line)
                if hash_match:
                    hashes = hash_match.group(1)
                    node_text_raw = hash_match.group(2)
                    current_markdown_level = len(hashes)
                    
                    # Determine semantic type based on markdown level
                    if current_markdown_level == 1:
                        node_type = "root"
                    elif current_markdown_level == 2:
                        node_type = "section"
                    elif current_markdown_level == 3:
                        node_type = "detail_group"
                    else: # For headers beyond ###, classify as a sub-group
                        node_type = "sub_group" 

                # Check for bullet points. Ensure it starts with "- "
                elif line.startswith("- "):
                    node_text_raw = line[2:].strip() # Remove "- "
                    # Bullet points are always children of the last header on the stack.
                    # Their conceptual level is one deeper than their direct parent header.
                    current_markdown_level = (stack[-1][1] + 1) if stack else 1
                    node_type = "detail"
                else:
                    logger.warning(f"Skipping unparseable line {line_num}: '{line}' - Does not match expected markdown header or bullet format.")
                    continue

                title, weight = self._extract_title_and_weight(node_text_raw)
                if not title:
                    logger.warning(f"Skipping line {line_num} due to empty title after parsing: '{line}'")
                    continue

                node = {
                    "id": str(uuid.uuid4()),
                    "text": title,
                    "weight": weight,
                    "children": [],
                    "type": node_type,
                }

                # Manage the stack for hierarchy based on markdown level
                if node_type in ["root", "section", "detail_group", "sub_group"]:
                    # Pop from stack until we find a parent that is at a higher level
                    # than the current node's markdown level.
                    while stack and stack[-1][1] >= current_markdown_level:
                        stack.pop()
                    
                    if stack:
                        # Append to the children of the found parent node
                        stack[-1][0]["children"].append(node)
                    else:
                        # If stack is empty, this is a new top-level node
                        result_nodes.append(node)
                    
                    # Push the current header node onto the stack
                    stack.append((node, current_markdown_level))
                
                elif node_type == "detail": # Bullet point
                    if stack:
                        # Bullet points always append to the children of the current deepest parent (last on stack)
                        stack[-1][0]["children"].append(node)
                    else:
                        # Fallback for bullet points without a parent header on the stack
                        logger.warning(f"Bullet point '{line}' found without a parent header. Appending to main result list.")
                        result_nodes.append(node)

            except Exception as e:
                logger.error(f"Error parsing line {line_num}: '{line}' - {e}", exc_info=True)
                continue
        
        # Post-processing to ensure a single root node as NotebookLM does.
        # If the LLM generates multiple '#' level 1 nodes, create a synthetic root.
        final_output = []
        if len(result_nodes) > 1:
            # Create a synthetic root. A good generic name can be "Document Summary"
            # or try to infer from the text (e.g., first top-level node's text as a starting point).
            # For robustness, using a fixed generic title is safest if the first header isn't always ideal.
            synthetic_root_text = "Overall Document Summary" 
            
            synthetic_root = {
                "id": str(uuid.uuid4()),
                "text": synthetic_root_text,
                "weight": 1.0, # Assign highest weight to the overall summary node
                "children": result_nodes, # All original top-level nodes become children
                "type": "root",
            }
            final_output = [synthetic_root]
        elif result_nodes:
            # If there's only one top-level node, ensure its type is explicitly "root"
            if result_nodes[0].get("type") != "root":
                result_nodes[0]["type"] = "root"
            final_output = result_nodes
        
        return final_output

    def _extract_title_and_weight(self, text: str) -> (str, float):
        """Extract title and weight from text like 'Title [weight: 0.8]' and remove numbering."""
        title = text.strip()
        weight = 0.5  # Default weight

        # 1. Extract and remove weight
        # Use re.DOTALL to allow the dot to match newlines if somehow present, though unlikely here
        weight_pattern = r'\[weight:\s*([\d.]+?)\]'
        weight_match = re.search(weight_pattern, title, re.DOTALL)
        if weight_match:
            try:
                weight = float(weight_match.group(1))
            except ValueError:
                logger.warning(f"Could not convert weight '{weight_match.group(1)}' to float. Using default.")
            title = re.sub(weight_pattern, '', title).strip()

        # 2. Remove any numbering (e.g., "1. ", "1.1. ", "1.1.1. ") that LLM might still include
        # The prompt strongly discourages this, but this is a fallback for robustness.
        title = re.sub(r'^\d+(\.\d+)*\.\s*', '', title).strip()

        return title, weight

    def save_json(self, data: List[Dict], filename: str = "mindmap.json"):
        """Save JSON data to a file with metadata."""
        try:
            output_data = {
                "metadata": {
                    "total_nodes": self.count_nodes(data),
                    "generated_by": "LangChain-Powered Mindmap Generator",
                    "version": "4.0" # Updated version number
                },
                "mindmap": data
            }

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Mindmap JSON saved to {filename}")

        except Exception as e:
            logger.error(f"Failed to save JSON: {e}", exc_info=True)

    def save_markdown(self, markdown: str, filename: str = "mindmap.md"):
        """Save the raw markdown for review."""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(markdown)
            logger.info(f"Raw Markdown saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save markdown: {e}", exc_info=True)

    def count_nodes(self, data: List[Dict]) -> int:
        """Count total nodes in the mindmap."""
        count = 0
        for item in data:
            count += 1
            if item.get("children"):
                count += self.count_nodes(item["children"])
        return count

    def get_mindmap_stats(self, data: List[Dict]) -> Dict[str, Any]:
        """Get statistics about the generated mindmap."""
        total_nodes = self.count_nodes(data)
        
        max_depth = 0
        weights = []

        def traverse_and_get_stats(nodes: List[Dict], current_depth: int):
            nonlocal max_depth
            for node in nodes:
                max_depth = max(max_depth, current_depth)
                if "weight" in node:
                    weights.append(node["weight"])
                if node.get("children"):
                    traverse_and_get_stats(node["children"], current_depth + 1)

        if data:
            traverse_and_get_stats(data, current_depth=1) # Start from depth 1 for the root node
        else:
            max_depth = 0

        stats = {
            "total_nodes": total_nodes,
            "max_depth": max_depth,
            "average_weight": sum(weights) / len(weights) if weights else 0,
            "weight_distribution": {
                "high": len([w for w in weights if w >= 0.7]),
                "medium": len([w for w in weights if 0.4 <= w < 0.7]),
                "low": len([w for w in weights if w < 0.4])
            }
        }
        return stats
    

import re
import string

def clean_text(text, remove_stopwords=False):
    """
    Cleans the input text by:
    - Lowercasing
    - Removing punctuation
    - Removing numbers
    - Removing extra whitespace
    - Optionally removing stopwords

    Parameters:
        text (str): The text to clean.
        remove_stopwords (bool): Whether to remove English stopwords.

    Returns:
        str: Cleaned text.
    """
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Remove numbers
    text = re.sub(r'\d+', '', text)
    
    # Remove extra whitespace
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)

    # # Remove stopwords (optional)
    # if remove_stopwords:
    #     from nltk.corpus import stopwords
    #     stop_words = set(stopwords.words('english'))
    #     text = ' '.join(word for word in text.split() if word not in stop_words)

    return text


def text_to_mindmap(text_data):
    text_data = clean_text(text_data)
    generator = MindmapGenerator(api_key=API_KEY)

    if generator.llm: # Check if LLM was configured successfully
        # Use the LangChain-powered mindmap generation
        # NOTE: For complex parsing and deep hierarchies, start with a lower max_depth
        # and ensure your prompt is extremely precise.
        # Max tokens from Gemini 2.5 Flash are very high (1M context), but output tokens still have limits.
        # Also, the LLM's ability to consistently generate complex nested JSON/Markdown can vary.
        mindmap_json_data = generator.generate_mindmap_json_lc(text_data)

        if mindmap_json_data:
            print("\n--- Generated Mindmap JSON (LangChain) ---")
            print(json.dumps(mindmap_json_data, indent=2, ensure_ascii=False))


            # Save the JSON and get stats
            generator.save_json(mindmap_json_data, "mindmap_lc.json")
            stats = generator.get_mindmap_stats(mindmap_json_data)
            print("\n--- Mindmap Statistics ---")
            return(json.dumps(mindmap_json_data, indent=2))
        else:
            print("Failed to generate mindmap JSON.")
    else:
        print("LLM initialization failed. Cannot proceed with mindmap generation.")
