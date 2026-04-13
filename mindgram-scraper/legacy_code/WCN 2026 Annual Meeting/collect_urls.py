from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import time
from collections import OrderedDict

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def extract_urls_from_page(page_url, page_number):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        driver = setup_driver()
        urls = []
        
        try:
            print(f"Navigating to URL: {page_url}")
            driver.get(page_url)
            
            # Wait for initial page load
            time.sleep(10)
            
            print(f"Looking for article citations on page {page_number}...")
            wait = WebDriverWait(driver, 20)
            
            css_selector = "h3 a"

            
            elements = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector))
            )
            
            print(f"Found {len(elements)} article citations")
            
            for element in elements:
                urls.append(element.get_attribute('href'))
            
            return urls
            
        except TimeoutException:
            print(f"Timeout error on attempt {retry_count + 1} of {max_retries}")
            retry_count += 1
            if retry_count == max_retries:
                print(f"Failed to load page {page_number} after {max_retries} attempts")
                return []
            time.sleep(5)
            
        except Exception as e:
            print(f"Error occurred on page {page_number}: {str(e)}")
            return []
            
        finally:
            print("Closing browser...")
            driver.quit()
            time.sleep(2)

def extract_all_urls():
    # Predefined list of page URLs
    page_urls = [
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=0",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=1",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=2",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=3",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=4",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=5",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=6",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=7",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=8",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=9",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=10",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=11",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=12",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=13",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=14",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=15",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=16",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=17",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=18",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=19",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=20",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=21",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=22",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=23",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=24",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=25",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=26",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=27",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=28",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=29",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=30",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=31",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=32",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=33",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=34",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=35",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=36",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=37",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=38",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=39",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=40",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=41",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=42",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=43",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=44",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=45",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=46",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=47",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=48",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=49",
"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart=50"
]
    
    # Dictionary to maintain order of URLs by page
    all_urls = OrderedDict()
    
    for page_number, page_url in enumerate(page_urls, 1):
        print(f"\nProcessing page {page_number} of {len(page_urls)}...")
        urls = extract_urls_from_page(page_url, page_number)
        
        if urls:
            all_urls[f"page_{page_number}"] = urls
            print(f"Total URLs collected on page {page_number}: {len(urls)}")
        else:
            print(f"No URLs found on page {page_number}")
            all_urls[f"page_{page_number}"] = []
        
        # Add delay between pages
        time.sleep(3)
    
    return all_urls

def save_to_json(urls_dict):
    if urls_dict:
        with open('article_urls.json', 'w', encoding='utf-8') as f:
            json.dump(urls_dict, f, indent=2, ensure_ascii=False)
        
        # Calculate total URLs
        total_urls = sum(len(urls) for urls in urls_dict.values())
        print(f"Successfully saved {total_urls} URLs from {len(urls_dict)} pages to article_urls.json")
    else:
        print("No URLs found to save")

if __name__ == "__main__":
    print("Starting URL extraction...")
    extracted_urls = extract_all_urls()
    save_to_json(extracted_urls)
    print("Script completed.")