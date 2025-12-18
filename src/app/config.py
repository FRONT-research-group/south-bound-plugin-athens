# src/app/config.py
'''
Import configuration using .env
'''
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# # Go 3 levels up from src/app/core/config.py → project root (where .env lives)
BASE_DIR = Path(__file__).resolve().parents[
    2]  #  from src/app/core/config.py up to project root
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings(BaseSettings):
    '''
    Project Settings class
    All values should be set in .env file
    Otherwise (no-working) defaults are found here
    '''
    CAMARA_ENDPOINT_URL: str = 'edit_me_at_env_file.com'
    EAAS_APPLICATION_REPO_URL: str = 'edit_me_at_env_file.com'
    
    aeriOS_TOKEN_URL: str
    aeriOS_CLIENT_ID: str
    aeriOS_CLIENT_SECRET: str | None = None

    aeriOS_USERNAME: str
    aeriOS_PASSWORD: str
    aeriOS_SCOPE: str | None = None

    DEBUG: bool = True
    LOG_FILE: str = ".log/southbound.log"

    class Config:
        '''
        Config for Settings
        '''
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"





@lru_cache()
def get_settings():
    '''
    Get settings for something like singleton
    '''
    return Settings()


config = get_settings()
