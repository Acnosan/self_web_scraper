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
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from urllib.parse import quote
from urllib3.util.retry import Retry
import httpx

class DanbooruScraper:
    def __init__(self,tag,max_images_posts,page_idx,output_folder,file_name,stopped_at_download_idx):
        self.base_url = "https://danbooru.donmai.us"
        self.tag = tag
        self.max_images_posts = max_images_posts
        self.page_idx = page_idx
        self.output_folder = output_folder
        self.file_name = file_name
        self.stopped_at_download_idx = stopped_at_download_idx

        self.session = None

    def init_driver_service_options(self):
        options = Options()
        # Performance optimizations
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')  # Bypass OS security model, required in some environments
        options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
        #options.add_argument('--disable-gpu')  # Disable GPU hardware acceleration
        options.add_argument('--disable-infobars')  # Disable infobars
        options.add_argument('--disable-notifications')  # Disable notifications
        # Memory optimizations
        options.add_argument('--disable-logging')  # Disable logging
        options.add_argument('--disable-extensions')  # Disable extensions
        options.add_argument('--disable-popup-blocking')  # Disable popup blocking
        options.add_argument('--disable-http-cache')
        options.add_argument('--dns-prefetch-disable')
        # Anti-detection measures
        #options.add_argument('--disable-blink-features=AutomationControlled')
        #options.add_experimental_option("excludeSwitches", ["enable-automation"])
        #options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--log-level=3')  # This suppresses the DevTools message
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # 2 = Block images
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option('excludeSwitches', ['enable-logging'])  # This suppresses console logging
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service,options=options)
        return driver

    def _make_session(self):
        retry_strategy = Retry(
            total=5,  # Retry up to 5 times
            backoff_factor=1,  # Wait 1s, 2s, 4s, etc. between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
        )
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=retry_strategy
        )
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        })
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def get_post_ids(self):
        """Extract post IDs from the search page."""
        post_urls = set()
        encoded_tag = quote(self.tag)
        search_url = f"{self.base_url}/posts?tags={encoded_tag}&page={self.page_idx}"
        try:
            try:
                with httpx.Client(http2=True, timeout=30) as client:
                    response = client.get(search_url)
                    print(response.text)
            except httpx.RequestError as e:
                print(f"Connection error: {e}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://danbooru.donmai.us/"
            }
            print(f"\nAttempting to access: {search_url} : {self.page_idx}")
            response = self.session.get(search_url,headers=headers,timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors
            print(response.text)
            if response.status_code != 200:
                print(f"Received status code {response.status_code}")
                return post_urls
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all('article', class_='post-preview')
            if not articles:
                print("No articles found on this page. Check if the page structure has changed.")
                return post_urls
            for post in articles:
                if len(post_urls) >= self.max_images_posts:  # Check if we've reached the limit
                    break  # Exit the loop if we have enough posts
                post_id = post.get('data-id')
                if post_id:
                    post_urls.add(post_id)
        except requests.exceptions.ReadTimeout as e:
            print(f"Timeout error: {e}")
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error: {e}")
        except Exception as e:
            print(f"Error processing post: {e}")
        finally:
            print(f"Found {len(post_urls)} posts on page (limited by max_images, left {self.max_images_posts})")
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
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            print("starting the executor for processing images scr from urls")
            results = executor.map(self.get_image_url, post_urls)
            combined_image_urls = set().union(*results)
        return combined_image_urls
    
    def scrape(self):
        """Main scraping method."""
        os.makedirs(self.output_folder, exist_ok=True)
        try:
            if not self.session:
                self.session = self._make_session()
            post_urls = self.get_post_ids()
            if not post_urls:
                return
            #while self.max_images_posts > 0:
                # Get post IDs from the current page
                #post_urls = self.get_post_ids()
            """
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
            """
        except Exception as e:
            print(f"Error during scraping: {e}")

if __name__ == "__main__":
    tag = "acheron_(honkai:_star_rail)" 
    page_idx = 1
    max_images_posts = 5
    stopped_at_download_idx = 0
    folder_name = re.sub(r"[(): ]", "_", tag)
    # Ensure the base folder exists
    os.makedirs('scraped_datasets', exist_ok=True)
    # Create the Pixiv folder path
    danbooru_folder = os.path.join('scraped_datasets', 'danbooru_images')
    output_folder = os.path.join(danbooru_folder,folder_name)
    file_name = tag+"_img"
    
    scraper_start_time = time.time()
    scraper = DanbooruScraper(
        tag=tag,
        max_images_posts=max_images_posts,
        page_idx=page_idx,
        output_folder=output_folder,
        file_name=file_name,
        stopped_at_download_idx=stopped_at_download_idx,
    )
    scraper.scrape()
    scraper_end_time = time.time()
    
    print(f"the time taken to get {max_images_posts} images is : {(scraper_end_time-scraper_start_time):.2f}")