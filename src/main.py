'''
# main.py
This module initializes the FastAPI application and includes the routers for the EaaS API.
'''
import json
from app import app
from app.config import config
from app.utils.logger import logger

logger.info('**EdgeCloudApplication CAMARA for aerOS started**')
pretty_settings = json.dumps(config.model_dump(), indent=2)
logger.info(f"Application Configuration: {pretty_settings}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
