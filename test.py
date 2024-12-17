from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import requests
from webdriver_manager.chrome import ChromeDriverManager

def download_image_using_selenium(image_url, file_name):
    options = Options()
    options.headless = True  # Run browser in the background
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(image_url)
        time.sleep(2)  # Wait for the image to load

        # Get the image source URL
        img_element = driver.find_element(By.TAG_NAME, "img")
        img_url = img_element.get_attribute("src")

        # Now use requests to download the image
        img_data = requests.get(img_url).content
        with open(file_name, 'wb') as file:
            file.write(img_data)
        
        print(f"Image downloaded as: {file_name}")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        driver.quit()

# Example usage
image_url = "https://cdn.donmai.us/original/47/9b/__scaramouche_and_raiden_mei_genshin_impact_and_3_more_drawn_by_carbuncly__479b6ca2b3d897e126ad8b167ac520de.jpg"
file_name = "scaramouche_raiden_mei.jpg"
download_image_using_selenium(image_url, file_name)