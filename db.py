from pymongo import MongoClient
import os

# MongoDB Configuration
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
print(MONGO_URI)
mongo_client = MongoClient(MONGO_URI)

db = mongo_client["sigma-ai-email"]

ProspectModel = db["prospect"]
EmailHistoryModel = db["email_history"]
