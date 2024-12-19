import os
import re
import time
import json
import requests
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

PIXIV_EMAIL = os.getenv("PIXIV_EMAIL")
PIXIV_PASSWORD = os.getenv("PIXIV_PASSWORD")

class PixivScraper():
    def __init__(self,tag,max_images,page_idx,output_folder,file_name,stopped_at_download_idx):
        self.base_url = "https://www.pixiv.net/en"
        self.login_path = "https://accounts.pixiv.net/login"
        self.tag = tag
        self.max_images = max_images
        self.page_idx = page_idx
        self.output_folder = output_folder
        self.file_name = file_name
        self.stopped_at_download_idx = stopped_at_download_idx

    def init_driver_service_options(self):
        options = Options()
        #options.add_argument('--no-sandbox')  # Required for running in some environments
        #options.add_argument('--disable-dev-shm-usage')  # Overcomes limited resource problems
        #options.add_argument('--disable-gpu')  # Can help avoid some graphics-related bugs
        options.add_argument('--log-level=3')  # This suppresses the DevTools message
        options.add_experimental_option('excludeSwitches', ['enable-logging'])  # This suppresses console logging
        #options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        #options.add_argument('--disable-blink-features=AutomationControlled')
        #options.add_experimental_option("excludeSwitches", ["enable-automation"])
        #options.add_experimental_option('useAutomationExtension', False)
        # Add a realistic user agent
        #options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
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
                    print(f"Error adding specific cookie: {cookie.get('name')}: {e}")
                    continue
            #print("Cookies added Successfully")
        except Exception as e:
            print(f"Error during cookies adding to the driver : {e}")
            return False
        return True        

    def delete_cookies(self):
        cookies_path = os.path.join(os.getcwd(),"pixiv_cookies.json")
        if os.path.exists(cookies_path):
            os.remove(cookies_path)
            print("Cookies file deleted successfully")

    def create_cookies(self):
        driver = self.init_driver_service_options()
        driver.delete_all_cookies()
        driver.get(self.login_path)
        try:
            wait = WebDriverWait(driver,15)
            email_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'][style='padding-right: 8px;']"))
            )
            password_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'][style='padding-right: 36px;']"))
            )
            login_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'][height='40']"))
            )
            try:
                
                email_input.send_keys(PIXIV_EMAIL)
                password_input.send_keys(PIXIV_PASSWORD)
                login_button.click()
                print("Logged in Successfully")
            except Exception as e:
                print("Error During Passing Variables Or Login Button")
            driver.get(self.base_url)
            time.sleep(8)
            cookies = driver.get_cookies()
            if cookies:
                with open("pixiv_cookies.json", "w") as file:
                    json.dump(cookies, file)
                print(f"Saved {len(cookies)} cookies")
                return True
            else:
                print("No cookies found")
                
        except Exception as e:
            print(f"Login Problem {e}")
        driver.quit()
        return False

    def create_driver(self):
        driver = self.init_driver_service_options()
        driver.get(self.base_url)
        time.sleep(5)  # Give it time to load
        #print(f"Current URL: {driver.current_url}")
        cookies = self.load_cookies()
        if self.verify_cookies(cookies,driver):
            driver.refresh()
        
        return driver

    def extract_posts(self):
        driver = self.init_driver_service_options()
        search_url = f"{self.base_url}/tags/{self.tag}/illustrations"
        if self.page_idx > 1:
            search_url = search_url+f"?p={self.page_idx}"
        print(f"Loading Page {self.page_idx}: {search_url}")
        posts_ids = []
        try:
            driver.get(search_url)
            try:
                WebDriverWait(driver,20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='sc-rp5asc-0']"))
                )
                #print("Drive Posts Are loaded Successfully")
            except Exception as e:
                print("Exception During the Drive Waiting for Posts")
            posts = driver.find_elements(By.CSS_SELECTOR, "div[class*='sc-rp5asc-0'] > a")
            if self.stopped_at_download_idx >= int(len(posts)-1):
                self.page_idx +=1
            for post in posts:
                if len(posts_ids) >= self.max_images:
                    break
                post_id = post.get_attribute('data-gtm-value')
                #print(f"post_id found {post_id}")
                if post_id:
                    posts_ids.append(post_id)
        except Exception as e:
            print(f"Error Occured in Extract posts : {e}")
            posts_ids = None
        
        finally:
            driver.quit()
            print(f"Found {len(posts) if posts else -1} posts on page, retrieved {len(posts_ids)}, (limited by max_images which left {self.max_images} )")
        return posts,posts_ids

    def extract_srcs(self,post_id):
        driver = self.create_driver()
        images_srcs = set()
        try:
            driver.get(f"{self.base_url}/artworks/{post_id}")
            try:
                WebDriverWait(driver,10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='sc-1e1hy3c-1']"))
                )                
                #print("Drive Illustration Is loaded Successfully")
            except Exception as e:
                print("Exception During the Drive Waiting For illustration")
            images = driver.find_elements(By.CSS_SELECTOR, "img[class*='eMdOSW']")
            print(f"For {post_id}, We Got {len(images)} Images")
            for image in images:
                image_src = image.get_attribute('src')
                if image_src is None:
                    print("extract_scrs returned Nothing...")
                    break
                #print(f"post_src found {image_src}")
                #images_srcs.add(image_src)
                self.download_image(self.stopped_at_download_idx, image_src, post_id)
        except Exception as e:
            print(f"Error Occured in Extract Srcs : {e}")
            #images_srcs = None
        finally:
            driver.quit()
            return images_srcs

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
        finally:
            self.max_images -= 1
            self.stopped_at_download_idx += 1
            print(f"{image_name} Downloaded, left {self.max_images}")

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
            print("Error Occured During the Creation of Cookies, Leaving....")
            return
        try:
            while self.max_images > 0:
                print(f"Page Number: {self.page_idx}, LETS START")
                posts_ids,retrieved_posts_ids = self.extract_posts()
                if retrieved_posts_ids is None:
                    print("extract_posts returned Nothing...")
                    break
                images_srcs = self.multi_threading_extract_scrs(retrieved_posts_ids)
                print(f"{len(images_srcs)} Srcs Ready For Downloading.. !!")
                #self.multi_threading_download_images(images_srcs,posts_ids,retrieved_posts_ids)
        except Exception as e:
            print(f"Error Occured in Scrape Method : {e}")
        finally:
            print(f"Download of {self.stopped_at_download_idx} images is Fully done, left {self.max_images}")
        self.delete_cookies()

if __name__ == "__main__":
    tag = "acheron"
    page_idx = 1
    max_images = 10
    output_folder = os.path.join("pixiv_images",tag)
    file_name = tag+"img"
    stopped_at_download_idx = 0
    
    begin_time = time.time()
    scraper = PixivScraper(
        tag=tag,
        max_images=max_images,
        page_idx=1,
        output_folder=output_folder,
        file_name=file_name,
        stopped_at_download_idx=stopped_at_download_idx,
    )
    scraper.scrape()
    end_time = time.time()
    print(f"Scaper took {(end_time-begin_time):.2f} seconds")