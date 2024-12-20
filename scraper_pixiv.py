import os
import re
import time
import json
import requests
import threading
from itertools import repeat
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys

from webdriver_manager.chrome import ChromeDriverManager
import concurrent.futures as THREAD
import logging
from pathlib import Path

PIXIV_EMAIL = os.getenv("PIXIV_EMAIL")
PIXIV_PASSWORD = os.getenv("PIXIV_PASSWORD")

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
        self.lock = threading.Lock()

    def init_driver_service_options(self):
        options = Options()
        # Performance optimizations
        options.add_argument('--no-sandbox')  # Bypass OS security model, required in some environments
        #options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
        #options.add_argument('--disable-gpu')  # Disable GPU hardware acceleration
        options.add_argument('--disable-infobars')  # Disable infobars
        options.add_argument('--disable-notifications')  # Disable notifications
        
        # Memory optimizations
        options.add_argument('--disable-logging')  # Disable logging
        options.add_argument('--disable-extensions')  # Disable extensions
        options.add_argument('--disable-popup-blocking')  # Disable popup blocking
        
        # Anti-detection measures
        #options.add_argument('--disable-blink-features=AutomationControlled')
        #options.add_experimental_option("excludeSwitches", ["enable-automation"])
        #options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service,options=options)
        driver.maximize_window()
        return driver
    
    def load_cookies(self):
        cookies_path = os.path.join(os.getcwd(),"pixiv_cookies.json")
        if os.path.exists(cookies_path):
            with open("pixiv_cookies.json", "r") as file:
                cookies = json.load(file)
            return cookies

    def verify_cookies(self,cookies,driver):
        try:
            for cookie in cookies:
                # Fix cookie domain if needed
                if 'domain' not in cookie or not cookie['domain']:
                    cookie['domain'] = '.pixiv.net'
                    
                if cookie['domain'] not in driver.current_url:
                    print(f"Skipping cookie due to domain mismatch: {cookie['name']}")
                    continue  # Skip this cookie if the domain doesn't match
                # Remove problematic attributes
                cookie.pop('expiry', None)  # Sometimes expiry can cause issues
                cookie.pop('sameSite', None)  # Remove if present
                
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    logging.ERROR(f"Error adding specific cookie: {cookie.get('name')}: {e}")
                    continue
            print("Cookies added Successfully")
            return True     
        except Exception as e:
            logging.ERROR(f"Error during cookies adding to the driver : {e}")
            return False   

    def delete_cookies(self):
        cookies_path = os.path.join(os.getcwd(),"pixiv_cookies.json")
        if os.path.exists(cookies_path):
            os.remove(cookies_path)
            self.driver.quit()
            print("Cookies file deleted successfully Thus Logged Out")

    def _wait_for_auth(self,driver):
        
        driver.get(self.login_path)
        try:
            wait = WebDriverWait(driver,10)
            email_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'][style='padding-right: 8px;']"))
            )
            password_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'][style='padding-right: 36px;']"))
            )
            login_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'][height='40']"))
            )
            email_input.send_keys(PIXIV_EMAIL)
            password_input.send_keys(PIXIV_PASSWORD)
            login_button.click()
            print("Logged in Successfully")
            return True
        except Exception as e:
            logging.ERROR(f"Error During Passing Variables Or Login Button : {e}")
        return False

    def create_cookies(self):
        driver = self.init_driver_service_options()
        driver.delete_all_cookies()
        try:
            if not self._wait_for_auth(driver):
                return
            driver.get(self.base_url)
            time.sleep(2)
            cookies = driver.get_cookies()
            if cookies:
                with open("pixiv_cookies.json", "w") as file:
                    json.dump(cookies, file)
                print(f"Saved {len(cookies)} cookies")
                return True
        except Exception as e:
            print(f"Login Problem {e}")
        driver.close()
        return False

    def create_driver(self):
        driver = self.init_driver_service_options()
        driver.get(self.base_url)
        cookies = self.load_cookies()
        if self.verify_cookies(cookies,driver):
            print("Cookies Verified, Refresh....")
            driver.refresh()
        return driver

    def extract_posts(self):
        search_url = f"{self.base_url}/tags/{self.tag}/illustrations"
        if self.page_idx > 1:
            search_url += f"?p={self.page_idx}"
        print(f"Loading Page {self.page_idx}: {search_url}")
        posts_ids = []
        try:
            self.driver.get(search_url)
            wait = WebDriverWait(self.driver, 10)
            posts = wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div[class*='sc-rp5asc-0'] > a")
                )
            )
            
            if self.stopped_at_download_idx >= int(len(posts)-1):
                self.page_idx +=1
                
            for post in posts:
                if len(posts_ids) >= self.max_images_posts:
                    break
                post_id = post.get_attribute('data-gtm-value')
                if post_id:
                    posts_ids.append(post_id)
            print(f"Found {len(posts)} posts on page, retrieved {len(posts_ids)}, (limited by max_images_posts which left {self.max_images_posts} )")
            return len(posts),posts_ids
        except Exception as e:
            print(f"Error occurred in extract_posts: {e}")
            return -1, []

    def _open_post_tab(self, post_id):
        """Open the post in a new tab."""
        self.driver.execute_script(f"window.open('{self.base_url}/artworks/{post_id}');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        #driver.refresh()
        logging.info(f"Opened new tab for post {post_id}")

    def _wait_for_content(self):
        """Wait for the content to load and return the presentation div."""
        try:
            wait = WebDriverWait(self.driver, 10)
            return wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='presentation']"))
            )
        except Exception as e:
            logging.error(f"Timeout waiting for content: {str(e)}")
        return False
        
    def _handle_show_all_button(self) -> None:
        """Click 'Show All' button if it exists."""
        try:
            wait = WebDriverWait(self.driver, 5)
            show_all_button = wait.until(
                EC.presence_of_element_located((By.XPATH, "//div[text()='Show all']"))
            )
            show_all_button.click()
            logging.info("'Show All' button found - Multiple image post")
        except Exception:
            logging.info("No 'Show All' button found - single image post")

    def _process_image_src(self,post_id):
        images = self.driver.find_elements(By.CSS_SELECTOR, "div[role='presentation'] > div[class*='gtm-expand-full-size-illust'] > img ")
        logging.info(f"Found {len(images)} images in post {post_id}")
        for idx,image in enumerate(images):
            image_src = image.get_attribute('src')
            if not image_src:
                logging.warning(f"No source found for image {idx} in post {post_id}")
                continue
            self.download_image(self.stopped_at_download_idx, image_src, post_id)
            
        self.max_images_posts -= 1
        self.stopped_at_download_idx += 1
        print(f"Downloaded, left {self.max_images_posts} post's")
            
    def extract_srcs(self,post_id):
        try:
            self._open_post_tab(post_id)
            if self._wait_for_content():
                logging.info(f"The Image Content Is Present, Next Handling the Case of Show All Button Presence")
                self._handle_show_all_button()
                self._process_image_src(post_id)
                
        except Exception as e:
            logging.error(f"Error processing post {post_id}: {str(e)}")
        finally:
            try:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception as e:
                logging.error(f"Error cleaning up post {post_id}: {e}")

    def download_image(self,idx,image_src,post_id):
        #idx += 1
        image_name = self.file_name+"_idx_"+str(idx+1)+".jpg"
        image_path = os.path.join(self.output_folder,image_name)
        
        session = requests.Session()
        cookies = self.load_cookies()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        headers = {
            "Referer": f"{self.base_url}/artworks/{post_id}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            response = requests.get(image_src,headers=headers)
            response.raise_for_status() 
            if os.path.exists(image_path):
                image_name = self.file_name+"_idx__"+str(idx+1)+".jpg"
                image_path = os.path.join(self.output_folder,image_name)
            with open(image_path, 'wb') as image:
                image.write(response.content)
        except Exception as e:
            print(f"Error Occured in Download image : {e}")
            return

    def multi_threading_extract_scrs(self,posts_ids,):
        print("Multi Threading Of SRCs Extraction BEGIN....")
        with THREAD.ThreadPoolExecutor(max_workers=5) as EXE:
            results = EXE.map(
                self.extract_srcs,
                posts_ids
            )
            combined_set = set().union(*results)
            return combined_set

    def multi_threading_download_images(self,images_srcs,posts,posts_ids):
        print("Multi Threading Of Downloading Images BEGIN....")
        with THREAD.ThreadPoolExecutor(max_workers=10) as EXE:            
            EXE.map(
                self.download_image,
                zip(
                    range(self.stopped_at_download_idx,self.stopped_at_download_idx+len(posts_ids)),
                    images_srcs,
                    posts_ids
                )
            )
            #if self.stopped_at_download_idx == int(len(posts)-1):
            #    self.page_idx +=1
            #self.download_image(self.stopped_at_download_idx, images_srcs, posts_ids)

    def scrape(self):
        os.makedirs(self.output_folder,exist_ok=True)
        if not self.create_cookies():
            logging.ERROR("ERROR DRIVER CREATION, LEAVING...")
        self.driver = self.create_driver()
        try:
            while self.max_images_posts > 0:
                if self.max_images_posts <= 0:
                    break
                print(f"Page Number: {self.page_idx}, LETS START")
                posts_length,retrieved_posts_ids = self.extract_posts()
                if posts_length == -1:
                    print("extract_posts returned Nothing...")
                    break
                for post_id in retrieved_posts_ids:
                    try:
                        self.extract_srcs(post_id)
                    except Exception as e:
                        print(f"Failed to process post {post_id}: {e}")
                        continue
                #self.multi_threading_extract_scrs(retrieved_posts_ids)
                #images_srcs = self.multi_threading_extract_scrs(retrieved_posts_ids)
                #print(f"{len(images_srcs)} Srcs Ready For Downloading.. !!")
                #self.multi_threading_download_images(images_srcs,posts_ids,retrieved_posts_ids)
        except Exception as e:
            print(f"Error Occured in Scrape Method : {e}")
        finally:
            try:
                self.driver.quit()
            except:
                pass
            self.delete_cookies()

def count_images_os(folder_path):
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    count = sum(1 for file in os.listdir(folder_path) 
                if file.lower().endswith(image_extensions))
    return count

if __name__ == "__main__":
    tag = "acheron"
    page_idx = 1
    max_images_posts = 10
    output_folder = os.path.join("pixiv_images",tag)
    file_name = tag+"img"
    stopped_at_download_idx = 0
    
    begin_time = time.time()
    scraper = PixivScraper(
        tag=tag,
        max_images_posts=max_images_posts,
        page_idx=1,
        output_folder=output_folder,
        file_name=file_name,
        stopped_at_download_idx=stopped_at_download_idx,
    )
    scraper.scrape()
    end_time = time.time()
    print(f"Scaper took {(end_time-begin_time):.2f} seconds with final result of {count_images_os(output_folder)} images.")