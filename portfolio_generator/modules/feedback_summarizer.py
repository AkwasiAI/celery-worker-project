import os
import re
from typing import List, Dict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

class FeedbackSummarizer:
    def __init__(self, model_name: str = "gemini-2.5-flash-preview-05-20"):
        self.llm = ChatGoogleGenerativeAI(model=model_name)
        
        # Define the templates just once
        self.chat_template = ChatPromptTemplate.from_template(
            """This is a conversation transcript between a chatbot and a person.
Summarize the key takeaways from this conversation in exactly 50 words.
Focus on: what the person was asking about, main topics discussed,
any important information or advice, and significant outcomes or decisions.

Conversation transcript:
{content}

Key takeaways summary (50 words):"""
        )
        self.generic_template = ChatPromptTemplate.from_template(
            """Please provide a concise 50-word summary of the following {feedback_type} content.
Focus on the key points, main topics, and important information mentioned.
Keep it exactly around 50 words and make it informative and clear.

Content:
{content}

Summary (50 words):"""
        )

    def parse_feedback_sections(self, text: str) -> List[Dict[str, str]]:
        feedback_sections = []
        patterns = [
            (r'=====VideoFeedback=====(.*?)(?=====\w+Feedback=====|$)', 'VideoFeedback'),
            (r'=====PortfolioFeedback=====(.*?)(?=====\w+[A-Z][a-z]+=====|$)', 'PortfolioFeedback'),
            (r'=====ManualUpload=====(.*?)(?=====\w+[A-Z][a-z]+=====|$)', 'ManualUpload'),
            (r'=====ChatHistory=====(.*?)(?=====\w+[A-Z][a-z]+=====|$)', 'ChatHistory')
        ]
        for pattern, feedback_type in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                content = match.strip()
                if content:
                    feedback_sections.append({'type': feedback_type, 'content': content})
        return feedback_sections

    def extract_reference_info(self, content: str, feedback_type: str) -> str:
        if feedback_type == 'VideoFeedback':
            video_match = re.search(r'Context from latest video: ([^\s]+)', content)
            return f"Video: {video_match.group(1)}" if video_match else "Video: Reuters screen recording"
        elif feedback_type == 'PortfolioFeedback':
            date_match = re.search(r'Report Date: ([^\n]+)', content)
            return f"Portfolio Report: {date_match.group(1)}" if date_match else "Portfolio Report"
        elif feedback_type == 'ManualUpload':
            file_type_match = re.search(r'File Type: ([^\n]+)', content)
            return f"Manual Upload: {file_type_match.group(1)} file" if file_type_match else "Manual Upload"
        elif feedback_type == 'ChatHistory':
            return "Chat History Transcript"
        return f"{feedback_type} Content"

    def has_meaningful_content(self, content: str, feedback_type: str) -> bool:
        content_clean = content.strip()
        if len(content_clean) < 30:
            return False
        if feedback_type == 'PortfolioFeedback':
            lines = [line.strip() for line in content_clean.split('\n') if line.strip()]
            if len(lines) <= 1 and any(re.match(r'^Report Date:', line) for line in lines):
                return False
            meaningful_lines = [line for line in lines if not re.match(r'^(Report Date:|Type:|File Type:)', line)]
            if not meaningful_lines:
                return False
        elif feedback_type == 'ManualUpload':
            lines = [line.strip() for line in content_clean.split('\n') if line.strip()]
            if len(lines) <= 3 and all(re.match(r'^(Type:|File Type:)', line) for line in lines):
                return False
            meaningful_lines = [line for line in lines if not re.match(r'^(Type:|File Type:)', line)]
            if not meaningful_lines or all(len(line) < 20 for line in meaningful_lines):
                return False
        elif feedback_type == 'VideoFeedback':
            lines = [line.strip() for line in content_clean.split('\n') if line.strip()]
            meaningful_lines = [line for line in lines if not re.match(r'^(Context from latest video:|====)', line)]
            if len(meaningful_lines) < 3:
                return False
        elif feedback_type == 'ChatHistory':
            user_messages = content_clean.count('[user -')
            assistant_messages = content_clean.count('[assistant -')
            if user_messages == 0 and assistant_messages == 0:
                return False
            if user_messages + assistant_messages < 2:
                return False
        return True

    def generate_summary(self, content: str, feedback_type: str) -> str:
        try:
            if feedback_type == 'ChatHistory':
                chain = self.chat_template | self.llm
                result = chain.invoke({"content": content})
            else:
                chain = self.generic_template | self.llm
                result = chain.invoke({"content": content, "feedback_type": feedback_type})
            return result.content.strip()
        except Exception as e:
            return f"Error generating summary: {str(e)}"

    def process_feedback_text(self, input_text: str) -> str:
        feedback_sections = self.parse_feedback_sections(input_text)
        if not feedback_sections:
            return "No feedback sections found in the input text."
        meaningful_sections = [
            section for section in feedback_sections
            if self.has_meaningful_content(section['content'], section['type'])
        ]
        if not meaningful_sections:
            return "No meaningful feedback content found to summarize."
        markdown_output = "# Feedback Summaries\n\n"
        for i, section in enumerate(meaningful_sections, 1):
            feedback_type = section['type']
            content = section['content']
            reference = self.extract_reference_info(content, feedback_type)
            summary = self.generate_summary(content, feedback_type)
            markdown_output += f"## {i}. {feedback_type}\n\n"
            markdown_output += f"**Summary:** {summary}\n\n"
            markdown_output += f"**Reference:** {reference}\n\n"
            markdown_output += "---\n\n"
        return markdown_output
