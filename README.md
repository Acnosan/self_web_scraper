# Images Scraper specific for websites "Pixiv, Zerochan, Danbooru, Pinterest"
a web scraper made using python to facilitate the extraction and downloading of images from 3 websites currently "included in the title"

---
I made this project for personal use as a data science student so that I could use it in my data collection process.
The choice of these websites is based on the high quality images they provide.
The code is divided into sections where:
- **Folders** : contains the scrapers scripts.
- **app.py** : the main app to run which uses a GUI for non dev users.
- **requirements.txt** : the requirements to run the scrapers (go to Requirements section below to know how to use it).
- **lib_cookies.py** : a cookies manager class used mainly for websites that requires login like 'pixiv', to use it follows the Require Cookies section below.

## In Developement : unfinished versions
- Danbooru api scraper.
## In Production : finished versions
- all the rest of the scrapers.

## Require Cookies :

1. If you need to use cookies to access the desired website (in our case here its pixiv) you need to create a file called '.env'
2. in this file write PIXIV_EMAIL={your pixiv email} and below it PIXIV_PASSWORD={your pixiv password}, after you finish adding your email and pass, you can now run the pixiv scraper

## Requirements :

1. Obviously you need to have Python on your machine first
2. Dependencies : all the requirements to run all the scrapers included in the "requirements.txt", To install them use the command ```pip install -r requirements.txt```.

## How to run :
- Simply type in the command line : ```py app.py``` and a Tkinter Interface (GUI) will show up