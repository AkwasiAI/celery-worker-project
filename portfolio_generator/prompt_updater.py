#!/usr/bin/env python3
"""
Prompt Updater - A utility to update prompt templates based on feedback.
This module allows for systematic updates to prompt templates with version tracking.
"""

import os
import re
import json
import datetime
from pathlib import Path
import shutil

# Default path to the prompts config file
DEFAULT_PROMPTS_PATH = Path(__file__).parent / "prompts_config.py"

# Prompt template names (from prompts_config.py)
PROMPT_TEMPLATES = [
    "REPORT_PLANNER_INSTRUCTIONS",
    "QUERY_WRITER_INSTRUCTIONS",
    "SECTION_WRITER_INSTRUCTIONS",
    "FINAL_SECTION_WRITER_INSTRUCTIONS",
    "INVESTMENT_PORTFOLIO_PROMPT"
]

def backup_prompts_file(prompts_path=DEFAULT_PROMPTS_PATH):
    """Create a backup of the prompts config file with a timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = prompts_path.parent / f"prompts_config_backup_{timestamp}.py"
    
    shutil.copy2(prompts_path, backup_path)
    print(f"Created backup at: {backup_path}")
    return backup_path

def extract_prompt_template(content, template_name):
    """Extract a specific prompt template from the file content."""
    pattern = rf"{template_name}\s*=\s*'''(.*?)'''"
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        return None
    
    return match.group(1)

def update_prompt_template(content, template_name, new_template):
    """Update a specific prompt template in the file content."""
    pattern = rf"({template_name}\s*=\s*''')(.*?)(''')"
    replacement = f"\\1{new_template}\\3"
    
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Add version comment if not already present
    if f"# Updated {template_name}" not in new_content:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        version_comment = f"\n# Updated {template_name} on {timestamp}\n"
        new_content = new_content.replace(f"{template_name} = '''", 
                                       f"{version_comment}{template_name} = '''")
    
    return new_content

def apply_feedback(template_name, feedback, prompts_path=DEFAULT_PROMPTS_PATH):
    """
    Apply feedback to a specific prompt template.
    
    Args:
        template_name: Name of the template to update (must match one in PROMPT_TEMPLATES)
        feedback: Dictionary with feedback instructions on what to update
            - 'add': Text to add to the template
            - 'remove': Text or pattern to remove from the template
            - 'replace': Dictionary with 'old' and 'new' text pairs
            - 'complete_replacement': Complete new template text (overrides other options)
        prompts_path: Path to prompts_config.py file
        
    Returns:
        True if update was successful, False otherwise
    """
    if template_name not in PROMPT_TEMPLATES:
        print(f"Error: Unknown template name '{template_name}'")
        print(f"Valid templates: {', '.join(PROMPT_TEMPLATES)}")
        return False
    
    # Create a backup first
    backup_prompts_file(prompts_path)
    
    # Read the current prompts file
    with open(prompts_path, 'r') as f:
        content = f.read()
    
    # Extract the target template
    template = extract_prompt_template(content, template_name)
    if template is None:
        print(f"Error: Could not find template '{template_name}' in the file")
        return False
    
    # Apply feedback
    new_template = template
    
    # Complete replacement trumps all other options
    if 'complete_replacement' in feedback:
        new_template = feedback['complete_replacement']
    else:
        # Apply replacements
        if 'replace' in feedback:
            for old_text, new_text in feedback['replace'].items():
                new_template = new_template.replace(old_text, new_text)
        
        # Remove text or patterns
        if 'remove' in feedback:
            removes = feedback['remove']
            if not isinstance(removes, list):
                removes = [removes]
                
            for remove_text in removes:
                new_template = new_template.replace(remove_text, '')
        
        # Add text (usually at specific locations marked with comments)
        if 'add' in feedback:
            for marker, text_to_add in feedback['add'].items():
                if marker in new_template:
                    new_template = new_template.replace(marker, f"{marker}\n{text_to_add}")
                else:
                    # If no marker, append to the end before the response section
                    if '<Responses Required>' in new_template:
                        new_template = new_template.replace('<Responses Required>', 
                                                          f"{text_to_add}\n\n<Responses Required>")
                    else:
                        new_template += f"\n{text_to_add}\n"
    
    # Update the template in the file content
    updated_content = update_prompt_template(content, template_name, new_template)
    
    # Write the updated content back to the file
    with open(prompts_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated template '{template_name}'")
    return True

def create_feedback_from_log(log_file_path):
    """
    Extract feedback from a log file.
    Looks for sections in the format:
    
    PROMPT_FEEDBACK: TEMPLATE_NAME
    {json feedback object}
    END_PROMPT_FEEDBACK
    
    Returns a dictionary of template names and their feedback.
    """
    feedback_dict = {}
    
    with open(log_file_path, 'r') as f:
        content = f.read()
    
    # Find all feedback sections
    pattern = r"PROMPT_FEEDBACK: (\w+)\n(.*?)\nEND_PROMPT_FEEDBACK"
    matches = re.findall(pattern, content, re.DOTALL)
    
    for template_name, feedback_json in matches:
        try:
            feedback = json.loads(feedback_json)
            feedback_dict[template_name] = feedback
        except json.JSONDecodeError:
            print(f"Error parsing feedback JSON for {template_name}")
    
    return feedback_dict

def list_available_templates(prompts_path=DEFAULT_PROMPTS_PATH):
    """List all available prompt templates in the file with their descriptions."""
    with open(prompts_path, 'r') as f:
        content = f.read()
    
    print("Available prompt templates:")
    for template in PROMPT_TEMPLATES:
        template_text = extract_prompt_template(content, template)
        if template_text:
            # Extract first non-empty line as description
            first_line = next((line for line in template_text.split('\n') if line.strip()), "")
            print(f"- {template}: {first_line}")
        else:
            print(f"- {template}: [Not found in file]")

def show_template(template_name, prompts_path=DEFAULT_PROMPTS_PATH):
    """Display a specific template."""
    if template_name not in PROMPT_TEMPLATES:
        print(f"Error: Unknown template name '{template_name}'")
        print(f"Valid templates: {', '.join(PROMPT_TEMPLATES)}")
        return
    
    with open(prompts_path, 'r') as f:
        content = f.read()
    
    template = extract_prompt_template(content, template_name)
    if template:
        print(f"=== {template_name} ===")
        print(template)
    else:
        print(f"Template '{template_name}' not found in file")

def main():
    """Command-line interface for the prompt updater."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update prompt templates based on feedback")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List templates command
    list_parser = subparsers.add_parser("list", help="List available templates")
    
    # Show template command
    show_parser = subparsers.add_parser("show", help="Show a specific template")
    show_parser.add_argument("template", help="Template name to show")
    
    # Update template command
    update_parser = subparsers.add_parser("update", help="Update a template with feedback")
    update_parser.add_argument("template", help="Template name to update")
    update_parser.add_argument("--feedback", "-f", required=True,
                              help="JSON file with feedback or JSON string")
    
    # Process feedback log command
    process_parser = subparsers.add_parser("process-log", help="Process a log file with feedback")
    process_parser.add_argument("log_file", help="Path to the log file")
    
    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create a backup of prompts file")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_available_templates()
    
    elif args.command == "show":
        show_template(args.template)
    
    elif args.command == "update":
        # Determine if feedback is a file or a JSON string
        feedback = None
        if os.path.exists(args.feedback):
            with open(args.feedback, 'r') as f:
                feedback = json.load(f)
        else:
            try:
                feedback = json.loads(args.feedback)
            except json.JSONDecodeError:
                print("Error: Feedback must be a valid JSON file or string")
                return
        
        apply_feedback(args.template, feedback)
    
    elif args.command == "process-log":
        if not os.path.exists(args.log_file):
            print(f"Error: Log file '{args.log_file}' not found")
            return
        
        feedback_dict = create_feedback_from_log(args.log_file)
        for template, feedback in feedback_dict.items():
            print(f"Applying feedback to {template}...")
            apply_feedback(template, feedback)
    
    elif args.command == "backup":
        backup_path = backup_prompts_file()
        print(f"Backup created at: {backup_path}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
