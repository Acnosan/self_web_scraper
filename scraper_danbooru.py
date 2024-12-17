from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException,StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

import os
import time
import requests
import concurrent.futures
from urllib.parse import quote

class DanbooruScraper:
    def __init__(self, tags, output_folder, max_images=100):
        self.base_url = "https://danbooru.donmai.us"
        # Properly encode tags for URL
        self.tags = quote(tags.replace(' ', '_'))
        self.output_folder = output_folder
        self.max_images = max_images
        self.setup_driver()
        
    def setup_driver(self):
        options = webdriver.ChromeOptions()
        #options.add_argument("--headless")  # Uncomment to hide browser
        options.add_argument("--window-size=1920,1080")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def extract_image_urls(self, page):
        image_urls = set()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".post-preview"))
        )

        # First collect all post IDs
        posts = self.driver.find_elements(By.CSS_SELECTOR, ".post-preview")
        print(f"Found {len(posts)} posts on page {page}")
        
        post_ids = []
        for post in posts:
            try:
                post_id = post.get_attribute('data-id')
                if post_id:
                    post_ids.append(post_id)
            except StaleElementReferenceException:
                continue

        # Then visit each post page separately
        for post_id in post_ids:
            post_url = f"{self.base_url}/posts/{post_id}"
            img_url = self.get_full_image_url(post_url)
            if img_url:
                image_urls.add(img_url)
                print(f"Url Extracted Successfully: {img_url}")

        return image_urls

    
    def get_full_image_url(self, post_url):
        try:
            self.driver.get(post_url)

            # Wait for the image element to load
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "img"))
            )
            # Wait a bit longer to ensure images are loaded
            time.sleep(3)
            
            # Try targeting the post image more specifically (change the class as needed)
            img_elements = self.driver.find_elements(By.CSS_SELECTOR, "img.fit-width")

            # Check if any images are found and return the first one
            for img in img_elements:
                img_url = img.get_attribute('src')
                if img_url and "static" not in img_url:  # Avoid static images like logos
                    return img_url

            print("No post image found.")
            return None

        except Exception as e:
            print(f"Error getting full image URL: {e}")
            return None

        
    def download_image(self, args):
        idx, image_url = args
        img_name = str(self.tags)+str(idx+1)+".jpg"
        file_path = os.path.join(self.output_folder, img_name)
        
        try:
            img_data = requests.get(image_url).content
            with open(file_path, 'wb') as file:
                file.write(img_data)
            
            return f"Image downloaded as: {img_name}"
        
        except Exception as e:
            print(f"Error: {e}")
    
    def scrape(self):
        """Main scraping method."""
        os.makedirs(self.output_folder, exist_ok=True)
        
        try:
            page = 1
            image_urls = set()
            
            while len(image_urls) < self.max_images:
                # Construct and load search URL
                search_url = f"{self.base_url}/posts?tags={self.tags}&page={page}"
                print(f"Loading page {page}: {search_url}")
                self.driver.get(search_url)
                
                # Extract images from current page
                new_urls = self.extract_image_urls(page)
                if not new_urls:
                    print("No more images found on this page")
                    break
                image_urls.update(new_urls)
                if len(image_urls) >= self.max_images:
                    break
                page += 1
                
                # Check if we've reached the last page
                if "No posts found" in self.driver.page_source:
                    print("Reached the end of search results")
                    break
                
            # Convert to list and limit to max_images
            final_urls = list(image_urls)[:self.max_images]
            print(f"\nFound {len(final_urls)} unique posts. Starting download...")
            
            # Download images in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(self.download_image, enumerate(final_urls)))
            
            for result in results:
                print(result)
                
        finally:
            self.driver.quit()
            print("Scraping completed!")

if __name__ == "__main__":
    # Configuration
    tags = "acheron_(honkai:_star_rail)"  # Use underscores instead of spaces
    output_folder = os.path.join("danbooru_images", "acheron")
    max_images = 12  # Adjust this number as needed
    
    # Create and run scraper
    scraper = DanbooruScraper(
        tags=tags,
        output_folder=output_folder,
        max_images=max_images
    )
    scraper.scrape()