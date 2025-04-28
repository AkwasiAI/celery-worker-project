"""
Test module for the report_upload module.
This verifies that the Firestore upload functionality works correctly.
"""
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import os
import json
import tempfile
from portfolio_generator.modules.report_upload import upload_report_to_firestore


class TestReportUpload(unittest.TestCase):
    """Test class for Firestore upload functionality."""
    
    @patch('portfolio_generator.modules.report_upload.FirestoreUploader')
    @patch('portfolio_generator.modules.report_upload.asyncio.to_thread')
    @patch('portfolio_generator.modules.report_upload.log_info')
    @patch('portfolio_generator.modules.report_upload.log_success')
    @patch('portfolio_generator.modules.report_upload.FIRESTORE_AVAILABLE', True)
    async def test_upload_report_to_firestore_success(self, mock_log_success, mock_log_info, 
                                                     mock_to_thread, mock_firestore_uploader):
        """Test successful report upload to Firestore."""
        # Mock the FirestoreUploader instance
        mock_uploader_instance = MagicMock()
        mock_firestore_uploader.return_value = mock_uploader_instance
        
        # Set up the last_uploaded_ids attribute with expected values
        mock_uploader_instance.last_uploaded_ids = {
            'reports': 'test_report_id',
            'portfolio_weights': 'test_portfolio_id'
        }
        
        # Mock the successful upload
        mock_to_thread.return_value = (True, True)  # (report_success, weights_success)
        
        # Test data
        report_content = "# Test Report\nThis is a test report."
        portfolio_json = {"test": "portfolio", "data": {"assets": []}}
        
        # Call the function
        result = await upload_report_to_firestore(report_content, portfolio_json)
        
        # Verify the result
        self.assertEqual(result, 'test_report_id')
        
        # Verify the FirestoreUploader was initialized and used correctly
        mock_firestore_uploader.assert_called_once()
        mock_to_thread.assert_called_once()
        
        # Check that the upload_portfolio_data method was called with correct argument types
        call_args = mock_to_thread.call_args[0]
        self.assertEqual(call_args[0], mock_uploader_instance.upload_portfolio_data)
        # The other args should be file paths
        self.assertTrue(isinstance(call_args[1], str))  # report_path
        self.assertTrue(isinstance(call_args[2], str))  # portfolio_path
        
        # Verify logging calls
        mock_log_info.assert_called()
        mock_log_success.assert_called()
    
    @patch('portfolio_generator.modules.report_upload.FirestoreUploader')
    @patch('portfolio_generator.modules.report_upload.asyncio.to_thread')
    @patch('portfolio_generator.modules.report_upload.log_warning')
    @patch('portfolio_generator.modules.report_upload.FIRESTORE_AVAILABLE', True)
    async def test_upload_report_to_firestore_failure(self, mock_log_warning, mock_to_thread, 
                                                     mock_firestore_uploader):
        """Test failed report upload to Firestore."""
        # Mock the FirestoreUploader instance
        mock_uploader_instance = MagicMock()
        mock_firestore_uploader.return_value = mock_uploader_instance
        
        # Mock a failed upload
        mock_to_thread.return_value = (False, False)  # (report_success, weights_success)
        
        # Test data
        report_content = "# Test Report\nThis is a test report."
        portfolio_json = {"test": "portfolio", "data": {"assets": []}}
        
        # Call the function
        result = await upload_report_to_firestore(report_content, portfolio_json)
        
        # Verify the result is None for failure
        self.assertIsNone(result)
        
        # Verify warning was logged
        mock_log_warning.assert_called_with("Failed to upload report to Firestore")
    
    @patch('portfolio_generator.modules.report_upload.log_warning')
    @patch('portfolio_generator.modules.report_upload.FIRESTORE_AVAILABLE', False)
    async def test_upload_report_firestore_unavailable(self, mock_log_warning):
        """Test behavior when Firestore is unavailable."""
        report_content = "# Test Report"
        portfolio_json = {"test": "data"}
        
        result = await upload_report_to_firestore(report_content, portfolio_json)
        
        # Should return None when Firestore is unavailable
        self.assertIsNone(result)
        mock_log_warning.assert_called_with("Firestore upload requested but Firestore is not available")
    
    @patch('portfolio_generator.modules.report_upload.FirestoreUploader')
    @patch('portfolio_generator.modules.report_upload.asyncio.to_thread')
    @patch('portfolio_generator.modules.report_upload.log_error')
    @patch('portfolio_generator.modules.report_upload.FIRESTORE_AVAILABLE', True)
    async def test_upload_report_exception_handling(self, mock_log_error, mock_to_thread, 
                                                   mock_firestore_uploader):
        """Test exception handling during upload."""
        # Mock an exception during upload
        mock_to_thread.side_effect = Exception("Test error")
        
        # Test data
        report_content = "# Test Report"
        portfolio_json = {"test": "data"}
        
        # Call the function
        result = await upload_report_to_firestore(report_content, portfolio_json)
        
        # Verify the result is None for error
        self.assertIsNone(result)
        
        # Verify error was logged
        mock_log_error.assert_called_with("Error uploading to Firestore: Test error")


if __name__ == "__main__":
    unittest.main()
