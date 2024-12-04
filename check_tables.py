import sqlite3

# Path to your database file
db_path = "bot.db"  # Replace with your actual database path

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the `users` table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitch_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            is_mod BOOLEAN DEFAULT FALSE,
            is_subscriber BOOLEAN DEFAULT FALSE,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    print("`users` table created successfully.")

except Exception as e:
    print("Error creating `users` table:", e)
finally:
    conn.close()
