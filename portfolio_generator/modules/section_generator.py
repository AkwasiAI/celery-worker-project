"""Section generator for portfolio reports."""
import asyncio
from portfolio_generator.modules.logging import log_info, log_warning, log_error

async def generate_section(client, section_name, system_prompt, user_prompt, search_results=None, previous_sections=None, target_word_count=3000):
    """Generate a section of the investment portfolio report.
    
    Args:
        client: OpenAI client
        section_name: Name of the section to generate
        system_prompt: The system prompt for the model
        user_prompt: The user prompt for the model
        search_results: Optional search results to include in the prompt
        previous_sections: Optional previous sections to provide context
        target_word_count: Target word count for the section
        
    Returns:
        str: The generated section content
    """
    log_info(f"Generating {section_name}...")
    
    try:
        # Create messages for the API call
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Add web search results if available
        if search_results and search_results.strip():
            messages.append({"role": "user", "content": "Here is the latest information from web searches:\n\n" + search_results})
        
        # Add previous sections' summaries for context if available
        if previous_sections:
            context_message = "Previous sections of the report include:\n\n"
            for sec_name, sec_content in previous_sections.items():
                # Only include a brief summary to keep the context concise
                summary = sec_content[:500] + "..." if len(sec_content) > 500 else sec_content
                context_message += f"## {sec_name}\n{summary}\n\n"
            messages.append({"role": "user", "content": context_message})
        
        # Explicitly mention word count in the final request
        if target_word_count:
            word_count_msg = f"Please write approximately {target_word_count} words for this section, maintaining depth and quality."
            messages.append({"role": "user", "content": word_count_msg})
        
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
        # Combine all inputs into a single comprehensive prompt
        full_prompt = f"""# {section_name}

{system_prompt}

{user_prompt}
"""
        
        # Add previous sections' summaries for context if available
        # Ensure previous_sections is a dictionary to avoid 'int' object has no attribute 'items' error
        if previous_sections and isinstance(previous_sections, dict):
            sections_context = "\n\n## Previous sections of the report include:\n\n"
            for sec_name, sec_content in previous_sections.items():
                # Include the full content of each previous section
                sections_context += f"### {sec_name}\n{sec_content}\n\n"
            full_prompt += sections_context
        elif previous_sections and not isinstance(previous_sections, dict):
            # Log warning if previous_sections is provided but not a dictionary
            log_warning(f"previous_sections parameter for {section_name} is not a dictionary: {type(previous_sections)}")
        
        # Explicitly mention word count in the final request
        if target_word_count:
            full_prompt += f"\n\nPlease write approximately {target_word_count} words for this section, maintaining depth and quality."
        
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