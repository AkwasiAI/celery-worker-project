#!/usr/bin/env python3
"""
Firestore Downloader Module
This module retrieves the latest document of a specified type from Firestore.
"""
import os
import json
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

class FirestoreDownloader:
    def __init__(self, database='hedgefundintelligence', collection_name='portfolios'):
        """Initialize Firestore client and target collection."""
        try:
            # Initialize client
            self.db = firestore.Client(database=database)
            self.collection = self.db.collection(collection_name)
        except Exception as e:
            print(f"Error initializing FirestoreDownloader: {e}")
            raise

    def get_latest(self, doc_type, output_file=None):
        """Retrieve the latest document of the specified type. Return content or output file path."""
        # Build query for latest document
        try:
            query = (
                self.collection
                    .filter('doc_type', '==', doc_type)
                    .filter('is_latest', '==', True)
                    .limit(1)
            )
        except AttributeError:
            query = (
                self.collection
                    .where(filter=FieldFilter('doc_type', '==', doc_type))
                    .where(filter=FieldFilter('is_latest', '==', True))
                    .limit(1)
            )
        docs = list(query.stream())
        if not docs:
            return None

        data = docs[0].to_dict()
        content = data.get('content')

        # Save to file if specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                if isinstance(content, dict):
                    json.dump(content, f, indent=2)
                else:
                    f.write(str(content))
            return output_file

        # Return the raw content (dict or string)
        return content
