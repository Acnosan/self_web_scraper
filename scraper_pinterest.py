import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import concurrent.futures

class PinterestScraper:
    def __init__(self, search_query, output_folder, max_images=100):
        self.search_query = search_query
        self.output_folder = output_folder
        self.max_images = max_images
        self.setup_driver()
        
    def setup_driver(self):
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless")  # Uncomment to hide browser
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.driver = webdriver.Chrome(options=options)

    def wait_for_images(self):
        """Wait for any images to load using multiple selectors."""
        selectors = [
            "img[srcset]",
            "div[data-test-id='pinrep-image'] img",
            "div[data-test-id='pin'] img",
            "img[loading='auto']",
            "img[decoding='auto']"
        ]
        
        for selector in selectors:
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return True
            except TimeoutException:
                continue
        return False

    def extract_image_urls(self):
        """Extract image URLs using multiple methods."""
        image_urls = set()
        
        # Method 1: Direct img tags with srcset
        images = self.driver.find_elements(By.CSS_SELECTOR, "img[srcset]")
        for img in images:
            srcset = img.get_attribute('srcset')
            if srcset:
                urls = [url.strip().split(' ')[0] for url in srcset.split(',')]
                if urls:
                    image_urls.add(urls[-1])

        # Method 2: Pinterest-specific image containers
        pins = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test-id='pinrep-image'] img, div[data-test-id='pin'] img")
        for pin in pins:
            src = pin.get_attribute('src')
            if src and 'pinimg.com' in src:
                # Convert to original size URL
                parts = src.split('/')
                if len(parts) > 4:
                    base_url = '/'.join(parts[:-1])
                    image_urls.add(f"{base_url}/originals")

        # Method 3: Any large images
        images = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='pinimg.com']")
        for img in images:
            src = img.get_attribute('src')
            if src and 'pinimg.com' in src and not src.endswith(('.gif', '.svg')):
                image_urls.add(src)

        return image_urls

    def scroll_and_extract(self):
        """Scroll the page and extract image URLs."""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        image_urls = set()
        no_new_images_count = 0
        
        while len(image_urls) < self.max_images and no_new_images_count < 3:
            # Extract current images
            current_urls = self.extract_image_urls()
            prev_count = len(image_urls)
            image_urls.update(current_urls)
            
            if len(image_urls) == prev_count:
                no_new_images_count += 1
            else:
                no_new_images_count = 0
                
            print(f"Found {len(image_urls)} unique images")
            
            # Scroll down
            self.driver.execute_script("""
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            """)
            time.sleep(2)  # Wait for new images to load
            
            # Check if we've reached the bottom
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Try one more time with a longer wait
                time.sleep(2)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
            last_height = new_height
            
        return list(image_urls)

    def download_image(self, args):
        """Download a single image with retry mechanism."""
        idx, img_url = args
        retries = 3
        
        for attempt in range(retries):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.pinterest.com/'
                }
                
                response = requests.get(img_url, headers=headers, timeout=10)
                if response.status_code == 200 and len(response.content) > 1024:  # Check if image is not empty
                    filename = os.path.join(self.output_folder, f"image_{idx+1}.jpg")
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    return f"Successfully downloaded image {idx+1}"
            except Exception as e:
                if attempt == retries - 1:
                    return f"Failed to download image {idx+1} after {retries} attempts: {e}"
                time.sleep(1)

    def scrape(self):
        """Main scraping method."""
        os.makedirs(self.output_folder, exist_ok=True)
        
        try:
            # Load Pinterest search results
            url = f"https://www.pinterest.com/search/pins/?q={self.search_query}&rs=typed"
            print(f"Searching Pinterest for '{self.search_query}'...")
            self.driver.get(url)
            
            # Wait for initial content with multiple selectors
            print("Waiting for images to load...")
            if not self.wait_for_images():
                print("Warning: Initial images not found, but continuing anyway...")
            
            # Scroll and collect images
            print("Scrolling to load images...")
            img_urls = self.scroll_and_extract()
            
            if not img_urls:
                print("No images found!")
                return
                
            print(f"\nFound {len(img_urls)} unique high-resolution images.")
            
            # Download images in parallel
            print("Downloading images...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(self.download_image, enumerate(img_urls[:self.max_images])))
            
            for result in results:
                print(result)
                
        finally:
            self.driver.quit()
            print("Scraping completed!")

if __name__ == "__main__":
    # Configuration
    search_query = "kiana kaslana"
    output_folder = os.path.join("pinterest_images", "kiana_kaslana")
    max_images = 2000  # Adjust this number as needed
    
    # Create and run scraper
    scraper = PinterestScraper(search_query, output_folder, max_images)
    scraper.scrape()