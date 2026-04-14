import logging
import time
import os
import random
import undetected_chromedriver as uc
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

def test():
    options = uc.ChromeOptions()
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=SearchEngineChoice,ProfilePicker")
    options.add_argument("--window-size=1366,768")
    
    # Profile config — use local COPY of Ashok profile (system profile is always locked)
    user_data_dir = str(Path("chrome_profile_ashok").resolve())
    
    # No profile_name needed — the folder IS the profile

    print(f"User Data Dir: {user_data_dir}")

    try:
        driver = uc.Chrome(
            options=options,
            version_main=147,
            user_data_dir=user_data_dir,
            use_subprocess=True
        )
        driver.maximize_window()
        print("Driver started successfully!")
        driver.get("https://www.sciencedirect.com")
        time.sleep(5)
        print("Page title:", driver.title)
        driver.quit()
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    test()
