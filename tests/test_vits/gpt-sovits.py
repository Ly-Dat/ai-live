import logging, asyncio, aiohttp, traceback, os
from aiohttp import FormData
from urllib.parse import urlencode, urljoin

class TTS:
    def __init__(self):
        self.timeout = 60

    # Request vits_simple_api APIapi gpt_sovits
    async def vits_simple_api_gpt_sovits_api(self, data):
        try:
            logging.debug(f"data={data}")
            # APIAddress "http://127.0.0.1:5000/voice"
            API_URL = urljoin(data["api_ip_port"], '/voice/gpt-sovits')

            data_json = {
                "text": data["content"],
                "id": data["id"],
                "format": data["format"],
                "lang": data["lang"],
                "segment_size": data["segment_size"],
                "prompt_text": data["prompt_text"],
                "prompt_lang": data["prompt_lang"],
                "preset": data["preset"],
                "top_k": data["top_k"],
                "top_p": data["top_p"],
                "temperature": data["temperature"]
            }

            # Create a FormData object
            form_data = FormData()
            # Add the text field
            for key, value in data_json.items():
                form_data.add_field(key, str(value))

            # Open the audio file in binary read mode and add it to the form data
            # 'reference_audio' Is the field name, which should match the name the server receives
            form_data.add_field('reference_audio',
                        open(data["reference_audio"], 'rb'),
                        content_type='audio/mpeg')  # The content type is modified according to the file type
                
            logging.info(f"data_json={data_json}")
            # logging.info(f"data={data}")

            logging.info(f"API_URL={API_URL}")

            # url = f"{API_URL}?{urlencode(data_json)}"

            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, data=form_data, timeout=self.timeout) as response:
                    response = await response.read()
                    # print(response)
                    # file_name = 'vits_simple_api_gpt_sovits_' + self.common.get_bj_time(4) + '.wav'
                    # voice_tmp_path = self.common.get_new_audio_path(self.audio_out_path, file_name)
                    voice_tmp_path = '1.wav'
                    with open(voice_tmp_path, 'wb') as f:
                        f.write(response)
                    
                    return voice_tmp_path
        except aiohttp.ClientError as e:
            logging.error(traceback.format_exc())
            logging.error(f'vits_simple_api gpt_sovitsRequest failed, please check whether your vits_simple_api is started/configured correctly, error details: {e}')
        except Exception as e:
            logging.error(traceback.format_exc())
            logging.error(f'vits_simple_api gpt_sovitsUnknown error, please check whether your vits_simple_api is started/configured correctly, error details: {e}')
        
        return None

if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "api_ip_port": "http://127.0.0.1:23456/",
        "content": "你好,你在说什么玩意，啊啊啊啊",
        "id": 0,
        "format": "wav",
        "lang": "auto",
        "segment_size": 30,
        "reference_audio": "E:\\GitHub_pro\\AI-Vtuber\\out\\gpt_sovits_67.wav",
        "prompt_text": "所有拍到的姐妹一定不要划走",
        "prompt_lang": "auto",
        "preset": "default",
        "top_k": 5,
        "top_p": 1,
        "temperature": 1
    }
    asyncio.run(TTS().vits_simple_api_gpt_sovits_api(data))


    