import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import concurrent.futures
import re

class PinterestScraper:
    def __init__(self, search_query, output_folder, folder_name, max_images):
        self.search_query = search_query
        self.output_folder = output_folder
        self.folder_name = folder_name
        self.max_images = max_images
        
    def setup_driver(self):
        options = Options()
        #options.add_argument('--headless=new')
        options.add_argument("--window-size=1280,720")
        options.add_argument('--log-level=3')  # This suppresses the DevTools message
        options.add_experimental_option('excludeSwitches', ['enable-logging'])  # This suppresses console logging
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    
    def wait_for_images(self):
        self.driver = self.setup_driver()
        url = f"https://www.pinterest.com/search/pins/?q={self.search_query}&rs=typed"
        print(f"Searching Pinterest for '{self.search_query}'...")
        self.driver.get(url)
        print("Waiting for images to load...")
        WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-test-id='search-feed'] img"))
        )
        """
        selectors = [
            "hCL kVc L4E MIw"
            "img[srcset]",
            "div[data-test-id='search-feed'] img",
            "div[data-test-id='pin'] img",
            "img[loading='auto']",
            "img[decoding='auto']"
        ]
        """


    def extract_image_urls(self):
        image_urls = set()
        images = self.driver.find_elements(By.CSS_SELECTOR, "img[src*='pinimg.com']")
        for img in images:
            src = img.get_attribute('src')
            if src and 'pinimg.com' in src and not src.endswith(('.gif', '.svg')):
                image_urls.add(src)

        return image_urls

    def scroll_and_extract(self):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        image_urls = set()
        no_new_images_count = 0
        
        while len(image_urls) < self.max_images and no_new_images_count < 3:
            # Extract current images
            current_urls = self.extract_image_urls()
            if not current_urls:
                print("No images found!")
                return
            
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
                break

        return list(image_urls)

    def download_image(self, args):
        idx, img_url = args
        img_name = self.folder_name+"_idx_"+str(idx)+".jpg"
        file_path = os.path.join(self.output_folder,img_name)
        try:
            response = requests.get(img_url).content
            with open(file_path, 'wb') as file:
                file.write(response)
                print(f'Successfully downloaded image {idx+1}')
            return
        except Exception as e:
            print(f"Failed to download image Error: {e}")

    def scrape(self):
        """Main scraping method."""
        os.makedirs(self.output_folder, exist_ok=True)
        
        try:
            self.wait_for_images()
            # Scroll and collect images
            print("Scrolling to load images...")
            img_urls = self.scroll_and_extract()
                
            print(f"\nFound {len(img_urls)} unique high-resolution images.")
            
            print("Downloading images...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(
                    self.download_image, 
                    enumerate(img_urls[:self.max_images])
                )
        finally:
            self.driver.quit()
            print("Scraping completed!")

if __name__ == "__main__":
    # Configuration
    search_query = "roger"
    
    folder_name = re.sub(r"[ ,]","__",search_query)
    output_folder = os.path.join("pinterest_images", folder_name)
    max_images = 20
    
    # Create and run scraper
    scraper = PinterestScraper(search_query, output_folder, folder_name, max_images)
    scraper.scrape()