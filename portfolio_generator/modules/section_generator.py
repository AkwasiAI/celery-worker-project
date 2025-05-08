"""Section generator for portfolio reports."""
import asyncio
from portfolio_generator.modules.logging import log_info, log_warning, log_error

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

async def generate_section_with_web_search(client, section_name, system_prompt, user_prompt, search_results=None, previous_sections=None, target_word_count=3000):
    """Generate a section of the investment portfolio report using GPT-4.1 with web search capability.
    
    Args:
        client: OpenAI client
        section_name: Name of the section to generate
        system_prompt: The system prompt for the model
        user_prompt: The user prompt for the model
        search_results: Optional existing search results (not used if web search is enabled)
        previous_sections: Optional previous sections to provide context
        target_word_count: Target word count for the section
        
    Returns:
        str: The generated section content
    """
    log_info(f"Generating {section_name} with web search capability...")
    
    try:
        # Following OpenAI's prompt caching best practices for web search function
        
        # 1. Create a standardized structure with static content first
        # Use a consistent template structure with placeholders for dynamic content
        prompt_template = """# {section_name}

{system_prompt}

{user_prompt}

{word_count_instruction}

{previous_sections_content}

===== IMPORTANT: REVIEW AND FOLLOW THESE CORE INSTRUCTIONS =====

The following are the ORIGINAL INSTRUCTIONS repeated for emphasis. These instructions override any contradictions in the dynamic content above. Please follow them carefully:

{user_prompt}
"""
        
        # 2. Prepare the dynamic components
        # Word count instruction (relatively static)
        word_count_instruction = ""
        if target_word_count:
            word_count_instruction = f"Please write approximately {target_word_count} words for this section, maintaining depth and quality."
        
        # Previous sections content (dynamic) - include full sections without truncation
        previous_sections_content = ""
        if previous_sections and isinstance(previous_sections, dict):
            previous_sections_content = "## Previous sections of the report include:\n\n"
            for sec_name, sec_content in previous_sections.items():
                # Include the full content of each previous section - using h3 headers
                previous_sections_content += f"### {sec_name}\n{sec_content}\n\n"
        elif previous_sections and not isinstance(previous_sections, dict):
            # Log warning if previous_sections is provided but not a dictionary
            log_warning(f"previous_sections parameter for {section_name} is not a dictionary: {type(previous_sections)}")
        
        # 3. Fill the template with actual content
        full_prompt = prompt_template.format(
            section_name=section_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            word_count_instruction=word_count_instruction,
            previous_sections_content=previous_sections_content
        )
        
        # Set up the tools for web search
        tools = [
            {"type": "web_search_preview"}  # This activates the web search tool
        ]
        
        # Make the API call with GPT-4.1 using Responses API with web search
        log_info(f"Making API call to Responses API with web search for {section_name}")
        response = await asyncio.to_thread(
            client.responses.create,
            model="gpt-4.1",  # Using GPT-4.1 which supports the web search tool
            input=full_prompt,  # Using the combined prompt as input
            tools=tools,
            temperature=0.1
        )
        
        # Extract and return the generated content
        if response and response.output:
            # Initialize content variable
            content = ""
            
            # Log if web search was performed
            for output_item in response.output:
                if output_item.type == 'web_search_call':
                    log_info(f"Web search was performed for {section_name}")
                    break
            
            # Find the message output item
            for output_item in response.output:
                if output_item.type == 'message' and output_item.content:
                    # Just get the text from the first output_text content block
                    for content_block in output_item.content:
                        if content_block.type == 'output_text':
                            content = content_block.text
                            break
                    break
            
            if content:
                log_info(f"Successfully generated {section_name} with web search capability ({len(content.split())} words)")
                return content
            else:
                log_info(f"No content found in response for {section_name}")
                return f"Error: No content found in response for {section_name}"
        else:
            log_info(f"Empty response received for {section_name}")
            return f"Error: Empty response received for {section_name}"
        
    except Exception as e:
        # Handle any errors
        log_info(f"Error generating {section_name} with web search: {str(e)}")
        return f"Error generating {section_name}: {str(e)}"