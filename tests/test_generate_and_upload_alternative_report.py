import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

import portfolio_generator.modules.report_upload as report_upload

class TestGenerateAndUploadAlternativeReport(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Force Firestore available
        report_upload.FIRESTORE_AVAILABLE = True

    @patch('portfolio_generator.modules.report_upload.FirestoreUploader')
    async def test_generate_and_upload_alternative_report_success(self, mock_firestore_uploader):
        # Fake document snapshot
        class FakeSnapshot:
            def __init__(self, id, data, exists=True):
                self.id = id
                self._data = data
                self.exists = exists
            def get(self, key):
                return self._data.get(key)
            def to_dict(self):
                return self._data

        current_id = 'current1'
        prev_id = 'prev1'
        current_snap = FakeSnapshot(current_id, {'content': 'current content'})
        prev_snap = FakeSnapshot(prev_id, {'content': 'previous content', 'created_at': datetime(2025,5,1), 'timestamp': 100})

        # Fake portfolios collection
        portfolios = MagicMock()
        portfolios.document.return_value.get.return_value = current_snap
        portfolios.filter.return_value = portfolios
        portfolios.where.return_value = portfolios
        portfolios.stream.return_value = [current_snap, prev_snap]

        # Fake alternative reports collection
        alt_coll = MagicMock()
        alt_coll.filter.return_value = alt_coll
        alt_coll.where.return_value = alt_coll
        alt_coll.stream.return_value = []
        alt_doc_ref = MagicMock()
        alt_doc_ref.id = 'alt_report_id'
        alt_coll.document.return_value = alt_doc_ref

        # Fake Firestore DB
        fake_db = MagicMock()
        fake_db.collection.side_effect = lambda name: portfolios if name == 'portfolios' else alt_coll

        # Fake uploader instance
        fake_uploader = MagicMock()
        fake_uploader.db = fake_db
        fake_uploader.collection = portfolios
        mock_firestore_uploader.return_value = fake_uploader

        # Fake OpenAI client
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=MagicMock(content='alternative report content'))]
        fake_client = MagicMock()
        fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

        # Patch weight generation
        with patch('portfolio_generator.modules.report_upload.generate_alternative_portfolio_weights', AsyncMock(return_value='{}')):
            alt_id = await report_upload.generate_and_upload_alternative_report('report_content', current_id, openai_client=fake_client)

        self.assertEqual(alt_id, 'alt_report_id')

if __name__ == '__main__':
    unittest.main()
