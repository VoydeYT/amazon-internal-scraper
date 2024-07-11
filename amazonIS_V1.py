from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import json
import time
from datetime import datetime
from twilio.rest import Client
import schedule
import threading

# Twilio configuration
ACCOUNT_SID = ''
AUTH_TOKEN = ''
TWILIO_PHONE_NUMBER = ''
YOUR_PHONE_NUMBER = ''

def initialize_driver():
    driver = webdriver.Chrome()
    return driver

def main():
    try:
        # Initialize the WebDriver
        driver = initialize_driver()

        # URL to start scraping
        url = ""

        # Open the URL
        driver.get(url)

        # Record the start time
        start_time = datetime.now()

        # Function to get uptime
        def get_uptime():
            return datetime.now() - start_time

        # Function to scrape job listings from the current page
        def scrape_job_listings():
            job_listings = []
            job_tiles = driver.find_elements(By.CLASS_NAME, "job-tile")
            for tile in job_tiles:
                job_title_element = tile.find_element(By.CLASS_NAME, "job-link")
                job_title = job_title_element.text
                job_id_element = tile.find_element(By.XPATH, ".//li[contains(text(),'Job ID')]")
                job_id = job_id_element.text.split(":")[1].strip()
                job_listings.append({"title": job_title, "id": job_id})
            return job_listings

        # Function to check if the 'Next' button is interactable
        def is_next_button_interactable():
            try:
                next_button = driver.find_element(By.XPATH, "//button[@class='btn circle right' and @aria-label='Next page']")
                return next_button.is_enabled()
            except NoSuchElementException:
                return False

        # Function to wait indefinitely until the 'Next' button is visible
        def wait_for_next_button():
            while True:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.XPATH, "//button[@class='btn circle right' and @aria-label='Next page']"))
                    )
                    break
                except:
                    time.sleep(1)  # Wait for 1 second before checking again

        # Function to update the JSON file with new job listings
        def update_json(new_listings):
            try:
                with open("job_listings.json", "r") as f:
                    existing_listings = json.load(f)
            except FileNotFoundError:
                existing_listings = []

            existing_ids = [listing["id"] for listing in existing_listings]
            new_entries = [listing for listing in new_listings if listing["id"] not in existing_ids]

            if new_entries:
                updated_listings = existing_listings + new_entries
                with open("job_listings.json", "w") as f:
                    json.dump(updated_listings, f, indent=4)
                print(f"New job listings added: {new_entries}")
                send_sms_notification(new_entries)
            else:
                print("No new job listings found.")

        # Function to send an SMS notification
        def send_sms_notification(new_entries):
            client = Client(ACCOUNT_SID, AUTH_TOKEN)
            if new_entries:
                message_body = "New job listings added:\n" + "\n".join([f"{entry['title']} (Job ID: {entry['id']})" for entry in new_entries])
                # Split the message into chunks if it exceeds the 1600 character limit
                max_sms_length = 1600
                messages = [message_body[i:i + max_sms_length] for i in range(0, len(message_body), max_sms_length)]
                for message in messages:
                    sms = client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=YOUR_PHONE_NUMBER
                    )
                    print(f"SMS sent: {sms.sid}")
            else:
                print("No new job listings found today.")

        # Function to send daily summary SMS at 4:00 PM
        def send_daily_summary():
            try:
                with open("job_listings.json", "r") as f:
                    existing_listings = json.load(f)
                total_listings = len(existing_listings)
            except FileNotFoundError:
                total_listings = 0

            uptime = get_uptime()
            message_body = f"Daily Summary:\nTotal job listings: {total_listings}\nUptime: {uptime}"
            
            client = Client(ACCOUNT_SID, AUTH_TOKEN)
            message = client.messages.create(
                body=message_body,
                from_=TWILIO_PHONE_NUMBER,
                to=YOUR_PHONE_NUMBER
            )
            print(f"Daily summary SMS sent: {message.sid}")

        # Schedule the daily summary at 4:00 PM
        schedule.every().day.at("16:00").do(send_daily_summary)

        def run_schedule():
            while True:
                schedule.run_pending()
                time.sleep(1)

        # Start the scheduling thread
        threading.Thread(target=run_schedule).start()

        # Main loop to repeatedly scrape and update the job listings
        attempt_counter = 0
        while True:
            all_job_listings = []

            # Open the URL and wait for the 'Next' button
            driver.get(url)
            wait_for_next_button()

            # Scrape until the 'Next' button is not interactable
            while True:
                # Wait until the job tiles are visible
                WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CLASS_NAME, "job-tile"))
                )

                # Scrape job listings from the current page
                listings = scrape_job_listings()
                all_job_listings.extend(listings)

                # Check if the 'Next' button is interactable
                if not is_next_button_interactable():
                    break

                # Wait until the 'Next' button is visible and clickable
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@class='btn circle right' and @aria-label='Next page']"))
                )

                # Click the 'Next' button
                driver.execute_script("arguments[0].click();", next_button)

                # Wait for the next page to load
                time.sleep(3)

            # Update the JSON file with new job listings
            update_json(all_job_listings)

            # Print attempts and uptime every 10 attempts
            attempt_counter += 1
            if attempt_counter % 10 == 0:
                uptime = get_uptime()
                print(f"Attempts: {attempt_counter}, Uptime: {uptime}")

            # Wait for 1 minute before the next iteration
            time.sleep(60)
    except Exception as e:
        print(f"An error occurred: {e}")
        driver.quit()
        main()

if __name__ == "__main__":
    main()
