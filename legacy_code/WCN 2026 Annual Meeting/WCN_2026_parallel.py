import json
import time
import logging
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-safe lock for writing shared results
results_lock = threading.Lock()

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
    """Comprehensive data extraction with multiple retry mechanisms."""
    missing_fields = {}
    
    try:
        # Navigate to URL with a random delay
        driver.get(url)
        time.sleep(random.uniform(1, 2))

        # Wait explicitly for author information to load (20 seconds)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.dropBlock__body__outer"))
            )
        except TimeoutException:
            logging.warning(f"Timeout waiting for author information on {url}")
        
        # Extract data using BeautifulSoup for more reliable parsing
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Title extraction using XPath equivalent
        title_elem = soup.select_one('h1[property="name"]')
        title = title_elem.get_text().strip() if title_elem else ""
        if not title:
            missing_fields['title'] = 'Missing'    

        # Abstract extraction with proper spacing
        abstract_elem = soup.select_one('section#bodymatter[data-extent="bodymatter"][property="articleBody"][typeof="Text"], div#abstracts[data-extent="frontmatter"]')
        abstract = abstract_elem.get_text(strip=True, separator=' ') if abstract_elem else ""
        abstract_html = abstract_elem.prettify() if abstract_elem else ""
        
        if not abstract:
            missing_fields['abstract'] = 'Missing'
        if not abstract_html:
            missing_fields['abstract_html'] = 'Missing'
        
        author_info_list = []
        author_containers = soup.select("div.dropBlock__body__outer")
        for container in author_containers:
            author_elem = container.select_one("div.dropBlock__body div.heading")
            affiliation_elem = container.select_one("div[property='affiliation'][typeof='Organization']")
            if author_elem:
                author_name = author_elem.get_text().strip()
                affiliation = affiliation_elem.get_text().strip() if affiliation_elem else ""
                if affiliation:
                    author_info = f"{author_name}; {affiliation}"
                else:
                    author_info = author_name
                author_info_list.append(author_info)

        author_info = ", ".join(author_info_list)
        if not author_info:
            missing_fields['author_info'] = 'Missing'                
        # DOI extraction
        doi_elem = soup.select_one("span.doi a")
        doi = doi_elem.get_text().strip() if doi_elem else ""
        if not doi:
            missing_fields['doi'] = 'Missing'

        # Construct result dictionary
        result = {
            "link": url,
            "title": title,
            "doi": doi,
            "number": "",
            "author_info": author_info,
            "abstract": abstract,
            "abstract_html": abstract_html,
            "abstract_markdown": "",
            "abstract_metadata": {}
        }

        return result, missing_fields if missing_fields else None

    except Exception as e:
        logging.error(f"Error extracting data from {url}: {str(e)}")
        return None, {"url": url, "error": str(e)}


def create_driver_with_retry(max_attempts=3):
    """Create a driver with retry logic to handle driver initialization failures."""
    for attempt in range(1, max_attempts + 1):
        try:
            driver = setup_driver()
            logging.info(f"Driver created successfully on attempt {attempt}")
            return driver
        except Exception as e:
            logging.error(f"Driver creation failed on attempt {attempt}: {str(e)}")
            if attempt < max_attempts:
                time.sleep(3)  # Wait before retrying
            else:
                raise RuntimeError(f"Failed to create driver after {max_attempts} attempts: {str(e)}")


