import sqlite3

DB_PATH = "./instance/game.db"  # change this if your DB is elsewhere

def print_db_contents(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables found: {tables}\n")

    # Print contents of each table
    for table in tables:
        print(f"=== Table: {table} ===")
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [col[1] for col in cursor.fetchall()]
        print("Columns:", columns)

        cursor.execute(f"SELECT * FROM {table};")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(dict(zip(columns, row)))
        else:
            p

print_db_contents(DB_PATH)
