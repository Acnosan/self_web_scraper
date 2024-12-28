import os
import time
import json
import requests
import threading
import logging

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

import concurrent.futures as THREAD
from datetime import datetime
from lib_cookies import pixiv_cookies

PIXIV_EMAIL = os.getenv("PIXIV_EMAIL")
PIXIV_PASSWORD = os.getenv("PIXIV_PASSWORD")
MAX_WORKERS_EXTRACT_SRCS = 1
MAX_WORKERS_DOWNLOAD_IMAGES = 10

class PixivScraper():
    def __init__(self,tag,max_images_posts,page_idx,output_folder,file_name,stopped_at_download_idx):
        self.base_url = "https://www.pixiv.net/en"
        self.login_path = "https://accounts.pixiv.net/login"
        self.tag = tag
        self.max_images_posts = max_images_posts
        self.page_idx = page_idx
        self.output_folder = output_folder
        self.file_name = file_name
        self.stopped_at_download_idx = stopped_at_download_idx
        
        self.driver = None
        self.session = None
        self.cookies = None
        self.lock = threading.Lock()

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
        
        options.add_argument("--window-size=1280,720")
        options.add_argument('--log-level=3')  # This suppresses the DevTools message
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # 2 = Block images
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option('excludeSwitches', ['enable-logging'])  # This suppresses console logging
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service,options=options)
        return driver

    def create_driver(self):
        driver = self.init_driver_service_options()
        driver.get(self.base_url)
        self.cookies = pixiv_cookies_manager._wait_load_cookies()
        if pixiv_cookies_manager.verify_cookies(self.cookies,driver):
            print("Cookies Verified, Refreshed....")
        return driver

    def extract_posts(self):
        #self.driver = self.init_driver_service_options()
        search_url = f"{self.base_url}/tags/{self.tag}/illustrations"
        if self.page_idx > 1:
            search_url += f"?p={self.page_idx}"
        print(f"\nLoading Page {self.page_idx}: {search_url}\n")
        posts_ids = []
        try:
            self.driver.get(search_url)
            self._scroll_and_load_images()
            wait = WebDriverWait(self.driver, 10)
            posts = wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div[class*='sc-rp5asc-0'] > a")
                )
            )
            
            if self.max_images_posts >= int(len(posts)-1):
                self.page_idx +=1
                
            for post in posts:
                if len(posts_ids) >= self.max_images_posts:
                    break
                post_id = post.get_attribute('data-gtm-value')
                if post_id:
                    posts_ids.append(post_id)
            print(f"Found {len(posts)} posts on page, retrieved {len(posts_ids)}, (limited by max_images_posts which left {self.max_images_posts} )")
            #self.driver.quit()
            return posts_ids
        except Exception as e:
            print(f"Error occurred in extract_posts: {e}")
            return []

    def _open_post_tab(self, post_id):
        """Open the post in a new tab."""
        self.driver.execute_script(f"window.open('{self.base_url}/artworks/{post_id}');")
        tab_index = len(self.driver.window_handles) - 1
        self.driver.switch_to.window(self.driver.window_handles[tab_index])
        #print(f"Opened new tab for post {post_id}")

    def _wait_for_content(self):
        """Wait for the content to load and return the presentation div."""
        try:
            wait = WebDriverWait(self.driver, 7)
            return wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='presentation']"))
            )
        except Exception as e:
            print(f"Timeout waiting for content: {str(e)}")
        return False

    def _handle_show_all_button(self) -> None:
        """Click 'Show All' button if it exists."""
        try:
            self.driver.find_element(By.XPATH,"//div[text() = 'Show all']").click()
            #time.sleep(1)
            #print("'Show All' button found - Multiple image post")
        except Exception:
            #print("No 'Show All' button found - Single image post")
            pass

    def _scroll_and_load_images(self):
        try:
            for _ in range(2):  # Adjust the range based on the number of scrolls needed
                self.driver.execute_script("window.scrollBy(0, 600);")  # Scroll down
                time.sleep(1)  # Wait for new images to load
        except Exception as e:
            print(f"Error while scrolling: {e}")

    def _handle_show_all_images(self) -> None:
        try:
            wait = WebDriverWait(self.driver,5)
            return wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[role='presentation'] img "))
            )
        except Exception as e:
            print(f"Exception During Waiting For All Images To Show : {e}")
            return []

    def _process_image_src(self,post_id):
        images_srcs = set()
        images = self._handle_show_all_images()
        #print(f"Found {len(images)} images in post {post_id}")
        for idx,image in enumerate(images):
            image_src = image.get_attribute('src')
            if not image_src:
                print(f"No source found for image {idx} in post {post_id}")
                continue
            images_srcs.add(image_src)
            #print(f"{image_src} : ADDED")
        return images_srcs

    def extract_srcs(self,post_id):
        images_srcs = set()  # Ensure it's initialized
        try:
            with self.lock:
                self._open_post_tab(post_id)
                if self._wait_for_content():
                    #print("Images Content Are Present")
                    self._handle_show_all_button()
                    self._scroll_and_load_images()
                    images_srcs = self._process_image_src(post_id)
        except Exception as e:
            print(f"Error processing post {post_id}: {str(e)}")
        finally:
            with self.lock:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
        return [(src, post_id) for src in images_srcs]

    def download_image(self,session,idx,image_src,post_id):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = f"{self.file_name}_idx_{idx + 1:04d}_{timestamp}.jpg"
        image_path = os.path.join(self.output_folder, image_name)
        #print(f"Attempting to download image {image_src} as {image_name}")
        try:
            headers = {
                "Referer": f"{self.base_url}/artworks/{post_id}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = session.get(image_src,headers=headers)
            #print(f"Status code for {image_src}: {response.status_code}")
            if response.status_code != 200:
                print(f"Failed to fetch image {image_src}")
                return
            response.raise_for_status() 
            try:
                with open(image_path, 'wb') as image:
                    image.write(response.content)
                    #print(f"Image {image_src} Downloaded Successfully")
            except Exception as e:
                print(f"Image {image_src} Is Not Downloaded")
        except Exception as e:
            print(f"Error downloading image {image_name}:{e}")

    def multi_threading_extract_srcs(self, posts_ids):
        print("Multi Threading Of SRCs Extraction BEGIN....")
        combined_images_srcs = set()
        combined_posts_ids = []
        
        with THREAD.ThreadPoolExecutor(max_workers=MAX_WORKERS_EXTRACT_SRCS) as EXE:
            try:
                # Execute extract_srcs for each post_id and collect results
                all_results = []
                results = EXE.map(self.extract_srcs, posts_ids)
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

    def _make_session(self):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=3
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        try:
            cookies = self.cookies
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])
        except Exception as e:
            print(f"Exception During Session Configuration .. {e}")
        return session

    def multi_threading_download_images(self,images_srcs,posts_ids):
        print("Multi Threading Of Downloading Images BEGIN....")
        self.session = self._make_session()
        with THREAD.ThreadPoolExecutor(max_workers=MAX_WORKERS_DOWNLOAD_IMAGES) as executor:
            executor.map(
                lambda args: self.download_image(self.session, *args),
                zip(
                    range(self.stopped_at_download_idx, 
                        self.stopped_at_download_idx + len(images_srcs)),
                    images_srcs,
                    posts_ids
                )
            )

    def scrape(self):
        os.makedirs(self.output_folder,exist_ok=True)
        if not pixiv_cookies_manager._wait_load_cookies():
            self.driver = self.init_driver_service_options()
            is_cookies_created = pixiv_cookies_manager._wait_create_cookies(self.driver,self.base_url,self.login_path)
            if not is_cookies_created:
                print(f"ERROR COOKIES DRIVER CREATION, LEAVING... {e}")
                return
        try:
            self.driver = self.create_driver()
            while self.max_images_posts > 0:
                if self.max_images_posts <= 0:
                    break
                retrieved_posts_ids = self.extract_posts()
                if len(retrieved_posts_ids) == 0:
                    print("extract_posts returned Nothing...")
                    break
                try:
                    images_srcs,posts_ids = self.multi_threading_extract_srcs(retrieved_posts_ids)
                    if not images_srcs:
                        print("multithreading extract srcs returned Nothing...")
                        break
                    self.multi_threading_download_images(images_srcs,posts_ids)
                    self.max_images_posts -= len(retrieved_posts_ids)
                    self.stopped_at_download_idx += len(images_srcs)
                except Exception as e:
                    print(f"Failed to process post: {e}")
                    continue
        except Exception as e:
            print(f"Error Occured in Scrape Method : {e}")
        finally:
            try:
                print(f"Finished.. Quiting Process START")
            except:
                pass
            #pixiv_cookies_manager.delete_cookies(self.driver)
            self.driver.quit()

def count_images_os(folder_path):
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    count = sum(1 for file in os.listdir(folder_path) 
                if file.lower().endswith(image_extensions))
    return count

if __name__ == "__main__":
    tag = "raidenshogun"
    page_idx = 1
    max_images_posts = 2
    output_folder = os.path.join("pixiv_images",tag)
    file_name = tag+"img"
    stopped_at_download_idx = 0
    driver = None
    
    begin_time = time.time()
    scraper = PixivScraper(
        tag=tag,
        max_images_posts=max_images_posts,
        page_idx=page_idx,
        output_folder=output_folder,
        file_name=file_name,
        stopped_at_download_idx=stopped_at_download_idx,
    )
    pixiv_cookies_manager = pixiv_cookies()
    
    scraper.scrape()
    end_time = time.time()
    print(f"Scaper took {(end_time-begin_time):.2f} seconds with final result of {count_images_os(output_folder)} images.")
    
    
# for 104 images => 11.52 minutes
# for 119 images => 13.81 minutes
# for 254 images => 12.76 minutes
# for 723 images => 22.4 minutes
# for 1268 images => 43.35 minutes