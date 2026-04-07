import sqlite3
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gridflow.db")

def init_db():
    """Create the table if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS grid_logs 
                 (timestamp TEXT, load_mw REAL, temp_c REAL, solar_mw REAL, co2_kg REAL)''')
    conn.commit()
    conn.close()

def log_data(load, temp, solar, co2):
    """Save a new snapshot to the database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO grid_logs VALUES (?, ?, ?, ?, ?)", 
              (now, load, temp, solar, co2))
    conn.commit()
    conn.close()

def get_recent_history(limit=50):
    """Fetch the last X records for the graph"""
    conn = sqlite3.connect(DB_PATH)
    import pandas as pd
    df = pd.read_sql_query(f"SELECT * FROM grid_logs ORDER BY timestamp DESC LIMIT {limit}", conn)
    conn.close()
    return df.sort_values('timestamp') # Flip so it's chronological