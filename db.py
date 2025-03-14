from pymongo import MongoClient
import os

mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["loubby_navigator"]
feedback_collection = db["feedback"]

result = feedback_collection.insert_one("feedback_data")
