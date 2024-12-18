import os
import time
import requests
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from urllib.parse import quote
from webdriver_manager.chrome import ChromeDriverManager
from queue import Queue
from threading import Lock

class DanbooruScraper:
    def __init__(self, tags, output_folder, max_images=100):
        self.base_url = "https://danbooru.donmai.us"
        self.tags = quote(tags.replace(' ', '_'))
        self.output_folder = output_folder
        self.max_images = max_images
        self.image_urls = set()
        self.url_lock = Lock()
        self.drivers = Queue()
        
    def create_driver(self):
        """Create a new browser instance."""
        options = Options()
        #options.add_argument("--headless")
        options.add_argument("--window-size=1280,720")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
        
    def get_post_ids(self, page):
        """Extract post IDs from the search page."""
        driver = self.create_driver()
        try:
            search_url = f"{self.base_url}/posts?tags={self.tags}&page={page}"
            print(f"\nLoading search page {page}: {search_url}")
            driver.get(search_url)
            
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".post-preview"))
            )
            
            posts = driver.find_elements(By.CSS_SELECTOR, ".post-preview")
            post_ids = [post.get_attribute('data-id') for post in posts if post.get_attribute('data-id')]
            print(f"Found {len(post_ids)} posts on page {page}")
            return post_ids
            
        finally:
            driver.quit()

    def get_image_url(self, post_id):
        """Get image URL from a single post using a driver from the pool."""
        driver = self.create_driver()
        try:
            post_url = f"{self.base_url}/posts/{post_id}"
            driver.get(post_url)
            
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
            
            img_element = driver.find_element(By.CSS_SELECTOR, "img.fit-width")
            img_url = img_element.get_attribute('src')
            
            if img_url:
                with self.url_lock:
                    if len(self.image_urls) < self.max_images:
                        self.image_urls.add(img_url)
                        print(f"Found image URL ({len(self.image_urls)} total): {img_url}")
            
        except Exception as e:
            print(f"Error processing post {post_id}: {e}")
            
        finally:
            driver.quit()

    def download_image(self, args):
        idx, image_url = args
        img_name = str(self.tags)+str(idx+1)+".jpg"
        file_path = os.path.join(self.output_folder, img_name)
        
        try:
            img_data = requests.get(image_url).content
            with open(file_path, 'wb') as file:
                file.write(img_data)
            
            return f"Successfully downloaded: {img_name}"
        
        except Exception as e:
            print(f"Error: {e}")
            
    def process_page_posts(self, post_ids):
        """Process all posts from a page concurrently."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=11) as executor:
            executor.map(self.get_image_url, post_ids)

    def scrape(self):
        """Main scraping method."""
        os.makedirs(self.output_folder, exist_ok=True)
        
        try:
            page = 1
            while len(self.image_urls) < self.max_images:
                # Get post IDs from the current page
                post_ids = self.get_post_ids(page)
                
                if not post_ids:
                    print("No more posts found")
                    break
                
                # Process posts concurrently
                self.process_page_posts(post_ids)
                
                if len(self.image_urls) > self.max_images:
                    break
                    
                page += 1
            # Download the images concurrently
            final_urls = list(self.image_urls)[:self.max_images]
            print(f"\nStarting download of {len(final_urls)} images...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                executor.map(
                    self.download_image,
                    enumerate(final_urls))
            print("Download Done")
        except Exception as e:
            print(f"Error during scraping: {e}")

if __name__ == "__main__":
    tags = "kiana_kaslana"
    output_folder = os.path.join("danbooru_images", "kiana")
    max_images = 10
    
    scraper = DanbooruScraper(
        tags=tags,
        output_folder=output_folder,
        max_images=max_images
    )
    scraper.scrape()