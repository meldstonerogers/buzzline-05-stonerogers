# consumer_stonerogers.py

import json
import os
import pathlib
import sys
import time
from kafka import KafkaConsumer
from pymongo import MongoClient
from utils.utils_logger import logger
import utils.utils_config as config

# MongoDB functions
def init_db(mongo_uri: str, db_name: str, collection_name: str):
    """
    Initialize the MongoDB database by connecting to it.
    Args:
    - mongo_uri (str): MongoDB connection URI.
    - db_name (str): Database name.
    - collection_name (str): Collection name.
    """
    logger.info(f"Calling MongoDB init_db() for database '{db_name}' and collection '{collection_name}'.")
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]
        
        # Optionally, you can drop the collection if you want to start fresh
        collection.drop()
        logger.info("SUCCESS: Database and collection initialized.")
    except Exception as e:
        logger.error(f"ERROR: Failed to initialize MongoDB: {e}")


def insert_message(message: dict, mongo_uri: str, db_name: str, collection_name: str) -> None:
    """
    Insert a single processed message into the MongoDB collection.
    Args:
    - message (dict): Processed message to insert.
    - mongo_uri (str): MongoDB connection URI.
    - db_name (str): Database name.
    - collection_name (str): Collection name.
    """
    logger.info("Calling MongoDB insert_message() with:")
    logger.info(f"{message=}")

    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]
        result = collection.insert_one(message)
        logger.info(f"Inserted message into MongoDB with _id: {result.inserted_id}")
    except Exception as e:
        logger.error(f"ERROR: Failed to insert message into MongoDB: {e}")


def process_message(message: dict) -> dict:
    """
    Process and transform a single JSON message.
    Converts message fields to appropriate data types.
    Args:
        message (dict): The JSON message as a Python dictionary.
    """
    logger.info(f"Called process_message() with: {message=}")
    try:
        processed_message = {
            "message": message.get("message"),
            "author": message.get("author"),
            "timestamp": message.get("timestamp"),
            "category": message.get("category"),
            "sentiment": float(message.get("sentiment", 0.0)),
            "keyword_mentioned": message.get("keyword_mentioned"),
            "message_length": int(message.get("message_length", 0)),
        }
        logger.info(f"Processed message: {processed_message}")
        return processed_message
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return None


def consume_messages_from_kafka(
    topic: str,
    kafka_url: str,
    group: str,
    mongo_uri: str,
    db_name: str,
    collection_name: str,
    interval_secs: int,
):
    """
    Consume new messages from Kafka topic and process them.
    Each message is expected to be JSON-formatted.
    Args:
    - topic (str): Kafka topic to consume messages from.
    - kafka_url (str): Kafka broker address.
    - group (str): Consumer group ID for Kafka.
    - mongo_uri (str): MongoDB URI.
    - db_name (str): Database name.
    - collection_name (str): Collection name.
    - interval_secs (int): Interval between reads from the file.
    """
    logger.info(f"Starting Kafka consumer for topic {topic}")
    
    try:
        consumer = KafkaConsumer(
            topic,
            group_id=group,
            bootstrap_servers=kafka_url,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
    except Exception as e:
        logger.error(f"ERROR: Could not create Kafka consumer: {e}")
        sys.exit(1)

    try:
        for message in consumer:
            processed_message = process_message(message.value)
            if processed_message:
                insert_message(processed_message, mongo_uri, db_name, collection_name)
            time.sleep(interval_secs)
    except Exception as e:
        logger.error(f"ERROR: Could not consume messages from Kafka: {e}")
        raise


def main():
    """
    Main function to run the consumer process.
    Reads configuration, initializes the MongoDB, and starts consumption.
    """
    logger.info("Starting Consumer to run continuously.")

    try:
        topic = config.get_kafka_topic()
        kafka_url = config.get_kafka_broker_address()
        group_id = config.get_kafka_consumer_group_id()
        interval_secs = config.get_message_interval_seconds_as_int()
        
        # MongoDB details
        mongo_uri = config.get_mongo_uri()  # MongoDB URI (e.g., mongodb://localhost:27017)
        db_name = "buzzDB"  # The database name is set to buzzDB
        collection_name = "streamed_messages"  # The collection name

        logger.info("Successfully read environment variables.")
    except Exception as e:
        logger.error(f"ERROR: Failed to read environment variables: {e}")
        sys.exit(1)

    logger.info("Initialize MongoDB database.")
    init_db(mongo_uri, db_name, collection_name)

    logger.info("Start consuming Kafka messages and inserting into MongoDB.")
    try:
        consume_messages_from_kafka(
            topic, kafka_url, group_id, mongo_uri, db_name, collection_name, interval_secs
        )
    except KeyboardInterrupt:
        logger.warning("Consumer interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Consumer shutting down.")


if __name__ == "__main__":
    main()
