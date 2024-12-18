import os
import re
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
    def __init__(self, tags, output_folder, max_images ,page_number, download_idx):
        self.base_url = "https://danbooru.donmai.us"
        self.tags = quote(tags.replace(' ', '_'))
        self.output_folder = output_folder
        self.max_images = max_images
        self.page_number = page_number
        self.download_idx = download_idx
        self.drivers = Queue()
        
    def create_driver(self):
        """Create a new browser instance."""
        options = Options()
        #options.add_argument('--headless=new')
        options.add_argument("--window-size=1280,720")
        options.add_argument('--log-level=3')  # This suppresses the DevTools message
        options.add_experimental_option('excludeSwitches', ['enable-logging'])  # This suppresses console logging
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
        
    def get_post_ids(self, page):
        """Extract post IDs from the search page."""
        driver = self.create_driver()
        post_urls = []
        search_url = f"{self.base_url}/posts?tags={self.tags}&page={page}"
        print(f"\nLoading search page {page}: {search_url}")
        driver.get(search_url)
        
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".post-preview"))
        )
        try:
            posts = driver.find_elements(By.CSS_SELECTOR, ".post-preview")
            for post in posts:
                if len(post_urls) >= self.max_images:  # Check if we've reached the limit
                    break  # Exit the loop if we have enough posts
                post_id = post.get_attribute('data-id')
                if post_id:
                    post_urls.append(post_id)
        except Exception as e:
                print(f"Error processing post {posts}: {e}")
            
        finally:
            driver.quit()
            print(f"Found {len(post_urls)} posts on page (limited by max_images, left {self.max_images})")
            return post_urls

    def get_image_url(self, post_url):
        """Get image URL from a single post using a driver from the pool."""
        driver = self.create_driver()
        image_urls = set()
        try:
            driver.get(f"{self.base_url}/posts/{post_url}")
            
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
            img_element = driver.find_element(By.CSS_SELECTOR, "img.fit-width")
            img_url = img_element.get_attribute('src')
            if img_url:
                image_urls.add(img_url)
            
        except Exception as e:
            print(f"Error processing post {post_url}: {e}")
            
        finally:
            driver.quit()
            return image_urls

    def download_image(self, args):
        idx, image_url = args
        img_name = str(self.tags)+"_idx_"+str(idx+1)+".jpg"
        file_path = os.path.join(self.output_folder, img_name)
        
        try:
            img_data = requests.get(image_url).content
            with open(file_path, 'wb') as file:
                file.write(img_data)
                print(f'image {img_name} downloaded')
            return
        except Exception as e:
            print(f"Error: {e}")
            
    def process_page_posts(self, post_urls):
        """Process all posts from a page concurrently."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            print("starting the executor for processing images scr from urls")
            results = executor.map(self.get_image_url, post_urls)
            combined_image_urls = set().union(*results)
        return combined_image_urls
    
    def scrape(self):
        """Main scraping method."""
        os.makedirs(self.output_folder, exist_ok=True)
        try:
            while self.max_images > 0:
                # Get post IDs from the current page
                post_urls = self.get_post_ids(self.page_number)
                image_urls = self.process_page_posts(post_urls)
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(post_urls)) as executor:
                    executor.map(
                        self.download_image,
                        zip(
                            range(self.download_idx, self.download_idx + len(post_urls)),
                            image_urls
                        )
                    )
                self.download_idx += len(post_urls)
                self.max_images -= len(post_urls)
                print(f"Download of {len(post_urls)} images is done, left {self.max_images}")
                self.page_number += 1
                
        except Exception as e:
            print(f"Error during scraping: {e}")

if __name__ == "__main__":
    
    tags = "firefly (honkai: star rail)"
    max_images = 10
    stopped_at_idx = 50 # 0 if fresh download
    page_idx = 4
    
    folder_name = re.sub(r"[(): ]", "_", tags)
    output_folder = os.path.join("danbooru_images", folder_name)
    scraper_start_time = time.time()
    scraper = DanbooruScraper(
        tags=tags,
        output_folder=output_folder,
        max_images=max_images,
        page_number=page_idx,
        download_idx=stopped_at_idx
    )
    scraper.scrape()
    scraper_end_time = time.time()
    
    print(f"the time taken to get {max_images} images is : {(scraper_end_time-scraper_start_time):.2f}")