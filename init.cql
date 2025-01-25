CREATE KEYSPACE IF NOT EXISTS mlops 
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE mlops;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, 
    username TEXT,
    email TEXT,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    user_id TEXT,
    conversation_id TEXT,
    started_at TIMESTAMP,
    PRIMARY KEY (user_id, conversation_id)
);

CREATE TABLE IF NOT EXISTS messages (
    user_id TEXT,
    conversation_id TEXT,
    role TEXT, 
    message TEXT,
    timestamp TIMESTAMP,
    PRIMARY KEY ((conversation_id), timestamp)
);
