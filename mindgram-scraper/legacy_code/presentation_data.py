import json
import time
import logging
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

def setup_driver():
    """Setup and return a configured undetected Chrome driver instance to bypass bot detection."""
    options = uc.ChromeOptions()
    options.headless = False
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--start-maximized")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Create driver with specified options and automatic version matching
    driver = uc.Chrome(
        options=options,
        version_main=146  # This will match ChromeDriver to your Chrome version 135
    )
    
    # Execute JavaScript to make navigator.webdriver undefined
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def safe_extract_data(driver, url):
    """Comprehensive data extraction with multiple retry mechanisms using XPath selectors."""
    missing_fields = {}
    
    try:
        # Navigate to URL with a random delay
        driver.get(url)
        time.sleep(random.uniform(1, 2))

        # Wait explicitly for author information to load (20 seconds)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '(//h4[@class="panel-title-text"])[1]'))
            )
        except TimeoutException:
            logging.warning(f"Timeout waiting for author information on {url}")
        
        # Title extraction using XPath
        try:
            title = driver.find_element(By.XPATH, '(//h4[@class="panel-title-text"])[1]').text.strip().replace("\n", " ")
        except NoSuchElementException:
            title = ""
            missing_fields['title'] = 'Missing'

        try:
            session_name_elements = driver.find_elements(By.XPATH, '//p/b')
            session_name = " ".join([elem.text.strip().replace("\n", " ") for elem in session_name_elements])
        except NoSuchElementException:
            session_name = ""
            missing_fields['session_name'] = 'Missing'     

        try:
            session_topic_elements = driver.find_elements(By.XPATH, '//p[@class="trackname innertracks"]')
            session_topic = " ".join([elem.text.strip().replace("\n", " ") for elem in session_topic_elements])
        except NoSuchElementException:
            session_topic = ""
            missing_fields['session_topic'] = 'Missing'    

        try:
            presentation_time = driver.find_element(By.XPATH, '//div[contains(@class,"date-time-room-div") and .//i[@class="fa fa-clock-o"]]').text.strip().replace("\n", " ")
        except NoSuchElementException:
            presentation_time = ""
            missing_fields['presentation_time'] = 'Missing'

        try:
            author_info_elements = driver.find_elements(By.XPATH, '//div[@class="col-sm-9 col-xs-8"]')
            author_info_list = []
            for element in author_info_elements:
                try:
                    # Get author name from the span
                    author = element.find_element(By.XPATH, './/span[@class="text-large"]').text.strip().replace("\n", " ")
                    
                    # Get the full text of the div and extract affiliation (text after the author span)
                    full_div_text = element.text.strip()
                    
                    # Extract affiliation - it's the text that comes after the author name
                    # The author name is followed by newline and then affiliation
                    if author and author in full_div_text:
                        # Get everything after the author name
                        affiliation = full_div_text.split(author, 1)[-1].strip().replace("\n", " ")
                        # Clean up any leading newlines or extra spaces
                        affiliation = affiliation.lstrip('\n').strip()
                    else:
                        affiliation = ""
                        
                except NoSuchElementException:
                    author = ""
                    affiliation = ""
                    
                if author or affiliation:
                    author_info_list.append(f"{author}; {affiliation}")
            author_info = ", ".join(author_info_list) if author_info_list else ""
            if not author_info:
                missing_fields['author_info'] = 'Missing'
        except NoSuchElementException:
            author_info = ""
            missing_fields['author_info'] = 'Missing'   

        try:
            abstract = driver.find_element(By.XPATH, '//div[@class="panel-body" and starts-with(normalize-space(.), "Info")]').text.strip().replace("\n", " ")
        except NoSuchElementException:
            abstract = ""
            missing_fields['abstract'] = 'Missing'       

        try:
            abstract_html = driver.find_element(By.XPATH, '//div[@class="panel-body" and starts-with(normalize-space(.), "Info")]').get_attribute('outerHTML')
        except NoSuchElementException:
            abstract_html = ""
            missing_fields['abstract_html'] = 'Missing'         

        # Construct result dictionary
        result = {
            "link": url,
            "title": title,
            "doi": "",
            "number": "",
            "author_info": author_info,
            "abstract": abstract,
            "abstract_html": abstract_html,
            "abstract_markdown": "",
            "abstract_metadata": {
                "session_topic": session_topic,
                "presentation_time": presentation_time,
            }
        }

        return result, missing_fields if missing_fields else None

    except Exception as e:
        logging.error(f"Error extracting data from {url}: {str(e)}")
        return None, {"url": url, "error": str(e)}

def batch_scrape_urls(urls, batch_size=10):
    """Scrape URLs in batches using a single browser instance."""
    all_results = []
    failed_urls = {}
    missing_field_urls = {}
    
    # Setup a single driver for entire scraping process
    driver = setup_driver()
    
    try:
        total_urls = len(urls)
        
        for batch_start in range(0, total_urls, batch_size):
            batch_urls = urls[batch_start:batch_start + batch_size]
            
            for idx, url in enumerate(batch_urls):
                try:
                    print(f"Scraping URL {urls.index(url) + 1}/{total_urls}: {url}")
                    
                    # Add 30-second wait for the very first URL to allow for human verification
                    if batch_start == 0 and idx == 0:
                        print("Waiting 30 seconds for human verification on first URL...")
                        driver.get(url)
                        time.sleep(10)  # Wait for human to solve the verification puzzle
                    
                    result, missing_fields = safe_extract_data(driver, url)
                    
                    if result:
                        all_results.append(result)
                    
                    if missing_fields:
                        if isinstance(missing_fields, dict) and 'url' in missing_fields:
                            failed_urls[url] = missing_fields
                        else:
                            missing_field_urls[url] = missing_fields
                    
                    # Random small delay between requests
                    time.sleep(random.uniform(0.5, 1.5))
                
                except Exception as e:
                    logging.error(f"Error processing {url}: {str(e)}")
                    failed_urls[url] = {"error": str(e)}
    
    except Exception as e:
        logging.error(f"Overall scraping error: {str(e)}")
    
    finally:
        # Close the browser
        driver.quit()
    
    # Save results and failed URLs
    if all_results:
        with open('presentation_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=4, ensure_ascii=False)
    
    if failed_urls:
        with open('p_failed_urls.json', 'w', encoding='utf-8') as f:
            json.dump(failed_urls, f, indent=4, ensure_ascii=False)
    
    if missing_field_urls:
        with open('p_missing_field_urls.json', 'w', encoding='utf-8') as f:
            json.dump(missing_field_urls, f, indent=4, ensure_ascii=False)
    
    return all_results, failed_urls, missing_field_urls

def main():
    """Main function to run the optimized scraper."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("scraper.log"),
            logging.StreamHandler()
        ]
    )
    
    try:
        # Load URLs
        with open('article_urls.json', 'r') as f:   
            urls = json.load(f)
        
        print(f"Loaded {len(urls)} URLs for scraping")
        
        # Batch scrape URLs
        results, failed_urls, missing_field_urls = batch_scrape_urls(urls)
        
        print(f"Successfully scraped {len(results)} URLs")
        print(f"Failed to scrape {len(failed_urls)} URLs")
        print(f"URLs with missing fields: {len(missing_field_urls)}")
    
    except Exception as e:
        print(f"Error in main scraping process: {str(e)}")

if __name__ == "__main__":
    main()