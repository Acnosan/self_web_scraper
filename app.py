import tkinter as tk
from tkinter import filedialog, ttk

import time
import os
import urllib
import threading

from lib_cookies import PixivCookies
from pixiv_scraper.pixiv_api_scraper import PixivScraper
from zerochan_scraper.zerochan_api_scraper import ZeroChanScraper

def count_images_os(folder_path):
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    count = sum(1 for file in os.listdir(folder_path) if file.lower().endswith(image_extensions))
    return count

def run_scraper():
    print(f"[INFO] Starting scraper")
    print(f"Site: {site_var.get()}")
    print(f"Browser: {browser_var.get()}")
    print(f"Tag: {tag_entry.get()}")
    print(f"Images: {num_entry.get()}")
    print(f"Output directory: {output_dir.get()}")
    
    folder_name = f'{tag_entry.get()}_scraped'
    output_folder = os.path.join(output_dir.get(),folder_name)
    if site_var.get() == "Pixiv":
        begin_time = time.time()
        scraper = PixivScraper(
            tag=tag_entry.get(),
            max_images_posts=int(num_entry.get()),
            page_idx=int(page_idx.get()),
            output_folder=output_folder,
            file_name = urllib.parse.unquote(tag_entry.get()),
            pixiv_cookies_manager = PixivCookies()
        )
        scraper.scrape()
        end_time = time.time()
        print(f"Scaper took {(end_time-begin_time):.2f} seconds with final result of {count_images_os(output_folder)} images.")
    
    if site_var.get() == "Zerochan":
        begin_time = time.time()
        scraper = ZeroChanScraper(
            tag=tag_entry.get(),
            max_images_posts=int(num_entry.get()),
            page_idx=int(page_idx.get()),
            output_folder=output_folder,
            file_name = urllib.parse.unquote(tag_entry.get())
        )
        scraper.scrape()
        end_time = time.time()
        print(f"Scaper took {(end_time-begin_time):.2f} seconds with final result of {count_images_os(output_folder)} images.")
    
    
def start_thread():
    threading.Thread(target=run_scraper, daemon=True).start()

def browse_dir():
    folder_selected = filedialog.askdirectory()
    output_dir.set(folder_selected)
# 
root = tk.Tk()
root.title("Scraper UI")
root.geometry("400x500")

# Dropdowns
tk.Label(root, text="Choose Site").pack()
site_var = tk.StringVar()
ttk.Combobox(root, textvariable=site_var, values=["Pixiv", "Danbooru", "Zerochan", "Pinterest"]).pack()

tk.Label(root, text="Browser").pack()
browser_var = tk.StringVar()
ttk.Combobox(root, textvariable=browser_var, values=["Chrome", "Firefox"]).pack()

# Inputs
tk.Label(root, text="Tag").pack()
tag_entry = tk.Entry(root)
tag_entry.pack()

tk.Label(root, text="Number of Images").pack()
num_entry = tk.Entry(root)
num_entry.pack()

tk.Label(root, text="Starting Page Index").pack()
page_idx = tk.Entry(root)
page_idx.pack()

# Output directory
tk.Label(root, text="Output Directory").pack()
output_dir = tk.StringVar()
tk.Entry(root, textvariable=output_dir).pack()
tk.Button(root, text="Browse", command=browse_dir).pack()

# Start button
tk.Button(root, text="Start Scraping", command=start_thread).pack(pady=10)

root.mainloop()
