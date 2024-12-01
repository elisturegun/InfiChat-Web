import sqlite3

DATABASE_PATH = 'teams_database.db'

try:
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    # Execute a command to get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    print("Tables in the database:")
    for table in tables:
        print(table[0])

    # View data from the subscriptions table
    table_name = "subscriptions"  # Replace with your table name
    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()

    print(f"\nData from {table_name}:")
    for row in rows:
        print(row)

    # View data from the conversation_references table
    conversation_table_name = "conversation_references"  # The table for conversation references
    cursor.execute(f"SELECT * FROM {conversation_table_name};")
    conversation_rows = cursor.fetchall()

    print(f"\nData from {conversation_table_name}:")
    for conversation_row in conversation_rows:
        print(conversation_row)

    # Close the connection
    cursor.close()
    connection.close()

except sqlite3.Error as error:
    print(f"Error while connecting to sqlite: {error}")
    

def get_all_users_formatted(db_name='teams_database.db'):
    try:
        # Connect to the database
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Execute a command to get all users from the users table
        cursor.execute("SELECT user_id, display_name FROM users;")
        users = cursor.fetchall()

        # Close the database connection
        conn.close()

        # Improved formatted output for users
        print("\n========== All Users from the Users Table ==========\n")
        if users:
            for index, user in enumerate(users, start=1):
                print(f"{index:>3}. User ID     : {user[0]}")
                print(f"     Display Name: {user[1]}\n")
        else:
            print("No users found in the users table.\n")
        
        print("=====================================================\n")

    except Exception as e:
        print(f"An error occurred while retrieving users: {e}")

# Call the function to test it
get_all_users_formatted()




