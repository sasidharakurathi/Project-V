import sqlite3
import os

db_path = 'vega_sessions.db'
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check sessions table
    print("--- sessions table info ---")
    try:
        cursor.execute("PRAGMA table_info('sessions')")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
    except Exception as e:
        print(f"Error checking sessions: {e}")

    # Check episodic_memory table
    print("\n--- episodic_memory table info ---")
    try:
        cursor.execute("PRAGMA table_info('episodic_memory')")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
    except Exception as e:
        print(f"Error checking episodic_memory: {e}")

    conn.close()
