# This script extracts county, constituency, and ward data from a PDF and stores it in a SQLite database.
import pdfplumber
import sqlite3

PDF_PATH = "kenya_admin.pdf"
DB_PATH = "kenya_admin.db"

# Connect to SQLite
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS counties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS constituencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    county_id INTEGER,
    UNIQUE(name, county_id),
    FOREIGN KEY (county_id) REFERENCES counties(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS wards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    constituency_id INTEGER,
    UNIQUE(name, constituency_id),
    FOREIGN KEY (constituency_id) REFERENCES constituencies(id)
)
""")

conn.commit()


def get_or_create_county(name):
    cursor.execute("INSERT OR IGNORE INTO counties (name) VALUES (?)", (name,))
    conn.commit()
    cursor.execute("SELECT id FROM counties WHERE name=?", (name,))
    return cursor.fetchone()[0]


def get_or_create_constituency(name, county_id):
    cursor.execute("""
        INSERT OR IGNORE INTO constituencies (name, county_id)
        VALUES (?, ?)
    """, (name, county_id))
    conn.commit()
    cursor.execute("""
        SELECT id FROM constituencies
        WHERE name=? AND county_id=?
    """, (name, county_id))
    return cursor.fetchone()[0]


def get_or_create_ward(name, constituency_id):
    cursor.execute("""
        INSERT OR IGNORE INTO wards (name, constituency_id)
        VALUES (?, ?)
    """, (name, constituency_id))
    conn.commit()


last_county = None
last_constituency = None
last_ward = None

with pdfplumber.open(PDF_PATH) as pdf:
    for page in pdf.pages:
        table = page.extract_table()
        if not table:
            continue

        for row in table[1:]:  # skip header
            try:
                county = row[1].strip()
                constituency = row[2].strip()
                ward = row[3].strip()

                # Stop when DIASPORA appears
                if county.upper() == "DIASPORA":
                    print("Reached DIASPORA — stopping extraction.")
                    conn.commit()
                    conn.close()
                    exit()

                # Skip empty rows
                if not county or not constituency or not ward:
                    continue

                # Detect changes in hierarchy
                if county != last_county:
                    county_id = get_or_create_county(county)
                    last_county = county
                    last_constituency = None  # reset lower levels

                if constituency != last_constituency:
                    constituency_id = get_or_create_constituency(
                        constituency, county_id
                    )
                    last_constituency = constituency
                    last_ward = None

                if ward != last_ward:
                    get_or_create_ward(ward, constituency_id)
                    last_ward = ward

            except Exception as e:
                print("Skipping problematic row:", row)
                print("Error:", e)
                continue

conn.commit()
conn.close()

print("Extraction completed successfully.")