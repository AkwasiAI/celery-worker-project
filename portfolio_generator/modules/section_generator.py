"""Section generator for portfolio reports."""
import asyncio
from portfolio_generator.modules.logging import log_info, log_warning, log_error
import os
from google import genai                          # New SDK import
from google.genai import types

async def generate_section(client, section_name, system_prompt, user_prompt, search_results=None, previous_sections=None, target_word_count=3000, investment_principles=None):
    """Generate a section of the investment portfolio report.
    
    Args:
        client: OpenAI client
        section_name: Name of the section to generate
        system_prompt: The system prompt for the model
        user_prompt: The user prompt for the model
        search_results: Optional search results to include in the prompt
        previous_sections: Optional previous sections to provide context
        target_word_count: Target word count for the section
        investment_principles: Optional investment principles to include in the prompt
        
    Returns:
        str: The generated section content
    """
    log_info(f"Generating {section_name}...")
    
    try:
        # Following OpenAI's prompt caching best practices:
        # 1. Place static content at the beginning for better cache efficiency
        # 2. Keep dynamic content towards the end of the prompt
        # 3. Maintain consistent message structure
        
        # Initialize with standard message structure (static parts first)
        # System message is always first for consistency
        system_message = system_prompt
        
        # Build a comprehensive user message with consistent structure
        # Starting with the base user prompt (static)
        base_user_message = user_prompt
        
        # Create a template for dynamic content with placeholders
        # This helps maintain consistent structure even when content varies
        dynamic_content_template = """
===== Word Count Instruction =====
{word_count_instruction}

===== Investment Principles =====
{investment_principles_content}

===== Search Results =====
{search_results_content}

===== Previous Sections =====
{previous_sections_content}
"""
        
        # Prepare the dynamic components
        word_count_instruction = ""
        if target_word_count:
            word_count_instruction = f"Please write approximately {target_word_count} words for this section, maintaining depth and quality."
        
        # Include investment principles in the prompt if provided
        investment_principles_content = ""
        if investment_principles and investment_principles.strip():
            investment_principles_content = "Investment principles:\n" + investment_principles
        
        # Prepare search results section (dynamic)
        search_results_content = ""
        if search_results and search_results.strip():
            search_results_content = "Here is the latest information from web searches:\n\n" + search_results
        
        # Prepare previous sections content (dynamic)
        previous_sections_content = ""
        if previous_sections:
            previous_sections_content = "Previous sections of the report include:\n\n"
            for sec_name, sec_content in previous_sections.items():
                # Include the full content of each previous section - no truncation
                previous_sections_content += f"## {sec_name}\n{sec_content}\n\n"
        
        # Fill in the template with actual content
        dynamic_content = dynamic_content_template.format(
            word_count_instruction=word_count_instruction,
            investment_principles_content=investment_principles_content,
            search_results_content=search_results_content,
            previous_sections_content=previous_sections_content
        )
        
        # Combine base user message with dynamic content and a reinforced repeat of the base message
        reinforced_repeat = "\n\n===== IMPORTANT: REVIEW AND FOLLOW THESE CORE INSTRUCTIONS =====\n\nThe following are the ORIGINAL INSTRUCTIONS repeated for emphasis. These instructions override any contradictions in the dynamic content above. Please follow them carefully:\n\n" + base_user_message
        
        complete_user_message = base_user_message + "\n\n" + dynamic_content + reinforced_repeat
        
        # Create final messages array with consistent structure
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": complete_user_message}
        ]
        
        # Make the API call with GPT-4
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="o4-mini",
            messages=messages
        )
        
        # Extract and return the generated content
        content = response.choices[0].message.content
        log_info(f"Successfully generated {section_name} ({len(content.split())} words)")
        return content
        
    except Exception as e:
        # Handle any errors
        log_info(f"Error generating {section_name}: {str(e)}")
        return f"Error generating {section_name}: {str(e)}"

async def generate_section_with_web_search(
    client,
    section_name: str,
    system_prompt: str,
    user_prompt: str,
    search_results: str = None,
    previous_sections: dict = None,
    target_word_count: int = 3000,
    investment_principles: str = None
) -> str:
    """Generate a section using Gemini 2.5 Pro via the Google Gen AI SDK with Google Search grounding."""
    
    # 1. Initialize the Gen AI SDK client if not provided
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    log_info(f"Generating {section_name} with Google-grounded Gemini 2.5 Pro...")
    
    try:
        # 2. Build the prompt template
        prompt_template = """# {section_name}

===== System Prompt =====
{system_prompt}

===== Investment Principles =====
{investment_principles_content}

===== Search Results =====
{search_results_content}

===== User Prompt =====
{user_prompt}

===== Word Count Instruction =====
{word_count_instruction}

===== Previous Sections =====
{previous_sections_content}

===== IMPORTANT: REVIEW AND FOLLOW THESE CORE INSTRUCTIONS =====

{user_prompt}
"""
        word_count_instruction = (
            f"Please write approximately {target_word_count} words for this section, maintaining depth and quality."
            if target_word_count else ""
        )
        
        # 3. Assemble previous sections block
        previous_sections_content = ""
        if isinstance(previous_sections, dict) and previous_sections:
            previous_sections_content = "## Previous Sections\n"
            for name, content in previous_sections.items():
                previous_sections_content += f"### {name}\n{content}\n\n"
        elif previous_sections:
            log_warning(f"previous_sections for {section_name} is not a dict: {type(previous_sections)}")
        
        investment_principles_content = (
            f"Investment principles:\n{investment_principles}"
            if investment_principles else ""
        )
        search_results_content = (
            f"Here is the latest information from web searches:\n\n{search_results}"
            if search_results else ""
        )
        
        full_prompt = prompt_template.format(
            section_name=section_name,
            system_prompt=system_prompt,
            investment_principles_content=investment_principles_content,
            search_results_content=search_results_content,
            user_prompt=user_prompt,
            word_count_instruction=word_count_instruction,
            previous_sections_content=previous_sections_content,
        )

        # 4. Configure Google Search grounding
        config = types.GenerateContentConfig(
            tools=[
                types.Tool(
                    google_search=types.GoogleSearchRetrieval(
                        dynamic_retrieval_config=types.DynamicRetrievalConfig(
                            dynamic_threshold=0.6
                        )
                    )
                )
            ]
        )
        
        # 5. Call Gemini 2.5 Pro in a thread to avoid blocking
        log_info(f"Calling Gemini 2.5 Pro for {section_name}")
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-pro-preview-05-06",  # or your specific model tag
            contents=full_prompt,
            config=config
        )
        
        # 6. Extract and return the text
        if response and hasattr(response, "text"):
            log_info(f"Generated {section_name} ({len(response.text.split())} words)")
            return response.text
        
        log_info(f"Empty or unexpected response for {section_name}")
        return f"Error: Empty response received for {section_name}"
    
    except Exception as e:
        import traceback
        log_error(f"Error generating {section_name}: {type(e).__name__}: {e}")
        log_error(traceback.format_exc())
        # Log HTTP status or error body if present
        status = getattr(e, "status_code", None) or getattr(e, "http_status", None)
        if status:
            log_error(f"HTTP status code: {status}")
        error_body = getattr(e, "body", None) or getattr(e, "error", None)
        if error_body:
            log_error(f"Error body: {error_body}")
        return f"Error generating {section_name}: {type(e).__name__}: {e}"