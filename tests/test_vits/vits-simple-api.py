import pygame, requests, asyncio
import logging, aiohttp, traceback
from urllib.parse import urljoin
from urllib.parse import urlencode


# Request vits APIapi
async def vits_api(self, data):
    try:
        logging.debug(f"data={data}")
        if data["type"] == "vits":
            # APIAddress "http://127.0.0.1:23456/voice/vits"
            API_URL = urljoin(data["api_ip_port"], '/voice/vits')
            data_json = {
                "text": data["content"],
                "id": data["id"],
                "format": data["format"],
                "lang": "ja",
                "length": data["length"],
                "noise": data["noise"],
                "noisew": data["noisew"],
                "max": data["max"]
            }
            
            if data["lang"] == "中文" or data["lang"] == "汉语":
                data_json["lang"] = "zh"
            elif data["lang"] == "英文" or data["lang"] == "英语":
                data_json["lang"] = "en"
            elif data["lang"] == "韩文" or data["lang"] == "韩语":
                data_json["lang"] = "ko"
            elif data["lang"] == "日文" or data["lang"] == "日语":
                data_json["lang"] = "ja"
            elif data["lang"] == "自动":
                data_json["lang"] = "auto"
            else:
                data_json["lang"] = "auto"
        elif data["type"] == "bert_vits2":
            # APIAddress "http://127.0.0.1:23456/voice/bert-vits2"
            API_URL = urljoin(data["api_ip_port"], '/voice/bert-vits2')

            data_json = {
                "text": data["content"],
                "id": data["id"],
                "format": data["format"],
                "lang": "ja",
                "length": self.get_random_float(data["length"]),
                "noise": self.get_random_float(data["noise"]),
                "noisew": self.get_random_float(data["noisew"]),
                "max": data["max"],
                "sdp_radio": self.get_random_float(data["sdp_radio"])
            }
            
            if data["lang"] == "中文" or data["lang"] == "汉语":
                data_json["lang"] = "zh"
            elif data["lang"] == "英文" or data["lang"] == "英语":
                data_json["lang"] = "en"
            elif data["lang"] == "韩文" or data["lang"] == "韩语":
                data_json["lang"] = "ko"
            elif data["lang"] == "日文" or data["lang"] == "日语":
                data_json["lang"] = "ja"
            elif data["lang"] == "自动":
                data_json["lang"] = "auto"
            else:
                data_json["lang"] = "auto"
        elif data["type"] == "gpt_sovits":
            # Request vits_simple_api APIapi gpt_sovits
            async def vits_simple_api_gpt_sovits_api(data):
                try:
                    from aiohttp import FormData

                    logging.debug(f"data={data}")
                    API_URL = urljoin(data["api_ip_port"], '/voice/gpt-sovits')


                    data_json = {
                        "text": data["content"],
                        "id": data["gpt_sovits"]["id"],
                        "format": data["gpt_sovits"]["format"],
                        "lang": data["gpt_sovits"]["lang"],
                        "segment_size": data["gpt_sovits"]["segment_size"],
                        "prompt_text": data["gpt_sovits"]["prompt_text"],
                        "prompt_lang": data["gpt_sovits"]["prompt_lang"],
                        "preset": data["gpt_sovits"]["preset"],
                        "top_k": data["gpt_sovits"]["top_k"],
                        "top_p": data["gpt_sovits"]["top_p"],
                        "temperature": data["gpt_sovits"]["temperature"]
                    }

                    # Create a FormData object
                    form_data = FormData()
                    # Add the text field
                    for key, value in data_json.items():
                        form_data.add_field(key, str(value))

                    # Open the audio file in binary read mode and add it to the form data
                    # 'reference_audio' Is the field name, which should match the name the server receives
                    form_data.add_field('reference_audio',
                                open(data["gpt_sovits"]["reference_audio"], 'rb'),
                                content_type='audio/mpeg')  # The content type is modified according to the file type
                        
                    logging.debug(f"data_json={data_json}")

                    logging.debug(f"API_URL={API_URL}")

                    async with aiohttp.ClientSession() as session:
                        async with session.post(API_URL, data=form_data, timeout=60) as response:
                            response = await response.read()
                            # print(response)
                            voice_tmp_path = 'vits_simple_api_.wav'

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
            
            voice_tmp_path = await vits_simple_api_gpt_sovits_api(data)
            return voice_tmp_path
            
        # logging.info(f"data_json={data_json}")
        # logging.info(f"data={data}")

        logging.debug(f"API_URL={API_URL}")

        url = f"{API_URL}?{urlencode(data_json)}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as response:
                response = await response.read()
                # print(response)
                voice_tmp_path = 'vits_.wav'
                with open(voice_tmp_path, 'wb') as f:
                    f.write(response)
                
                return voice_tmp_path
    except aiohttp.ClientError as e:
        logging.error(traceback.format_exc())
        logging.error(f'vitsRequest failed, please check whether your vits-simple-api is started/configured correctly, error details: {e}')
    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f'vitsUnknown error, please check whether your vits-simple-api is started/configured correctly, error details: {e}')
    
    return None


