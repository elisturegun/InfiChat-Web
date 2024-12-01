import sqlite3

# Specify the path to your database
DATABASE_PATH = 'teams_database.db'

try:
    # Connect to the database
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    # Specify the table name you want to delete records from
    table_name = "subscriptions"

    # Execute a command to delete all rows from the specified table
    cursor.execute(f"DELETE FROM {table_name};")
    connection.commit()  # Commit the changes

    print(f"All records from the '{table_name}' table have been deleted.")

    # Optionally, you can verify if the table is empty by fetching all rows
    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()

    if not rows:
        print(f"No records left in the '{table_name}' table.")
    else:
        print(f"Remaining data from {table_name}:")
        for row in rows:
            print(row)

    # Close the connection
    cursor.close()
    connection.close()

except sqlite3.Error as error:
    print(f"Error while connecting to sqlite: {error}")
