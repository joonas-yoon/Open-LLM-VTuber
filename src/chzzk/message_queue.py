"""
Requirements:

`docker run -d --name postgres -e POSTGRES_PASSWORD=<pwd> -p 5432:5432 quay.io/tembo/pg16-pgmq:latest`

In Postgres shell:

```sql
CREATE DATABASE chats ENCODING 'UTF8';
CREATE EXTENSION pgmq;
SELECT pgmq.create('messages');
```
"""
import os

from typing import List
from loguru import logger

from pgmq_sqlalchemy import PGMQueue
from pgmq_sqlalchemy.schema import Message, QueueMetrics

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

POSTGRES_NAME = os.environ.get("POSTGRES_NAME", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DSN = f"postgresql://{POSTGRES_NAME}:{POSTGRES_PASSWORD}@localhost:{POSTGRES_PORT}/chats"

engine = create_engine(POSTGRES_DSN)
session_maker = sessionmaker(bind=engine)
pgmq = PGMQueue(dsn=POSTGRES_DSN, engine=engine, session_maker=session_maker)

QUEUE_ID = 'messages'


def create_queue():
    global pgmq
    queues = pgmq.list_queues()
    if QUEUE_ID not in queues:
        logger.info(f"Creating queue: {QUEUE_ID}")
        pgmq.create_queue(QUEUE_ID)
    else:
        logger.info(f"Queue already exists: {QUEUE_ID}")


def push(message: dict) -> int:
    global pgmq
    message_id: int = pgmq.send(QUEUE_ID, message)
    return message_id


def poll(batch_size: int = 10) -> List[str]:
    global pgmq
    alive_secs = 60 * 1
    messages: List[Message] = pgmq.read_batch(
        QUEUE_ID, batch_size, vt=alive_secs) or []
    contents = []
    popped_ids = []
    for msg in messages:
        mid, message, enqueued_at = msg.msg_id, msg.message, msg.enqueued_at
        logger.info(
            f"Processing message: {mid} {enqueued_at} {message}")
        popped_ids.append(mid)
        contents.append(message)
    pgmq.delete_batch(QUEUE_ID, popped_ids)
    return contents


def count() -> int:
    global pgmq
    metrics: QueueMetrics = pgmq.metrics(QUEUE_ID)
    current_remains = metrics.queue_length
    # total_count_in_history = metrics.total_messages
    return current_remains


def is_empty() -> bool:
    return count() == 0