if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "type": "gpt_sovits",
        "config_path": "E:\\vits-simple-api\\Model\\ikaros\\config.json",
        "api_ip_port": "http://127.0.0.1:23456",
        "id": 1,
        "lang": "zh",
        "length": "1",
        "noise": "0.33",
        "noisew": "0.4",
        "max": "50",
        "format": "wav",
        "sdp_radio": "0.2",
        "gpt_sovits": {
            "id": 0,
            "format": "wav",
            "lang": "auto",
            "segment_size": "30",
            "reference_audio": "E:\\GitHub_pro\\AI-Vtuber\\out\\gpt_sovits_67.wav",
            "prompt_text": "所有拍到的姐妹一定不要划走",
            "prompt_lang": "auto",
            "preset": "default",
            "top_k": "5",
            "top_p": "0.8",
            "temperature": "0.9",
            "streaming": True
        },
        "content": "你好"
    }
    

    # Call the API to synthesize speech
    API_URL = urljoin(data["api_ip_port"], '/voice/gpt-sovits')


    data_json = {
        "text": data["content"],
        "id": data["gpt_sovits"]["id"],
        "format": data["gpt_sovits"]["format"],
        "lang": data["gpt_sovits"]["lang"],
        "segment_size": data["gpt_sovits"]["segment_size"],
        "prompt_text": data["gpt_sovits"]["prompt_text"],
        "prompt_lang": data["gpt_sovits"]["prompt_lang"],
        "preset": data["gpt_sovits"]["preset"],
        "top_k": data["gpt_sovits"]["top_k"],
        "top_p": data["gpt_sovits"]["top_p"],
        "temperature": data["gpt_sovits"]["temperature"]
    }

    # Create a FormData object
    form_data = FormData()
    # Add the text field
    for key, value in data_json.items():
        form_data.add_field(key, str(value))

    # Open the audio file in binary read mode and add it to the form data
    # 'reference_audio' Is the field name, which should match the name the server receives
    form_data.add_field('reference_audio',
                open(data["gpt_sovits"]["reference_audio"], 'rb'),
                content_type='audio/mpeg')  # The content type is modified according to the file type
        
    logging.debug(f"data_json={data_json}")

    logging.debug(f"API_URL={API_URL}")

    # Initializepygame
    pygame.init()

    # Request audio stream data
    url = "your_audio_stream_url"
    response = requests.get(url, stream=True)

    # Create a pygame.mixer.Sound object
    sound = pygame.mixer.Sound("1.wav")

    # Read data from the audio stream and play it
    for chunk in response.iter_content(chunk_size=1024):
        if chunk:
            sound.play(pygame.mixer.find_channel())
            pygame.time.wait(int(len(chunk) / (2 * 16000)))  # Assume the audio sample rate is16000Hz

    # Wait for audio playback to finish
    while pygame.mixer.get_busy():
        pygame.time.Clock().tick(10)

    # Exitpygame
    pygame.quit()
