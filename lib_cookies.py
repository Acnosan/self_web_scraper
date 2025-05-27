import os
import json
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

PIXIV_EMAIL = os.getenv("PIXIV_EMAIL")
PIXIV_PASSWORD = os.getenv("PIXIV_PASSWORD")

class PixivCookies:
    def __init__(self):
        pass
        
    def _wait_load_cookies(self):
        try:
            cookies_path = os.path.join(os.getcwd(),"pixiv_cookies.json")
            if os.path.exists(cookies_path):
                with open("pixiv_cookies.json", "r") as file:
                    cookies = json.load(file)
                #print(f"Cookies File Is Located!")
                return cookies
            else:
                print(f"No Cookies File Is Located, Making New One..")
        except Exception as e:
            print(f"Error Loading Cookies: {e}")
        return False

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
            driver.refresh()
            return True     
        except Exception as e:
            print(f"Error during cookies adding to the driver : {e}")
            return False   

    def delete_cookies(self):
        cookies_path = os.path.join(os.getcwd(),"pixiv_cookies.json")
        if os.path.exists(cookies_path):
            os.remove(cookies_path)
            print("Cookies file deleted successfully Thus Logged Out")

    def _wait_for_auth(self,driver,login_path):
        
        driver.get(login_path)
        try:
            wait = WebDriverWait(driver,10)
            email_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'][placeholder='E-mail address or pixiv ID']"))
            )
            password_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'][placeholder='Password']"))
            )
            login_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            email_input.send_keys(PIXIV_EMAIL)
            password_input.send_keys(PIXIV_PASSWORD)
            login_button.click()
            print("Logged in Successfully")
            return True
        except Exception as e:
            print(f"Error During Passing Variables Or Login Button : {e}")
        return False
    
    def _wait_create_cookies(self,driver,base_url,login_path):
        try:
            driver.delete_all_cookies()
            if not self._wait_for_auth(driver,login_path):
                return False
            driver.get(base_url)
            cookies = driver.get_cookies()
            if cookies:
                with open("pixiv_cookies.json", "w") as file:
                    json.dump(cookies, file)
                print(f"Saved {len(cookies)} cookies")
                return True
        except Exception as e:
            pass
        return False
