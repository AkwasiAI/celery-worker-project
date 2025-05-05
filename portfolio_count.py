#!/usr/bin/env python3
"""
Simple script to list collections and count docs in 'portfolios' for Firestore production project.
"""
import os
# Remove emulator host if present to ensure production Firestore
os.environ.pop('FIRESTORE_EMULATOR_HOST', None)
from google.cloud import firestore
from google.oauth2 import service_account

SERVICE_ACCOUNT_PATH = "/Users/akwasiappiah/Documents/GitHub/celery-worker-project/hedgefundintelligence-1efd159a68ef.json"
PROJECT_ID = "hedgefundintelligence"

# Load credentials from service account
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH)

# Initialize Firestore client
client = firestore.Client(project=PROJECT_ID, credentials=creds, database='hedgefundintelligence')

# List all root collections
collections = list(client.collections())
print(f"Total collections in Firestore: {len(collections)}")
for coll in collections:
    print(f" - {coll.id}")

# Count documents in 'portfolios'
portfolios = client.collection("portfolios")
count = portfolios.count().get()[0][0].value
print(f"Total documents in 'portfolios' collection: {count}")
