import os
import unittest
from datetime import datetime
from google.cloud import firestore
import asyncio
from google.cloud.firestore_v1.base_query import FieldFilter

from portfolio_generator.modules import report_upload

class TestAlternativeReportIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        report_upload.FIRESTORE_AVAILABLE = True

    async def test_generate_and_upload_alternative_report(self):
        # Upload an initial older base report to Firestore to establish history
        old_content = "# Integration Test Old Base Report"
        old_portfolio = {"data": {"assets": []}}
        old_id = await report_upload.upload_report_to_firestore(old_content, old_portfolio)
        self.assertIsNotNone(old_id)
        # Upload a base report to Firestore
        base_content = "# Integration Test Base Report"
        base_portfolio = {"data": {"assets": []}}
        base_id = await report_upload.upload_report_to_firestore(base_content, base_portfolio)
        self.assertIsNotNone(base_id)

        # Fetch latest report from Firestore
        client = firestore.Client(database='hedgefundintelligence')
        portfolios = client.collection('portfolios')
        count_query = portfolios.count()             # build aggregation query :contentReference[oaicite:5]{index=5}  
        count_result = count_query.get()  
        doc_count = count_result[0][0].value  
        print(doc_count)
        
        query = portfolios
        query = query.where(filter=FieldFilter('doc_type', '==', 'reports'))
        query = query.where(filter=FieldFilter('is_latest', '==', True))
        docs = list(query.stream())
        self.assertTrue(docs, "No latest report found in Firestore")
        latest = docs[0]
        latest_content = latest.to_dict().get('content')
        self.assertEqual(latest_content, base_content)

        # Generate and upload alternative report using fetched data
        alt_content = "# Integration Test Alternative Content"
        alt_id = await report_upload.generate_and_upload_alternative_report(alt_content, base_id)
        self.assertIsNotNone(alt_id)

        # Verify alternative report is stored
        alt_coll = client.collection('report-alternatives')
        alt_docs = list(alt_coll.where('doc_type', '==', 'report-alternative').where('is_latest', '==', True).stream())
        alt_ids = [doc.id for doc in alt_docs]
        self.assertIn(alt_id, alt_ids)

if __name__ == '__main__':
    unittest.main()
