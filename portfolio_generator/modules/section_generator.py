"""Section generator for portfolio reports."""
import asyncio
from portfolio_generator.modules.logging import log_info

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
            model="gpt-4-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=4000
        )
        
        # Extract and return the generated content
        content = response.choices[0].message.content
        log_info(f"Successfully generated {section_name} ({len(content.split())} words)")
        return content
        
    except Exception as e:
        # Handle any errors
        log_info(f"Error generating {section_name}: {str(e)}")
        return f"Error generating {section_name}: {str(e)}"
