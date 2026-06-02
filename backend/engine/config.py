import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Konfigurasi untuk Instagram Scraper"""
    
    # Instagram credentials
    IG_USERNAME = os.getenv('IG_USERNAME', '')
    IG_PASSWORD = os.getenv('IG_PASSWORD', '')
    
    # Scraping settings
    HEADLESS = os.getenv('HEADLESS', 'True').lower() == 'true'
    
    # PERBAIKAN: Proxy harus None atau dict, bukan string
    PROXY_STRING = os.getenv('PROXY', '')
    PROXY = None  # Set None jika tidak pakai proxy
    # Jika ingin pakai proxy, format seperti ini:
    # PROXY = {
    #     'server': 'http://proxy-server:8080',
    #     'username': 'user',  # opsional
    #     'password': 'pass'   # opsional
    # }
    
    MAX_POSTS = int(os.getenv('MAX_POSTS', '10'))
    DELAY_BETWEEN_REQUESTS = int(os.getenv('DELAY_BETWEEN_REQUESTS', '3'))
    
    # Paths
    RESULTS_DIR = 'results'
    LOGS_DIR = 'logs'
    
    # Instagram URLs
    IG_BASE_URL = 'https://www.instagram.com'
    
    @classmethod
    def ensure_directories(cls):
        """Buat folder jika belum ada"""
        os.makedirs(cls.RESULTS_DIR, exist_ok=True)
        os.makedirs(cls.LOGS_DIR, exist_ok=True)