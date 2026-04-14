import undetected_chromedriver as uc
import time

def test_minimal():
    print("Starting minimal test...")
    try:
        driver = uc.Chrome(version_main=147)
        print("Driver started!")
        driver.get("https://www.google.com")
        print("Page loaded:", driver.title)
        time.sleep(2)
        driver.quit()
        print("Done.")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    test_minimal()
