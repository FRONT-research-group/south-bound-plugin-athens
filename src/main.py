'''
# main.py
This module initializes the FastAPI application and includes the routers for the EaaS API.
'''
import json
from pydantic_settings import BaseSettings
from app import app
from app.config import config
from app.utils.logger import logger

SENSITIVE_FIELDS = {
    "aeriOS_PASSWORD",
    "aeriOS_CLIENT_SECRET",
    "aeriOS_USERNAME",
}

def masked_settings_dump(settings: BaseSettings) -> dict:
    data = settings.model_dump()
    for key in SENSITIVE_FIELDS:
        if key in data and data[key]:
            data[key] = "********"
    return data


logger.info('**EdgeCloudApplication CAMARA for aerOS started**')
pretty_settings = json.dumps(masked_settings_dump(config), indent=2)
logger.info(f"Application Configuration: {pretty_settings}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
