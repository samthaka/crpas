# This script extracts county, constituency, and ward data from a PDF and stores it in a SQLite database.
import pdfplumber
import sqlite3
import psutil
import os
import gc
import re
from tqdm import tqdm

PDF_PATH = "kenya_admin.pdf"
DB_PATH = "kenya_admin.db"


process = psutil.Process(os.getpid())

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

last_county = None
last_constituency = None
last_ward = None

with pdfplumber.open(PDF_PATH) as pdf:
    total_pages = len(pdf.pages)

    with tqdm(total=total_pages, desc="Processing", unit="page") as pbar:

        for page in pdf.pages:

            text = page.extract_text()
            if not text:
                pbar.update(1)
                continue

            lines = text.split("\n")

            for line in lines:

                if "DIASPORA" in line.upper():
                    print("\nReached DIASPORA — stopping.")
                    conn.commit()
                    conn.close()
                    exit()

                if "PS ID" in line and "COUNTY" in line:
                    continue

                parts = re.split(r"\s{2,}", line.strip())

                if len(parts) < 4:
                    continue

                try:
                    county = parts[1].strip()
                    constituency = parts[2].strip()
                    ward = parts[3].strip()

                    if not county or not constituency or not ward:
                        continue

                    if county != last_county:
                        cursor.execute("INSERT OR IGNORE INTO counties (name) VALUES (?)", (county,))
                        cursor.execute("SELECT id FROM counties WHERE name=?", (county,))
                        county_id = cursor.fetchone()[0]
                        last_county = county
                        last_constituency = None

                    if constituency != last_constituency:
                        cursor.execute("""
                            INSERT OR IGNORE INTO constituencies (name, county_id)
                            VALUES (?, ?)
                        """, (constituency, county_id))
                        cursor.execute("""
                            SELECT id FROM constituencies
                            WHERE name=? AND county_id=?
                        """, (constituency, county_id))
                        constituency_id = cursor.fetchone()[0]
                        last_constituency = constituency
                        last_ward = None

                    if ward != last_ward:
                        cursor.execute("""
                            INSERT OR IGNORE INTO wards (name, constituency_id)
                            VALUES (?, ?)
                        """, (ward, constituency_id))
                        last_ward = ward

                except:
                    continue

            conn.commit()

            # Resource Monitoring
            mem_mb = process.memory_info().rss / (1024 * 1024)
            cpu = process.cpu_percent(interval=None)

            pbar.set_postfix({
                "RAM_MB": f"{mem_mb:.0f}",
                "CPU_%": f"{cpu:.1f}"
            })

            del text
            del lines
            gc.collect()

            pbar.update(1)

conn.commit()
conn.close()
print("\nExtraction complete.")