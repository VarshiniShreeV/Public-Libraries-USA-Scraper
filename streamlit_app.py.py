import os
import sqlite3
import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time

# Streamlit page configuration
st.set_page_config(page_title="Libraries Near You", page_icon="📚", layout="wide")
st.title("📚Libraries Near You")

# Database name
db_name = "libraries_data.db"

# Initialize session state variables
if "selected_state" not in st.session_state:
    st.session_state.selected_state = None
if "viewing_details" not in st.session_state:
    st.session_state.viewing_details = False


def scraper():
    # Check if the database file already exists
    if os.path.exists(db_name):
        st.write("✅ Data already exists. Skipping scraping.")
        return  # Exit the scraper function if the file exists

    st.write("⏳ Scraping data, please wait...")
    chrome_options = Options()
    chrome_options.add_argument("--start-fullscreen")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--headless")
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()

    # Create tables for states and libraries if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state_name TEXT UNIQUE
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS libraries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state_id INTEGER,
        city TEXT,
        library TEXT,
        address TEXT,
        zip TEXT,
        phone TEXT,
        FOREIGN KEY (state_id) REFERENCES states (id)
    )
    ''')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.maximize_window()

    url = "https://publiclibraries.com/state/"
    driver.get(url)

    # Scrape states
    states = driver.find_elements(By.CSS_SELECTOR, "a[href*='/state/']")
    state_links = [state.get_attribute("href") for state in states]

    for state_link in state_links:
        driver.get(state_link)
        state_name = driver.find_element(By.TAG_NAME, "h1").text.replace(" Public Libraries", "")
        print(f"Scraping data for {state_name}...")

        # Insert state into States Table
        cursor.execute('''
        INSERT OR IGNORE INTO states (state_name)
        VALUES (?)
        ''', (state_name,))
        connection.commit()
        
        state_id = cursor.execute('''SELECT id FROM states WHERE state_name = ?''', (state_name,)).fetchone()[0]

        # Scrape libraries data of respective states
        rows = driver.find_elements(By.CSS_SELECTOR, "#libraries tbody tr")
        for row in rows:
            columns = row.find_elements(By.TAG_NAME, "td")
            if len(columns) == 5:  # Ensure valid row structure
                city = columns[0].text or "Not Available"
                library = columns[1].text or "Not Available" 
                address = columns[2].text or "Not Available"
                zip_code = columns[3].text or "Not Available"
                phone = columns[4].text or "Not Available"

                # Insert library data into the libraries table
                cursor.execute('''
                INSERT INTO libraries (state_id, city, library, address, zip, phone)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (state_id, city, library, address, zip_code, phone))

        connection.commit() 
        time.sleep(2)  

    driver.quit()
    connection.close()
    st.write("✅ Scraping completed successfully!")


# Call scraper function
if st.button("Scrape"):
    scraper()

# Load state names from the database
connection = sqlite3.connect(db_name)
state_names = [row[0] for row in connection.execute("SELECT state_name FROM states").fetchall()]

if not st.session_state.viewing_details:  # Dropdown for state selection
    state = st.selectbox("Choose a State", ["Select"] + state_names)
    if state != "Select":
        st.session_state.selected_state = state
        if st.button("View Libraries"):
            st.session_state.viewing_details = True

if st.session_state.viewing_details:  # Display libraries for the selected state
    selected_state = st.session_state.selected_state
    st.title(f"Libraries in {selected_state}")

    query = '''
        SELECT libraries.city, libraries.library, libraries.address, libraries.zip, libraries.phone
        FROM libraries
        JOIN states ON libraries.state_id = states.id
        WHERE states.state_name = ?
        '''
    result = pd.read_sql_query(query, connection, params=(selected_state,))
    
    if result.empty:
        st.write(f"No libraries found for {selected_state}.")
    else:
        st.dataframe(result, use_container_width=True)

    # Back to state selection
    if st.button("Back to State Selection"):
        st.session_state.viewing_details = False  # Reset to go back to state dropdown

connection.close()
