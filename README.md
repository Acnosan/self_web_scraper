# Images Scraper specific for websites "Pixiv , Danbooru , Pinterest"

## a web scraper made using python to facilitate the extraction and downloading of images from 3 websites currently "included in the title"
I made this project for personal use as a data science student so that I could use it in my data collection process.
The choice of these 3 websites is based on the high quality images they provide.
The code is divided into sections where:
* **lib_cookies.py** is a cookies manager class .
* **pixiv_scraper** has two version :
### "pixiv_api_scraper.py" 
- uses pixiv api to request and get the data, processing speed is VERY FAST.
### "pixiv_webdriver_scraper.py"
- uses web driver instances to mimic a real user interaction, processing speed is VERY SLOW (it was my first attempt).
* **zerochan_api_scraper.py** uses bs4 to request and get the data, processing speed is VERY FAST. "note: no need to login, thus no cookies are required"
* **danbooru_scraper** has two version, same as pixiv one. "note: api version STILL IN PRODUCTION."
* **pinterest_scraper.py** same as the pixiv webdriver one, "note: STILL IN PRODUCTION." 

## Results :
pixiv_api and zerochan_api are the best versions here, works totally fine.

## Requirements :

1. Obviously you need to install Python on your machine first
2. Dependencies : all the requirements to run all the scrapers included in the "requirements.txt" file.
3. You can create a virtual environment and then install PIP and then use the command "pip install -r requirements.txt".