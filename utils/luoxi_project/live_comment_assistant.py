from urllib.parse import urljoin
from loguru import logger
import traceback

from utils.common import Common

common = Common()

# Send a message to Luoxi live danmaku assistant
async def send_msg_to_live_comment_assistant(config_data: dict, msg: str):
    try:
        API_URL = urljoin(config_data["api_ip_port"], '/send_text')
        data = {
            "text": msg,
        }
        resp_json = await common.send_async_request(API_URL, "POST", data)
        return resp_json
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f"Failed to request the Luoxi live danmaku assistant API: {e}")
        return None
