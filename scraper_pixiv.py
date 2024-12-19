import os
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import concurrent.futures as THREAD

class PixivScraper():
    def __init__(self,tag,max_images,page_idx,output_folder,file_name,stopped_at_download_idx):
        self.base_url = "https://www.pixiv.net/en"
        self.tag = tag
        self.max_images = max_images
        self.page_idx = page_idx
        self.output_folder = output_folder
        self.file_name = file_name
        self.stopped_at_download_idx = stopped_at_download_idx

    def create_driver(self):
        options = Options()
        options.add_argument("--window-size=1280,720")
        options.add_argument('--log-level=3')  # This suppresses the DevTools message
        options.add_experimental_option('excludeSwitches', ['enable-logging'])  # This suppresses console logging
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service,options=options)

    def extract_posts(self):
        driver = self.create_driver()
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
                print("Drive Posts Are loaded Successfully")
            except Exception as e:
                print("Exception During the Drive Waiting for Posts")
            posts = driver.find_elements(By.CSS_SELECTOR, "div[class*='sc-rp5asc-0'] > a")
            for post in posts:
                if len(posts_ids) >= self.max_images:
                    break
                post_id = post.get_attribute('data-gtm-value')
                print(f"post_id found {post_id}")
                if post_id:
                    posts_ids.append(post_id)
        except Exception as e:
            print(f"Error Occured in Extract posts : {e}")
            posts_ids = -1
        
        finally:
            driver.quit()
            print(f"Found {len(posts_ids) if posts_ids else posts_ids} posts on page (limited by max_images which left {self.max_images} )")
        
        return posts_ids

    def extract_srcs(self,post_id):
        driver = self.create_driver()
        images_srcs = set()
        try:
            driver.get(f"{self.base_url}/artworks/{post_id}")
            try:
                WebDriverWait(driver,10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='sc-1e1hy3c-1']"))
                )                
                print("Drive Illustration Is loaded Successfully")
            except Exception as e:
                print("Exception During the Drive Waiting For illustration")
                
            image = driver.find_element(By.CSS_SELECTOR, "div[class*='gtm-expand-full-size-illust']>img")
            image_src = image.get_attribute('src')
            if image_src:
                images_srcs.add(image_src)
        except Exception as e:
            print(f"Error Occured in Extract Srcs : {e}")
        finally:
            driver.quit()
            return images_srcs

    def download_image(self,args):
        idx,image_src = args
        idx += 1
        image_name = self.file_name+"_idx_"+str(idx)+".jpg"
        image_path = os.path.join(self.output_folder,image_name)
        
        try:
            image_content = requests.get(image_src).content
            with open(image_path, 'wb') as image:
                image.write(image_content)
        except Exception as e:
            print(f"Error Occured in Download image : {e}")
        finally:
            print(f"Download of {idx} image is done, left {self.max_images}")

    def multi_threading_extract_scrs(self,posts_ids):
        with THREAD.ThreadPoolExecutor(max_workers=5) as EXE:
            print("Multi Threading Of SRCs Extraction BEGIN....")
            results = EXE.map(
                self.extract_srcs,
                posts_ids
            )
            combined_set = set().union(*results)
            return combined_set

    def multi_threading_download_images(self,images_srcs,posts_ids):
        print("Multi Threading Of SRCs Extraction BEGIN....")
        with THREAD.ThreadPoolExecutor(max_workers=5) as EXE:
            EXE.map(
                self.download_image,
                zip(
                    range(self.stopped_at_download_idx,self.stopped_at_download_idx+len(posts_ids)),
                    images_srcs
                )
            )
            self.max_images -= len(posts_ids)
            self.stopped_at_download_idx += len(posts_ids)
            self.page_idx +=1

    def scrape(self):
        os.makedirs(self.output_folder,exist_ok=True)
        
        try:
            while self.max_images > 0:
                posts_ids = self.extract_posts()
                if posts_ids == -1 or len(posts_ids) == 0:
                    print("Scrape returned Nothing...")
                    break
                images_srcs = self.multi_threading_extract_scrs(posts_ids)
                self.multi_threading_download_images(images_srcs,posts_ids)
                
        except Exception as e:
            print(f"Error Occured in Scrape Method : {e}")
        finally:
            if posts_ids == -1 or len(posts_ids) == 0:
                print("Scrape returned Nothing...")
                return
            print(f"Download of {len(images_srcs)} is Fully done, left {self.max_images}")


if __name__ == "__main__":
    tag = "acheron"
    page_idx = 1
    max_images = 5
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
        stopped_at_download_idx=stopped_at_download_idx
    )
    
    scraper.scrape()
    end_time = time.time()
    print(f"Scaper took {(end_time-begin_time):.2f} seconds")
    