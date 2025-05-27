import os
import time
import requests
import urllib
from selenium.webdriver import firefox,chrome,Firefox,Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

import concurrent.futures as THREAD
from datetime import datetime
from lib_cookies import PixivCookies

MAX_WORKERS_EXTRACT_SRCS = 15
MAX_WORKERS_DOWNLOAD_IMAGES = 20

class PixivScraper():

    def __init__(self,tag,max_images_posts,page_idx,output_folder,file_name,pixiv_cookies_manager):
        self.base_url = "https://www.pixiv.net/en"
        self.login_path = "https://accounts.pixiv.net/login"
        self.tag = tag
        self.max_images_posts = max_images_posts
        self.page_idx = page_idx
        self.output_folder = output_folder
        self.file_name = file_name
        self.pixiv_cookies_manager = pixiv_cookies_manager
        self.driver = None
        self.session = None

    def init_driver_service_options(self):
        options = firefox.options.Options()
        
        #options.add_argument('--headless')
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

    def extract_posts(self):
        search_url = f"{self.base_url}/tags/{self.tag}/illustrations" + (f"?p={self.page_idx}" if self.page_idx>1 else '')

        all_ids = set()
        retrieved_posts_ids = []
        url = f"https://www.pixiv.net/ajax/search/illustrations/{self.tag}"
        headers = {
            "Referer": search_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        try:
            response = requests.get(url,headers=headers)
            print(f"\nLoading on page {self.page_idx}\n")
            if response.status_code != 200:
                print(f"{response.status_code} is the status code : not 200")
                return []
            data_body = response.json()
            body = data_body.get('body',{}) 
            illust = body.get("illust",{}).get("data",[])
            for post_id in illust:
                extracted_id = post_id.get('id',None)
                if extracted_id:
                    all_ids.add(extracted_id)
            if self.max_images_posts >= len(all_ids):
                self.page_idx +=1
            for post_id in all_ids:
                if len(retrieved_posts_ids) >= self.max_images_posts:
                    break
                retrieved_posts_ids.append(post_id)
                
            print(f"Found {len(all_ids)} posts on page, retrieved {len(retrieved_posts_ids)}, (limited by max_images_posts which left {self.max_images_posts} )")
            return retrieved_posts_ids
        except Exception as e:
            print(f"Error occurred in extract_posts: {e}")
            return []

    def extract_srcs(self,post_id):
        images_srcs = []  # Ensure it's initialized
        url = f"https://www.pixiv.net/ajax/illust/{post_id}/pages"
        headers = {
            "Referer": f"https://www.pixiv.net/en/artworks/{post_id}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"{response.status_code} is the status code : not 200")
                return []
            image_src = response.json()
            body = image_src.get('body',[]) 
            for url in body:
                image_src = url.get("urls",{}).get("original","regular")  # Use "original" or other sizes if needed
                images_srcs.append((image_src, post_id))
                print(f"for post {post_id} :src {image_src}")
        except Exception as e:
            print(f"Error processing post {post_id}: {str(e)}")
        # Return a list of tuples with image URLs and the post_id
        return images_srcs

    def _make_session(self):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=30,
            pool_maxsize=60,
            max_retries=3
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        try:
            for cookie in self.pixiv_cookies_manager._wait_load_cookies():
                session.cookies.set(cookie['name'], cookie['value'])
        except Exception as e:
            print(f"Exception During Session Configuration .. {e}")
        return session
    
    def download_image(self,session,idx,image_src,post_id):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = f"{self.file_name}_{idx + 1:04d}_{timestamp}.jpg"
        image_path = os.path.join(self.output_folder, image_name)
        try:
            headers = {
                "Referer": f"{self.base_url}/artworks/{post_id}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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

    def multi_threading_download_images(self,images_srcs,posts_ids):
        print("Multi Threading Of Downloading Images BEGIN....")
        self.session = self._make_session()
        with THREAD.ThreadPoolExecutor(max_workers=MAX_WORKERS_DOWNLOAD_IMAGES) as executor:
            executor.map(
                lambda args: self.download_image(self.session, *args),
                zip(
                    range(0, len(images_srcs)),
                    images_srcs,
                    posts_ids
                )
            )

    def scrape(self):
        try:
            os.makedirs(self.output_folder,exist_ok=True)
            if not self.pixiv_cookies_manager._wait_load_cookies():
                self.driver = self.init_driver_service_options()
                is_cookies_created = self.pixiv_cookies_manager._wait_create_cookies(self.driver,self.base_url,self.login_path)
                if not is_cookies_created:
                    print(f"ERROR COOKIES DRIVER CREATION, LEAVING... {e}")
                    return

            while self.max_images_posts > 0:
                if self.max_images_posts <= 0:
                    break
                retrieved_posts_ids = self.extract_posts()
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
                except Exception as e:
                    print(f"Failed to process post after we retrieved the posts in scrap method: {e}")
                    continue
        except Exception as e:
            print(f"Error Occured in Scrape Method : {e}")
        finally:
            print(f"Finished.. Quiting Process START")