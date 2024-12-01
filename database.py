# database.py

import sqlite3
import json

def init_db(db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, ip_address TEXT, url TEXT)''')
    
    # Create subscriptions table
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, subscription_type TEXT)''')

    # Conversation references table
    c.execute('''CREATE TABLE IF NOT EXISTS conversation_references
                 (user_id TEXT PRIMARY KEY, reference TEXT)''')
    
    # Users table to store all users from organization
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY, display_name TEXT)''')
    
    conn.commit()
    conn.close()
 
def add_document(title, content, ip_address, url=None, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("INSERT INTO documents (title, content, ip_address, url) VALUES (?, ?, ?, ?)", (title, content, ip_address, url))
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id

def delete_document(document_id, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()

def get_all_documents(db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("SELECT * FROM documents")
    documents = c.fetchall()
    conn.close()
    return documents

def get_document_by_id(document_id, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
    document = c.fetchone()
    conn.close()
    return document


# Function to save the conversation reference
def save_conversation_reference(user_id, conversation_reference, db_name='teams_database.db'):
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()

        # Serialize conversation reference to JSON
        reference_json = json.dumps(conversation_reference, default=str)

        # Insert or replace the conversation reference into the database
        c.execute("""
            REPLACE INTO conversation_references (user_id, reference)
            VALUES (?, ?)
        """, (user_id, reference_json))

        # Commit the transaction
        conn.commit()
    except Exception as e:
        print(f"Error saving conversation reference for user {user_id}: {e}")
    finally:
        # Ensure the connection is closed
        conn.close()

# Function to retrieve the conversation reference
def get_conversation_reference(user_id, db_name='teams_database.db'):
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()

        # Query to get the conversation reference
        c.execute("SELECT reference FROM conversation_references WHERE user_id = ?", (user_id,))
        result = c.fetchone()

        # Close the connection
        conn.close()

        if result:
            # Deserialize the conversation reference from JSON
            return json.loads(result[0])
        return None
    except Exception as e:
        print(f"Error retrieving conversation reference for user {user_id}: {e}")
        return None

# Function to delete a conversation reference
def delete_conversation_reference(user_id, db_name='teams_database.db'):
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()

        # Delete the conversation reference
        c.execute("DELETE FROM conversation_references WHERE user_id = ?", (user_id,))

        # Commit the transaction
        conn.commit()
    except Exception as e:
        print(f"Error deleting conversation reference for user {user_id}: {e}")
    finally:
        # Ensure the connection is closed
        conn.close()

def add_subscription(user_id, subscription_type, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("INSERT INTO subscriptions (user_id, subscription_type) VALUES (?, ?)", (user_id, subscription_type))
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id

def delete_subscription(user_id, subscription_type, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("DELETE FROM subscriptions WHERE user_id = ? AND subscription_type = ?", (user_id, subscription_type))
    conn.commit()
    conn.close()

def get_subscriptions_by_user(user_id, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("SELECT subscription_type FROM subscriptions WHERE user_id = ?", (user_id,))
    subscriptions = c.fetchall()
    conn.close()
    return subscriptions

def is_user_subscribed(user_id, subscription_type, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("SELECT 1 FROM subscriptions WHERE user_id = ? AND subscription_type = ?", (user_id, subscription_type))
    result = c.fetchone()
    conn.close()
    return result is not None

def unsubscribe(user_id, subscription_type, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("DELETE FROM subscriptions WHERE user_id = ? AND subscription_type = ?", (user_id, subscription_type))
    conn.commit()
    conn.close()
    
def get_subscriptions_by_user_type(subscription_type, db_name='teams_database.db'):
    """Retrieve all user IDs subscribed to a specific type of reminder."""
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("SELECT user_id FROM subscriptions WHERE subscription_type = ?", (subscription_type,))
    users = c.fetchall()
    conn.close()
    return users




def delete_all_subscriptions(db_name='teams_database.db'):
    """Delete all subscriptions from the subscriptions table."""
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("DELETE FROM subscriptions")
    conn.commit()
    conn.close()
    

# Function to add a user to the users table
def add_user(user_id, display_name, db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, display_name) VALUES (?, ?)", (user_id, display_name))
    conn.commit()
    conn.close()

# Function to get all users from the users table
def get_all_users(db_name='teams_database.db'):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute("SELECT user_id, display_name FROM users")
    users = c.fetchall()
    conn.close()
    return users

def get_all_conversation_references(db_name='teams_database.db'):
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        # Query all conversation references
        c.execute("SELECT user_id, reference FROM conversation_references")
        rows = c.fetchall()
        conn.close()

        # Transform results into a list of dictionaries
        conversation_references = []
        for row in rows:
            user_id, reference_json = row
            reference = json.loads(reference_json)
            display_name = reference.get("user", {}).get("name", "Unknown")
            conversation_references.append({"userId": user_id, "displayName": display_name})
        
        return conversation_references
    except Exception as e:
        logging.error(f"Error fetching conversation references: {str(e)}")
        return []

