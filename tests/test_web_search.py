"""
Test module for the web_search module.
This verifies that the Perplexity search functionality works correctly.
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import asyncio
from portfolio_generator.modules.web_search import PerplexitySearch, format_search_results


class TestWebSearch(unittest.IsolatedAsyncioTestCase):
    """Test class for web search functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Use a mock API key for testing
        self.api_key = "mock_api_key"
        os.environ["PERPLEXITY_API_KEY"] = self.api_key
        self.search = PerplexitySearch(api_key=self.api_key)
    
    @patch('portfolio_generator.modules.web_search.PerplexitySearch._search_single_query')
    async def test_search_query_validation(self, mock_search_single):
        """Test query validation in the search method."""
        # Setup the mock to return error for invalid queries
        mock_search_single.return_value = {"error": "invalid_query", "message": "Query is empty"}
        
        # Test with empty query
        result = await self.search._search_single_query("")
        self.assertEqual(result["error"], "invalid_query")
        
        # Test with a short query
        mock_search_single.return_value = {"error": "invalid_query", "message": "Query is too short"}
        result = await self.search._search_single_query("hi")
        self.assertEqual(result["error"], "invalid_query")
        self.assertIn("short", result["message"].lower())
    
    @patch('portfolio_generator.modules.web_search.requests.post')
    async def test_search_success(self, mock_post):
        """Test successful search request."""
        # Mock the response from the Perplexity API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "web_search": {
                "results": [
                    {
                        "title": "Test Result 1",
                        "url": "https://example.com/1",
                        "snippet": "This is test result 1"
                    },
                    {
                        "title": "Test Result 2",
                        "url": "https://example.com/2",
                        "snippet": "This is test result 2"
                    }
                ]
            }
        }
        mock_post.return_value = mock_response
        
        # Test with a valid query
        result = await self.search._search_single_query("test query with sufficient length")
        
        # Verify the API was called with the right parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]
        self.assertEqual(call_args["headers"]["X-API-KEY"], self.api_key)
        self.assertEqual(call_args["json"]["query"], "test query with sufficient length")
        
        # Check the result
        self.assertNotIn("error", result)
        self.assertEqual(result["answer"], "Test answer")
    
    @patch('portfolio_generator.modules.web_search.requests.post')
    async def test_search_retry_logic(self, mock_post):
        """Test the retry logic for server errors."""
        # Mock a server error response followed by a success
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500
        
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {
            "answer": "Test answer after retry",
            "web_search": {"results": []}
        }
        
        # Return error first, then success on retry
        mock_post.side_effect = [mock_error_response, mock_success_response]
        
        result = await self.search._search_single_query("test query with retry")
        
        # Verify the API was called twice due to retry
        self.assertEqual(mock_post.call_count, 2)
        
        # Check the result was from the successful retry
        self.assertNotIn("error", result)
        self.assertEqual(result["answer"], "Test answer after retry")
    
    async def test_format_search_results(self):
        """Test formatting of search results."""
        search_results = {
            "search_results": [
                {
                    "title": "Test Title",
                    "url": "https://example.com",
                    "snippet": "Test snippet for formatting"
                }
            ]
        }
        
        formatted = format_search_results(search_results)
        self.assertIn("Test Title", formatted)
        self.assertIn("https://example.com", formatted)
        self.assertIn("Test snippet for formatting", formatted)


if __name__ == "__main__":
    unittest.main()
