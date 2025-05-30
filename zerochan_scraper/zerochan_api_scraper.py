import os
import time
import json
import requests
import concurrent.futures as THREAD
from datetime import datetime
from bs4 import BeautifulSoup
from tqdm import tqdm
from threading import Lock
from urllib3.util.retry import Retry

MAX_WORKERS_EXTRACT_SRCS = 10
MAX_WORKERS_DOWNLOAD_IMAGES = 10
# CAUSE HERE WE WILL HAVE TWO PROCESSES THAT USES THREADS TOTAL IS 20 SO MAX POOL SIZE > 20

class ZeroChanScraper():

    def __init__(self,tag,max_images_posts,page_idx,output_folder,file_name):
        self.base_url = "https://www.zerochan.net"
        self.tag = tag
        self.max_images_posts = max_images_posts
        self.page_idx = page_idx
        self.output_folder = output_folder
        self.file_name = file_name
        self.session = None
        self.progress_bar = None
        self.lock = Lock()

    def _make_session(self):
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=25,
            pool_maxsize=25,
            max_retries=Retry(
                total=4,
                backoff_factor=1,  # Wait: 1s, 2s, 4s, etc.
                status_forcelist=[503]
            )
        )
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer":  self.base_url
        })
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def extract_posts(self):
        search_url = f"{self.base_url}/{self.tag}" + (f"?p={self.page_idx}" if self.page_idx>1 else '')
        all_ids = set()
        retrieved_posts_ids = []
        try:
            response = self.session.get(search_url)
            if response.status_code != 200:
                print(f"{response.status_code} is the status code : not 200")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            posts_section = soup.find('ul', class_='medium-thumbs')
            if not posts_section:
                print("No posts container found")
                return []
            posts_ids = posts_section.find_all('li')
            for post in posts_ids:
                extracted_id = post.get('data-id')
                if extracted_id:
                    all_ids.add(extracted_id)
            if self.max_images_posts >= len(all_ids):
                self.page_idx +=1
            retrieved_posts_ids = list(all_ids)[:self.max_images_posts]
            
            return retrieved_posts_ids
        except Exception as e:
            print(f"Error occurred in extract_posts: {e}")
            return []

    def extract_srcs(self,post_id):
        images_srcs = [] 
        search_url = f"https://www.zerochan.net/{post_id}"
        try:
            response = self.session.get(search_url)
            if response.status_code != 200:
                print(f"{response.status_code} is the status code : not 200")
                return []
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find("script", type="application/ld+json")
            image_src = json.loads(script_tag.string).get("contentUrl")
            #print(f"{post_id} : {image_src}")
            images_srcs.append((image_src, post_id))
        except Exception as e:
            print(f"Error processing post {post_id}: {str(e)}")

        return images_srcs

    def download_image(self,session,idx,image_src,post_id):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = f"{self.file_name}_{idx + 1:04d}_{timestamp}.jpg"
        image_path = os.path.join(self.output_folder, image_name)
        try:
            headers = {
                "Referer": f"{self.base_url}/{post_id}",
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
                with self.lock:
                    self.progress_bar.update(1)
                    time.sleep(0.0005)
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
                all_results = []
                results = EXE.map(self.extract_srcs, posts_ids)
                
                for result in results:
                    all_results.extend(result)
                
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
        os.makedirs(self.output_folder,exist_ok=True)
        try:
            self.progress_bar = tqdm(
                total=self.max_images_posts,
                desc="Scraping Images",
                unit="Image",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                colour='red',
                leave=True
            )
            while self.max_images_posts > 0:
                if self.max_images_posts <= 0:
                    break
                self.session = self._make_session()
                retrieved_posts_ids = self.extract_posts()
                if len(retrieved_posts_ids) == 0:
                    print("extract_posts returned nothing...")
                    break
                try:
                    images_srcs,posts_ids= self.multi_threading_extract_srcs(retrieved_posts_ids)
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