def worker_scrape(worker_id, urls_chunk, is_first_worker, total_urls, url_index_offset):
    """
    Worker function that runs in its own thread with its own driver.
    Each worker handles a subset of URLs assigned to it.
    """
    local_results = []
    local_failed = {}
    local_missing = {}

    driver = None
    try:
        driver = create_driver_with_retry()
        logging.info(f"[Worker {worker_id}] Driver initialized. Processing {len(urls_chunk)} URLs.")

        for idx, (global_idx, url) in enumerate(urls_chunk):
            # First worker, first URL: pause for human verification
            if is_first_worker and idx == 0:
                print(f"[Worker {worker_id}] Waiting 30 seconds for human verification on first URL...")
                driver.get(url)
                time.sleep(30)

            attempt = 0
            max_url_attempts = 3
            success = False

            while attempt < max_url_attempts and not success:
                try:
                    print(f"[Worker {worker_id}] Scraping URL {global_idx + 1}/{total_urls}: {url} (attempt {attempt + 1})")
                    result, missing_fields = safe_extract_data(driver, url)

                    if result:
                        local_results.append(result)

                    if missing_fields:
                        if isinstance(missing_fields, dict) and 'url' in missing_fields:
                            local_failed[url] = missing_fields
                        else:
                            local_missing[url] = missing_fields

                    success = True

                except WebDriverException as e:
                    attempt += 1
                    logging.error(f"[Worker {worker_id}] WebDriverException on {url} (attempt {attempt}): {str(e)}")

                    if attempt < max_url_attempts:
                        logging.info(f"[Worker {worker_id}] Reinitializing driver and retrying...")
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        try:
                            driver = create_driver_with_retry()
                        except Exception as reinit_err:
                            logging.error(f"[Worker {worker_id}] Driver reinitialization failed: {str(reinit_err)}")
                            local_failed[url] = {"error": f"Driver reinitialization failed: {str(reinit_err)}"}
                            break
                    else:
                        local_failed[url] = {"error": str(e)}

                except Exception as e:
                    logging.error(f"[Worker {worker_id}] Unexpected error on {url}: {str(e)}")
                    local_failed[url] = {"error": str(e)}
                    break

            # Random small delay between requests
            time.sleep(random.uniform(0.5, 1.5))

    except Exception as e:
        logging.error(f"[Worker {worker_id}] Fatal worker error: {str(e)}")

    finally:
        if driver:
            try:
                driver.quit()
                logging.info(f"[Worker {worker_id}] Driver closed.")
            except Exception:
                pass

    return local_results, local_failed, local_missing


def batch_scrape_urls(urls, num_workers=5):
    """Scrape URLs in parallel using 5 browser windows (one per worker thread)."""
    all_results = []
    failed_urls = {}
    missing_field_urls = {}

    total_urls = len(urls)

    # Distribute URLs evenly across workers
    # Each URL gets a global index so we can report progress accurately
    indexed_urls = list(enumerate(urls))  # [(0, url0), (1, url1), ...]

    # Split into num_workers chunks
    chunks = [[] for _ in range(num_workers)]
    for i, item in enumerate(indexed_urls):
        chunks[i % num_workers].append(item)

    print(f"Distributing {total_urls} URLs across {num_workers} parallel workers...")
    for i, chunk in enumerate(chunks):
        print(f"  Worker {i + 1}: {len(chunk)} URLs")

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {}
        for worker_id, chunk in enumerate(chunks):
            if not chunk:
                continue
            is_first = (worker_id == 0)
            future = executor.submit(
                worker_scrape,
                worker_id + 1,
                chunk,
                is_first,
                total_urls,
                chunk[0][0] if chunk else 0
            )
            futures[future] = worker_id + 1

        # Collect results as each worker completes
        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                local_results, local_failed, local_missing = future.result()
                with results_lock:
                    all_results.extend(local_results)
                    failed_urls.update(local_failed)
                    missing_field_urls.update(local_missing)
                print(f"[Worker {worker_id}] Finished. Collected {len(local_results)} results.")
            except Exception as e:
                logging.error(f"[Worker {worker_id}] Worker raised an exception: {str(e)}")

    # Save results and failed URLs
    if all_results:
        with open('scraped_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=4, ensure_ascii=False)
        print(f"Saved {len(all_results)} results to scraped_data.json")

    if failed_urls:
        with open('failed_urls.json', 'w', encoding='utf-8') as f:
            json.dump(failed_urls, f, indent=4, ensure_ascii=False)

    if missing_field_urls:
        with open('missing_field_urls.json', 'w', encoding='utf-8') as f:
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
        
        # Batch scrape URLs with 5 parallel workers
        results, failed_urls, missing_field_urls = batch_scrape_urls(urls, num_workers=5)
        
        print(f"Successfully scraped {len(results)} URLs")
        print(f"Failed to scrape {len(failed_urls)} URLs")
        print(f"URLs with missing fields: {len(missing_field_urls)}")
    
    except Exception as e:
        print(f"Error in main scraping process: {str(e)}")

if __name__ == "__main__":
    main()