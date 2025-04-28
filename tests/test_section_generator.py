"""
Test module for the section_generator module.
This verifies that the section generation functionality works correctly.
"""
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import os
import sys
from portfolio_generator.modules.section_generator import generate_section


class TestSectionGenerator(unittest.TestCase):
    """Test class for section generation functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.client = MagicMock()
        self.section_name = "Test Section"
        self.system_prompt = "You are a test assistant"
        self.user_prompt = "Generate a test section"
    
    @patch('portfolio_generator.modules.section_generator.asyncio.to_thread')
    @patch('portfolio_generator.modules.section_generator.log_info')
    async def test_generate_section_success(self, mock_log_info, mock_to_thread):
        """Test successful section generation."""
        # Mock the response from the OpenAI API
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test section content"
        
        # Setup the async mock
        mock_to_thread.return_value = mock_response
        
        # Call the function
        result = await generate_section(
            self.client,
            self.section_name,
            self.system_prompt,
            self.user_prompt
        )
        
        # Verify the OpenAI API was called with the right parameters
        mock_to_thread.assert_called_once()
        # The first arg to to_thread should be the client.chat.completions.create method
        self.assertEqual(mock_to_thread.call_args[0][0], self.client.chat.completions.create)
        
        # Check other args
        call_kwargs = mock_to_thread.call_args[0][1:]
        self.assertIn('model="gpt-4-turbo"', str(call_kwargs))
        
        # Check the result
        self.assertEqual(result, "Test section content")
        
        # Verify logging was called
        mock_log_info.assert_called()
    
    @patch('portfolio_generator.modules.section_generator.asyncio.to_thread')
    @patch('portfolio_generator.modules.section_generator.log_info')
    async def test_generate_section_with_search_results(self, mock_log_info, mock_to_thread):
        """Test section generation with search results."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test section with search results"
        mock_to_thread.return_value = mock_response
        
        # Call with search results
        search_results = "Sample search result"
        result = await generate_section(
            self.client,
            self.section_name,
            self.system_prompt,
            self.user_prompt,
            search_results=search_results
        )
        
        # Verify the result
        self.assertEqual(result, "Test section with search results")
        
        # Check if search results were included in the messages
        mock_to_thread.assert_called_once()
        call_args = mock_to_thread.call_args[0]
        messages_str = str(call_args)
        self.assertIn("Sample search result", messages_str)
    
    @patch('portfolio_generator.modules.section_generator.asyncio.to_thread')
    @patch('portfolio_generator.modules.section_generator.log_info')
    async def test_generate_section_error_handling(self, mock_log_info, mock_to_thread):
        """Test error handling in section generation."""
        # Mock an exception
        mock_to_thread.side_effect = Exception("Test error")
        
        # Call the function
        result = await generate_section(
            self.client,
            self.section_name,
            self.system_prompt,
            self.user_prompt
        )
        
        # Verify error handling
        self.assertIn("Error generating", result)
        self.assertIn("Test error", result)
        mock_log_info.assert_called_with(f"Error generating {self.section_name}: Test error")


if __name__ == "__main__":
    # Run with asyncio.run for async tests
    unittest.main()
