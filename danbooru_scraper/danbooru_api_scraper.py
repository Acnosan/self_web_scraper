import os
import re
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from selenium.webdriver import firefox,chrome,Firefox,Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
import concurrent.futures as THREAD

SAFE_WORK_RATING = "rating:general"
MAX_WORKERS_EXTRACT_SRCS = 15
MAX_WORKERS_DOWNLOAD_IMAGES = 20

class DanbooruScraper:
    def __init__(self,tag,max_images_posts,page_idx,output_folder,file_name,stopped_at_download_idx):
        self.base_url = "https://danbooru.donmai.us"
        self.tag = tag
        self.max_images_posts = max_images_posts
        self.page_idx = page_idx
        self.output_folder = output_folder
        self.file_name = file_name
        self.stopped_at_download_idx = stopped_at_download_idx
        self.driver = None
        self.session = None
        
    def init_driver_service_options(self):
        options = firefox.options.Options()
        # Performance optimizations
        options.add_argument('--headless')
        #options.add_argument('--no-sandbox')  # Bypass OS security model, required in some environments
        options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
        #options.add_argument('--disable-gpu')  # Disable GPU hardware acceleration
        options.add_argument('--disable-infobars')  # Disable infobars
        options.add_argument('--disable-notifications')  # Disable notifications
        # Memory optimizations
        options.add_argument('--disable-extensions')  # Disable extensions
        options.add_argument('--disable-popup-blocking')  # Disable popup blocking
        options.add_argument('--dns-prefetch-disable')
        options.add_argument("--window-size=1280,720")

        service = firefox.service.Service(GeckoDriverManager().install())
        driver = Firefox(service=service,options=options)
        return driver
    
    def _make_session(self):
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=30,
            pool_maxsize=60,
            max_retries=Retry(
                total=5,
                backoff_factor=2, 
                status_forcelist=[429, 443, 503, 504] 
            )
        )
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://danbooru.donmai.us',
            'Connection': 'keep-alive',
        })
        
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def get_posts_ids(self):
        """Extract post IDs from the search page."""
        post_urls = []
        tag = str(' '.join([self.tag,SAFE_WORK_RATING]))
        #search_url = f"{self.base_url}/posts?tags={self.tags}&page={self.page_idx}"
        search_url = f"{self.base_url}/posts?" + (f"page={self.page_idx}&tags={quote(tag)}" if self.page_idx > 1 else f"tags={quote(tag)}&z=5")

        self.driver.get(search_url)
        print(f"\nLoading search page {self.page_idx}: {search_url}")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".posts-container"))
        )
        try:
            print("posts container located")
            posts = self.driver.find_elements(By.TAG_NAME, "article")
            for post in posts:
                if len(post_urls) >= self.max_images_posts:  # Check if we've reached the limit
                    break  # Exit the loop if we have enough posts
                post_id = post.get_attribute('data-id')
                if post_id:
                    post_urls.append(post_id)
        except Exception as e:
                print(f"Error processing get_posts_ids {posts}: {e}")
            
        finally:
            print(f"Found {len(post_urls)} posts on page (limited by max_images, left {self.max_images_posts})")
            return post_urls

    # def get_image_src(self, post_id):
    #     image_src = []  # Ensure it's initialized
    #     search_url = f"{self.base_url}/posts/{post_id}"
    #     try:
    #         response = self.session.get(search_url)
    #         if response.status_code != 200:
    #             print(f"{response.status_code} is the status code : not 200")
    #             return []
            
    #         soup = BeautifulSoup(response.text, 'html.parser')
    #         image = soup.find("img", class_="fit-width")
    #         if image:
    #             image_src.append(image.get("src"))
    #     except Exception as e:
    #         print(f"Error processing get_images_srcs {post_id}: {str(e)}")
    #     return image_src
    def get_image_src(self, post_id):
        images_srcs = []  # Ensure it's initialized
        url = f"{self.base_url}/posts/{post_id}"
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "picture"))
            )
            # if response.status_code != 200:
            #     print(f"{response.status_code} is the status code : not 200")
            #     return []
            image_src = self.driver.find_elements(By.ID, "image")
            print(image_src)
            # soup = BeautifulSoup(response.text, 'html.parser')
            # image = soup.find("img", class_="fit-width")
            
            # if image:
            #     image_src = image.get("src")
            #     images_srcs.append((image_src,post_id))
            #     print(f"for post {post_id} :src {image_src}")
        except Exception as e:
            print(f"Error processing post {post_id}: {str(e)}")
        # Return a list of tuples with image URLs and the post_id
        return images_srcs
    
    def download_image(self,session,idx,image_src):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = f"{self.file_name}_idx_{idx + 1:04d}_{timestamp}.jpg"
        image_path = os.path.join(self.output_folder, image_name)
        #print(f"Attempting to download image {image_src} as {image_name}")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': 'https://danbooru.donmai.us',
                'Connection': 'keep-alive',
                # "Referer": f"https://www.pixiv.net/en/artworks/{post_id}",
                # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
            response = session.get(image_src,headers=headers)
            if response.status_code != 200:
                print(f"Failed to fetch image {image_src}")
                return
            response.raise_for_status() 
            try:
                with open(image_path, 'wb') as image:
                    image.write(response.content)
            except Exception as e:
                print(f"Image {image_src} Is Not Downloaded")
        except Exception as e:
            print(f"Error downloading image {image_name}:{e}")
    # def download_image(self, args):
    #     idx, image_url = args
    #     img_name = str(self.tag)+"_idx_"+str(idx+1)+".jpg"
    #     file_path = os.path.join(self.output_folder, img_name)
        
    #     try:
    #         img_data = requests.get(image_url).content
    #         with open(file_path, 'wb') as file:
    #             file.write(img_data)
    #             print(f'image {img_name} downloaded')
    #         return
    #     except Exception as e:
    #         print(f"Error: {e}")

    # def multi_threading_extract_srcs(self, posts_ids):
    #     with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    #         print("starting the executor for processing images scr from urls")
    #         results = executor.map(self.get_image_src, posts_ids)
    #     return results
    
    def multi_threading_extract_srcs(self, posts_ids):
        print("Multi Threading Of SRCs Extraction BEGIN....")
        combined_images_srcs = set()
        combined_posts_ids = []
        
        with THREAD.ThreadPoolExecutor(max_workers=MAX_WORKERS_EXTRACT_SRCS) as EXE:
            try:
                # Execute extract_srcs for each post_id and collect results
                all_results = []
                results = EXE.map(self.get_image_src, posts_ids)
                
                for result in results:
                    all_results.extend(result)
                
                # Process results while maintaining the relationship
                for img_src, post_id in all_results:
                    combined_images_srcs.add(img_src)
                    combined_posts_ids.append(post_id)
                        
            except Exception as e:
                print(f"Exception Occurred During Multi Threading Extract Srcs: {e}")
                return set(), []
        
        print(f"All Srcs Located With Total {len(combined_images_srcs)} : Combined Posts Urls : {len(combined_posts_ids)}")
        return combined_images_srcs, combined_posts_ids

    def multi_threading_download_images(self,images_srcs,posts_ids):
        print("Multi Threading Of Downloading Images BEGIN....")
        self.session = self._make_session()
        with THREAD.ThreadPoolExecutor(max_workers=MAX_WORKERS_DOWNLOAD_IMAGES) as executor:
            executor.map(
                lambda args: self.download_image(self.session, *args),
                zip(
                    range(self.stopped_at_download_idx, self.stopped_at_download_idx + len(images_srcs)),
                    images_srcs,
                    posts_ids
                )
            )

    def scrape(self):
        """Main scraping method."""
        os.makedirs(self.output_folder, exist_ok=True)
        try:
            self.driver = self.init_driver_service_options()

            while self.max_images_posts > 0:
                if self.max_images_posts <= 0:
                    break
                retrieved_posts_ids = self.get_posts_ids()
                if len(retrieved_posts_ids) == 0:
                    print("extract_posts returned nothing...")
                    break
                try:
                    images_srcs,posts_ids = self.multi_threading_extract_srcs(retrieved_posts_ids)
                    if not images_srcs:
                        print("multithreading extract srcs returned nothing...")
                        break
                    self.multi_threading_download_images(images_srcs,posts_ids)
                    self.max_images_posts -= len(retrieved_posts_ids)
                    self.stopped_at_download_idx += len(images_srcs)
                except Exception as e:
                    print(f"Failed to process post after we retrieved the posts in scrap method: {e}")
                    continue
            self.driver.quit()
        except Exception as e:
            print(f"Error Occured in Scrape Method : {e}")
        finally:
            print(f"Finished.. Quiting Process START")
        
if __name__ == "__main__":
    tag = "firefly_(honkai:_star_rail)" 
    page_idx = 1
    max_images_posts = 5
    stopped_at_download_idx = 0
    folder_name = re.sub(r"[(): ]", "_", tag)
    # Ensure the base folder exists
    os.makedirs('../scraped_datasets', exist_ok=True)
    # Create the Pixiv folder path
    danbooru_folder = os.path.join('../scraped_datasets', 'danbooru_images')
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
    
    print(f"the time taken is : {(scraper_end_time-scraper_start_time):.2f}")