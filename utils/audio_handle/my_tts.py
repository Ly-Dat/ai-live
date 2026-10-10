import asyncio
import json, os
import aiohttp, requests, ssl, asyncio
from urllib.parse import urlencode
from gradio_client import Client
import traceback
import edge_tts
from urllib.parse import urljoin
import random, copy

from utils.common import Common
from utils.my_log import logger
from utils import tts_cache, engine_stats, llm_guard
import time as _time
from utils.config import Config


# Language names accepted for the vits / bert_vits2 `lang` option -> API language code.
# Chinese names are kept as aliases so configs saved by older versions keep working.
_VITS_LANG_ALIASES = {
    "chinese": "zh", "zh": "zh", "中文": "zh", "汉语": "zh",
    "english": "en", "en": "en", "英文": "en", "英语": "en",
    "korean": "ko", "ko": "ko", "韩文": "ko", "韩语": "ko",
    "japanese": "ja", "ja": "ja", "jp": "ja", "日文": "ja", "日语": "ja",
    "auto": "auto", "自动": "auto",
}


def normalize_vits_lang(lang):
    """Map a language name (English or legacy Chinese) to the API code; unknown values mean auto-detect."""
    return _VITS_LANG_ALIASES.get(str(lang).strip().lower(), "auto")

class MY_TTS:
    def __init__(self, config_path):
        self.common = Common()
        self.config = Config(config_path)

        # Create an SSLContext object that does not verify certificates
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Get the logger of the werkzeug library
        # werkzeug_logger = logger.getLogger("werkzeug")
        # # Set the httpx logger level to WARNING
        # werkzeug_logger.setLevel(logger.WARNING)

        # Request timed out
        self.timeout = 60

        # Use internal members for config
        self.use_class_config = False
        # Back up the config
        self.class_config = copy.copy(self.config)

        try:
            self.audio_out_path = self.config.get("play_audio", "out_path")

            if not os.path.isabs(self.audio_out_path):
                if not self.audio_out_path.startswith('./'):
                    self.audio_out_path = './' + self.audio_out_path
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error("Please check the audio output path config for audio playback!!! This will affect program usage!")


    # Get a random number: a single value stays as is, a - means range data so a random value is picked, returning float data
    def get_random_float(self, data):
        # Handle non-string cases uniformly as min and max values of the same length
        if isinstance(data, str) and "-" in data:
            min, max = map(float, data.split("-"))
        else:
            min = max = float(data)
        
        # Return a random float within the specified range
        return random.uniform(min, max)

    # Base64 encoding of the audio file, pass in the file path
    def encode_audio_to_base64(self, file_path):
        import base64

        if file_path == "" or file_path is None:
            return None

        with open(file_path, "rb") as audio_file:
            audio_data = audio_file.read()
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        return encoded_audio

    async def download_audio(self, type: str, file_url: str, timeout: int=30, request_type: str="get", data=None, json_data=None, audio_suffix: str="wav"):
        async with aiohttp.ClientSession() as session:
            try:
                if request_type == "get":
                    async with session.get(file_url, params=data, timeout=timeout) as response:
                        if response.status == 200:
                            content = await response.read()
                            file_name = type + '_' + self.common.get_bj_time(4) + '.' + audio_suffix
                            voice_tmp_path = self.common.get_new_audio_path(self.audio_out_path, file_name)
                            with open(voice_tmp_path, 'wb') as file:
                                file.write(content)
                            return voice_tmp_path
                        else:
                            logger.error(f'{type} Failed to download audio: {response.status}')
                            return None
                else:
                    async with session.post(file_url, data=data, json=json_data, timeout=timeout) as response:
                        if response.status == 200:
                            content = await response.read()
                            file_name = type + '_' + self.common.get_bj_time(4) + '.' + audio_suffix
                            voice_tmp_path = self.common.get_new_audio_path(self.audio_out_path, file_name)
                            with open(voice_tmp_path, 'wb') as file:
                                file.write(content)
                            return voice_tmp_path
                        else:
                            logger.error(f'{type} Failed to download audio: {response.status}')
                            return None
            except asyncio.TimeoutError:
                logger.error("{type} Audio download timed out")
                return None

    # Request vits APIapi
    async def vits_api(self, data):
        try:
            logger.debug(f"data={data}")
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
                
                data_json["lang"] = normalize_vits_lang(data["lang"])
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
                
                data_json["lang"] = normalize_vits_lang(data["lang"])
            elif data["type"] == "gpt_sovits":
                # Request vits_simple_api APIapi gpt_sovits
                async def vits_simple_api_gpt_sovits_api(data):
                    try:
                        from aiohttp import FormData

                        logger.debug(f"data={data}")
                        url = urljoin(data["api_ip_port"], '/voice/gpt-sovits')


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
                            
                        logger.debug(f"data_json={data_json}")

                        logger.debug(f"url={url}")

                        return await self.download_audio("vits_simple_api", url, self.timeout, "post", form_data)
                    except aiohttp.ClientError as e:
                        logger.error(traceback.format_exc())
                        logger.error(f'vits_simple_api gpt_sovitsRequest failed, please check whether your vits_simple_api is started/configured correctly, error details: {e}')
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        logger.error(f'vits_simple_api gpt_sovitsUnknown error, please check whether your vits_simple_api is started/configured correctly, error details: {e}')
                    
                    return None
                
                voice_tmp_path = await vits_simple_api_gpt_sovits_api(data)
                return voice_tmp_path
                
            # logger.info(f"data_json={data_json}")
            # logger.info(f"data={data}")

            logger.debug(f"API_URL={API_URL}")

            url = f"{API_URL}?{urlencode(data_json)}"

            return await self.download_audio("vits", url, self.timeout)
        except aiohttp.ClientError as e:
            logger.error(traceback.format_exc())
            logger.error(f'vitsRequest failed, please check whether your vits-simple-api is started/configured correctly, error details: {e}')
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'vitsUnknown error, please check whether your vits-simple-api is started/configured correctly, error details: {e}')
        
        return None

    # Request bert_vits2 APIapi
    async def bert_vits2_api(self, data):
        try:
            logger.debug(f"data={data}")
            if data["type"] == "hiyori":
                # APIAddress "http://127.0.0.1:5000/voice"
                API_URL = urljoin(data["api_ip_port"], '/voice')

                data_json = {
                    "text": data["content"],
                    "model_id": data["model_id"],
                    "speaker_name": data["speaker_name"],
                    "speaker_id": data["speaker_id"],
                    "language": data["language"],
                    "length": self.get_random_float(data["length"]),
                    "noise": self.get_random_float(data["noise"]),
                    "noisew": self.get_random_float(data["noisew"]),
                    "sdp_radio": self.get_random_float(data["sdp_radio"]),
                    "auto_translate": data["auto_translate"],
                    "auto_split": data["auto_split"],
                    "emotion": data["emotion"],
                    "style_text": data["style_text"],
                    "style_weight": self.get_random_float(data["style_weight"])
                }
                
                logger.debug(f"data_json={data_json}")
                # logger.info(f"data={data}")

                logger.debug(f"API_URL={API_URL}")

                url = f"{API_URL}?{urlencode(data_json)}"

                # logger.warning(f"url={url}")

                return await self.download_audio("bert_vits2", url, self.timeout)
            elif data["type"] == "刘悦-中文特化API":
                type = data["type"]
                # APIAddress "http://127.0.0.1:5000/run/predict/"
                API_URL = urljoin(data[type]["api_ip_port"], '/tts_to_audio/')

                data_json = {
                    "text": data["content"],
                    "speaker": data[type]["speaker"],
                    "language": data["language"],
                    "length_scale": self.get_random_float(data[type]["length_scale"]),
                    "noise_scale": self.get_random_float(data[type]["noise_scale"]),
                    "noise_scale_w": self.get_random_float(data[type]["noise_scale_w"]),
                    "sdp_radio": self.get_random_float(data[type]["sdp_radio"]),
                    "cut_by_sent": data[type]["cut_by_sent"],
                    "interval_between_para": self.get_random_float(data[type]["interval_between_para"]),
                    "interval_between_sent": self.get_random_float(data[type]["interval_between_sent"]),
                    "emotion": data[type]["emotion"],
                    "style_text": data[type]["style_text"],
                    "style_weight": self.get_random_float(data[type]["style_weight"]),
                    "stream": data[type]["stream"]
                }

                logger.debug(f"data_json={data_json}")
                # logger.info(f"data={data}")

                logger.debug(f"API_URL={API_URL}")

                return await self.download_audio("bert_vits2", API_URL, self.timeout, "post", json_data=data_json)
        except aiohttp.ClientError as e:
            logger.error(traceback.format_exc())
            logger.error(f'bert_vits2Request failed, please check whether your bert_vits2 api is started/configured correctly, error details: {e}')
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'bert_vits2Unknown error, please check whether your bert_vits2 api is started/configured correctly, error details: {e}')
        
        return None
    
    # Request the VITS fast API to get the path of the synthesized audio
    def vits_fast_api(self, data):
        try:
            # APIAddress
            API_URL = urljoin(data["api_ip_port"], '/run/predict/')

            data_json = {
                "fn_index":0,
                "data":[
                    "こんにちわ。",
                    "ikaros",
                    "日本語",
                    1
                ],
                "session_hash":"mnqeianp9th"
            }

            data_json["data"] = [data["content"], data["character"], data["language"], data["speed"]]

            logger.debug(f'data_json={data_json}')

            response = requests.post(url=API_URL, json=data_json, timeout=self.timeout)
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            file_path = ret["data"][1]["name"]

            new_file_path = self.common.move_file(file_path, os.path.join(self.audio_out_path, 'vits_fast_' + self.common.get_bj_time(4)), 'vits_fast_' + self.common.get_bj_time(4))

            return new_file_path
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'vits-fastError, please check whether your vits-fast inference program is started/configured correctly, error details: {e}')
            return None
    

    # Request the Edge-TTS API to get the path of the synthesized audio
    async def edge_tts_api(self, data):
        try:
            file_name = 'edge_tts_' + self.common.get_bj_time(4) + '.mp3'
            voice_tmp_path = self.common.get_new_audio_path(self.audio_out_path, file_name)
            # voice_tmp_path = './out/' + self.common.get_bj_time(4) + '.mp3'
            # Filter" 'Character
            data["content"] = data["content"].replace('"', '').replace("'", '')

            t0 = _time.time()
            ck = None
            if llm_guard.tts_cache_enabled():
                ck = tts_cache.key("edge", data["content"], {k: data["edge-tts"].get(k) for k in ("voice", "rate", "volume")})
                hit = tts_cache.lookup(ck, ".mp3", voice_tmp_path)
                if hit:
                    engine_stats.record("tts", (_time.time() - t0) * 1000, cached=True)
                    return hit

            proxy = data["edge-tts"]["proxy"] if data["edge-tts"]["proxy"] != "" else None

            # Use Edge TTS to generate the voice file for the reply message
            communicate = edge_tts.Communicate(
                text=data["content"], 
                voice=data["edge-tts"]["voice"], 
                rate=data["edge-tts"]["rate"], 
                volume=data["edge-tts"]["volume"], 
                proxy=proxy
            )
            await communicate.save(voice_tmp_path)

            engine_stats.record("tts", (_time.time() - t0) * 1000)
            tts_cache.store(ck, ".mp3", voice_tmp_path)
            return voice_tmp_path
        except Exception as e:
            engine_stats.record("tts", 0, ok=False, error=str(e))
            logger.error(traceback.format_exc())
            logger.error(e)
            return None
    

    async def vieneu_tts_api(self, data):
        """VieNeu-TTS (free, local). Falls back to edge-tts when the VieNeu server is not reachable,
        so the stream never goes silent."""
        try:
            from utils import vieneu_tts
            file_name = 'vieneu_' + self.common.get_bj_time(4) + '.wav'
            out_path = self.common.get_new_audio_path(self.audio_out_path, file_name)
            t0 = _time.time()
            ck = None
            if llm_guard.tts_cache_enabled():
                ck = tts_cache.key("vieneu", data["content"], data.get("vieneu"))
                hit = tts_cache.lookup(ck, ".wav", out_path)
                if hit:
                    engine_stats.record("tts", (_time.time() - t0) * 1000, cached=True)
                    return hit
            path = await asyncio.to_thread(vieneu_tts.synthesize, data["content"], data["vieneu"], out_path)
            if path:
                engine_stats.record("tts", (_time.time() - t0) * 1000)
                tts_cache.store(ck, ".wav", path)   # only VieNeu's own audio; the edge-tts fallback below is never cached under this key
                return path
            logger.warning("VieNeu server not reachable or returned no audio; falling back to edge-tts")
            if data.get("edge-tts"):
                return await self.edge_tts_api({"content": data["content"], "edge-tts": data["edge-tts"]})
            return None
        except Exception:
            logger.error(traceback.format_exc())
            return None

    # Request OpenAI_TTS APIapi
    def openai_tts_api(self, data):
        try:
            if data["type"] == "huggingface":
                client = Client(data["api_ip_port"])
                result = client.predict(
                    data["content"],	# str in 'Text' Textbox component
                    data["model"],	# Literal[tts-1, tts-1-hd]  in 'Model' Dropdown component
                    data["voice"],	# Literal[alloy, echo, fable, onyx, nova, shimmer]  in 'Voice Options' Dropdown component
                    data["api_key"],	# str  in 'OpenAI API Key' Textbox component
                    api_name="/tts_enter_key"
                )

                new_file_path = self.common.move_file(result, os.path.join(self.audio_out_path, 'openai_tts_' + self.common.get_bj_time(4)), 'openai_tts_' + self.common.get_bj_time(4), "mp3")

                return new_file_path
            elif data["type"] == "api":
                from openai import OpenAI
                
                client = OpenAI(api_key=data["api_key"], base_url=data['api_ip_port'])

                response = client.audio.speech.create(
                    model=data["model"],
                    voice=data["voice"],
                    input=data["content"]
                )

                file_name = 'openai_tts_' + self.common.get_bj_time(4) + '.mp3'
                voice_tmp_path = self.common.get_new_audio_path(self.audio_out_path, file_name)

                response.stream_to_file(voice_tmp_path)

                return voice_tmp_path
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'OpenAI_TTSRequest failed: {e}')
            return None

    # Request gradio APIapi
    def gradio_tts_api(self, data):
        def get_value_by_index(response, index):
            try:
                # Make sure the response is a tuple or list and the index is in range
                if isinstance(response, (tuple, list)) and index < len(response):
                    return response[index]
                else:
                    return None
            except IndexError:
                logger.error(traceback.format_exc())
                # Index out of range
                return None

        def get_file_path(data):
            try:
                url = data.pop('url')  # Get and removeURL
                fn_index = data.pop('fn_index')  # Get and remove the function index
                data_analysis = data.pop('data_analysis')

                client = Client(url)

                # dataA dict containing all required parameters
                data_values = list(data.values())
                result = client.predict(fn_index=fn_index, *data_values)

                logger.debug(result)

                if isinstance(result, (tuple, list)):
                    # Get the element at index 1
                    file_path = get_value_by_index(result, int(data_analysis))

                    if file_path:
                        logger.debug(f"File path:{file_path}")
                        return file_path
                elif isinstance(result, str):
                    logger.debug(f"File path:{result}")
                    return result
                else:
                    logger.error("Data parsing failed!Invalid index or response format.")
                    return None
            except Exception as e:
                logger.error(traceback.format_exc())
                # Index out of range
                return None

        logger.debug(f"data={data}")
        data_str = data["request_parameters"]
        formatted_data_str = data_str.format(content=data["content"])
        data_json = json.loads(formatted_data_str)

        file_path = get_file_path(data_json)

        new_file_path = self.common.move_file(file_path, os.path.join(self.audio_out_path, 'gradio_tts_' + self.common.get_bj_time(4)), 'gradio_tts_' + self.common.get_bj_time(4))

        return new_file_path


    async def gpt_sovits_api(self, data):
        import base64
        import mimetypes
        import websockets
        import asyncio

        def file_to_data_url(file_path):
            # Determine the MIME type from the file extension
            mime_type, _ = mimetypes.guess_type(file_path)

            # Read the file content
            with open(file_path, "rb") as file:
                file_content = file.read()

            # Convert to Base64 encoding
            base64_encoded_data = base64.b64encode(file_content).decode('utf-8')

            # Construct the full Data URL
            return f"data:{mime_type};base64,{base64_encoded_data}"

               
        try:
            logger.debug(f"data={data}")
            
            if data["type"] == "gradio_0322":
                client = Client(data["gradio_ip_port"])
                voice_tmp_path = client.predict(
                    data["content"],	# str  in 'Text to synthesize' Textbox component
                    data["api_0322"]["text_lang"],	# Literal['Chinese', 'English', 'Japanese', 'Chinese-English mix', 'Japanese-English mix', 'Multilingual mix']  in 'Language to synthesize' Dropdown component
                    data["api_0322"]["ref_audio_path"],	# filepath  in 'Please upload a reference audio of 3-10 seconds, longer will cause an error!' Audio component
                    data["api_0322"]["prompt_text"],	# str  in 'Text of the reference audio' Textbox component
                    data["api_0322"]["prompt_lang"],	# Literal['Chinese', 'English', 'Japanese', 'Chinese-English mix', 'Japanese-English mix', 'Multilingual mix']  in 'Language of the reference audio' Dropdown component
                    data["api_0322"]["top_k"],	# float (numeric value between 1 and 100) in 'top_k' Slider component
                    data["api_0322"]["top_p"],	# float (numeric value between 0 and 1) in 'top_p' Slider component
                    data["api_0322"]["temperature"],	# float (numeric value between 0 and 1) in 'temperature' Slider component
                    data["api_0322"]["text_split_method"],	# Literal['No split', 'Split when reaching four sentences', 'Split when reaching 50 characters', 'Split at Chinese full stop', 'Split at English period', 'Split by punctuation']  in 'How to split' Radio component
                    int(data["api_0322"]["batch_size"]),	# float (numeric value between 1 and 200) in 'batch_size' Slider component
                    float(data["api_0322"]["speed_factor"]),	# float (numeric value between 0.25 and 4) in 'speed_factor' Slider component
                    data["api_0322"]["split_bucket"],	# bool  in 'Enable no-reference-text mode. Leaving the reference text empty also enables it.' Checkbox component
                    data["api_0322"]["return_fragment"],	# bool  in 'Data bucketing (may reduce computation slightly, just pick it)' Checkbox component
                    data["api_0322"]["fragment_interval"],	# float (numeric value between 0.01 and 1) in 'Segment interval (seconds)' Slider component
                    api_name="/inference"
                )
                if voice_tmp_path:
                    new_file_path = self.common.move_file(voice_tmp_path, os.path.join(self.audio_out_path, 'gpt_sovits_' + self.common.get_bj_time(4)), 'gpt_sovits_' + self.common.get_bj_time(4))

                return new_file_path
            elif data["type"] == "api":
                try:
                    data_json = {
                        "refer_wav_path": data["ref_audio_path"],
                        "prompt_text": data["prompt_text"],
                        "prompt_language": data["prompt_language"],
                        "text": data["content"],
                        "text_language": data["language"]
                    }
                                        
                    return await self.download_audio("gpt_sovits", data["api_ip_port"], self.timeout, "post", None, data_json)
                except aiohttp.ClientError as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsRequest failed: {e}')
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsUnknown error: {e}')
            elif data["type"] == "api_0322":
                try:

                    data_json = {
                        "text": data["content"],
                        "text_lang": data["api_0322"]["text_lang"],
                        "ref_audio_path": data["api_0322"]["ref_audio_path"],
                        "prompt_text": data["api_0322"]["prompt_text"],
                        "prompt_lang": data["api_0322"]["prompt_lang"],
                        "top_k": data["api_0322"]["top_k"],
                        "top_p": data["api_0322"]["top_p"],
                        "temperature": data["api_0322"]["temperature"],
                        "text_split_method": data["api_0322"]["text_split_method"],
                        "batch_size":int(data["api_0322"]["batch_size"]),
                        "speed_factor":float(data["api_0322"]["speed_factor"]),
                        "split_bucket":data["api_0322"]["split_bucket"],
                        "return_fragment":data["api_0322"]["return_fragment"],
                        "fragment_interval":data["api_0322"]["fragment_interval"],
                    }
                                        
                    return await self.download_audio("gpt_sovits", data["api_ip_port"], self.timeout, "post", None, data_json)
                except aiohttp.ClientError as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsRequest failed: {e}')
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsUnknown error: {e}')
            elif data["type"] == "api_0706":
                try:

                    data_json = {
                        "text": data["content"],
                        "refer_wav_path": data["api_0706"]["refer_wav_path"],
                        "text_language": data["api_0706"]["text_language"],
                        "prompt_text": data["api_0706"]["prompt_text"],
                        "prompt_language": data["api_0706"]["prompt_language"],
                        "cut_punc": data["api_0706"]["cut_punc"],
                    }
                                        
                    return await self.download_audio("gpt_sovits", data["api_ip_port"], self.timeout, "post", None, data_json)
                except aiohttp.ClientError as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsRequest failed: {e}')
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsUnknown error: {e}')
            elif data["type"] == "v2_api_0821":
                try:
                    data_json = {
                        "text": data["content"],
                        "text_lang": data[data["type"]]["text_lang"],
                        "ref_audio_path": data[data["type"]]["ref_audio_path"],
                        "aux_ref_audio_paths": data[data["type"]]["aux_ref_audio_paths"],
                        "prompt_text": data[data["type"]]["prompt_text"],
                        "prompt_lang": data[data["type"]]["prompt_lang"],
                        "top_k": int(data[data["type"]]["top_k"]),
                        "top_p": float(data[data["type"]]["top_p"]),
                        "temperature": float(data[data["type"]]["temperature"]),
                        "text_split_method": data[data["type"]]["text_split_method"],
                        "batch_size": int(data[data["type"]]["batch_size"]),
                        "split_bucket": data[data["type"]]["split_bucket"],
                        "speed_factor": float(data[data["type"]]["speed_factor"]),
                        "fragment_interval": float(data[data["type"]]["fragment_interval"]),
                        "seed": int(data[data["type"]]["seed"]),
                        "media_type": data[data["type"]]["media_type"],
                        "streaming_mode": data[data["type"]]["streaming_mode"],
                        "parallel_infer": data[data["type"]]["parallel_infer"],
                        "repetition_penalty": float(data[data["type"]]["repetition_penalty"]),
                    }

                    API_URL = urljoin(data["api_ip_port"], '/tts')

                    return await self.download_audio("gpt_sovits", API_URL, self.timeout, "post", None, data_json)
                except aiohttp.ClientError as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsRequest failed: {e}')
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsUnknown error: {e}')
            
            elif data["type"] == "webtts":
                try:
                    # Use a dict comprehension to build the params dict, containing only non-empty string values
                    params = {
                        key: value
                        for key, value in data["webtts"].items()
                        if value != ""
                        if key != "api_ip_port"
                    }

                    params["speed"] = self.get_random_float(params["speed"])
                    params["text"] = data["content"]

                    if params["version"] in ["1", "2"]:
                        return await self.download_audio("gpt_sovits", data["webtts"]["api_ip_port"], self.timeout, "get", params)
                    elif params["version"] == "1.4":
                        async with aiohttp.ClientSession() as session:
                            async with session.get(data["webtts"]["api_ip_port"], params=params, timeout=self.timeout) as response:
                                resp_json = await response.json()

                                url = urljoin(data["webtts"]["api_ip_port"], resp_json['url'])

                                return await self.download_audio("gpt_sovits", url, self.timeout, "get", params)
                except aiohttp.ClientError as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsRequest failed: {e}')
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'gpt_sovitsUnknown error: {e}')
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'gpt_sovitsUnknown error, please check whether your gpt_sovits inference is started/configured correctly, error details: {e}')
        
        return None


    def azure_tts_api(self, data):
        """Call the Azure TTS API to synthesize audio and return the audio path

        Args:
            data (dict): JSONData

        Returns:
            str: Audio path
        """
        try:
            import azure.cognitiveservices.speech as speechsdk

            file_name = 'azure_tts_' + self.common.get_bj_time(4) + '.wav'
            voice_tmp_path = self.common.get_new_audio_path(self.audio_out_path, file_name)
            
            # Create the speech config object using the Azure subscription key and service region
            speech_config = speechsdk.SpeechConfig(subscription=self.config.get("azure_tts", "subscription_key"), region=self.config.get("azure_tts", "region"))
            speech_config.speech_synthesis_voice_name = self.config.get("azure_tts", "voice_name")

            # Create the audio config object, specifying the output audio file path
            audio_config = speechsdk.audio.AudioOutputConfig(filename=voice_tmp_path)

            # Create the speech synthesizer object
            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

            # Perform text-to-speech conversion
            result = speech_synthesizer.speak_text_async(data["content"]).get()

            # Check the result
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.debug(f"Audio successfully saved to: {voice_tmp_path}")
                return voice_tmp_path
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logger.error(f"Text-to-speech canceled: {str(cancellation_details.reason)}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    if cancellation_details.error_details:
                        logger.error(f"Error details: {str(cancellation_details.error_details)}")

                return None
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'azure_ttsUnknown error: {e}')

            return None
        

    # CosyVoice (gradio_client-0.16.4, version too old to use meow)
    async def cosyvoice_api(self, data):
        """CosyVoice GradioAPI integration meow

        Args:
            data (dict): Parameter data meow

        Returns:
            str: Audio path
        """
        try:
            if data["type"] == "gradio_0707":
                from gradio_client import Client, file

                client = Client(data["gradio_ip_port"])

                if data["gradio_0707"]["prompt_wav_upload"] == "":
                    prompt_wav_upload = None
                else:
                    prompt_wav_upload = file(data["gradio_0707"]["prompt_wav_upload"])

                result = client.predict(
                    tts_text=data["content"] + "。",
                    mode_checkbox_group=data["gradio_0707"]["mode_checkbox_group"],
                    sft_dropdown=data["gradio_0707"]["sft_dropdown"],
                    prompt_text=data["gradio_0707"]["prompt_text"],
                    prompt_wav_upload=prompt_wav_upload,
                    prompt_wav_record=None,
                    instruct_text=data["gradio_0707"]["instruct_text"],
                    seed=int(data["gradio_0707"]["seed"]),
                    api_name="/generate_audio"
                )

                new_file_path = None

                if result:
                    voice_tmp_path = result
                    new_file_path = self.common.move_file(voice_tmp_path, os.path.join(self.audio_out_path, 'cosyvoice_' + self.common.get_bj_time(4)), 'cosyvoice_' + self.common.get_bj_time(4))

                return new_file_path
            elif data["type"] == "api_0819":
                url = data["api_ip_port"]

                params = {
                    "text": data["content"],
                    "speaker": data["api_0819"]["speaker"],
                    'new': int(data["api_0819"]["new"]),
                    'speed': float(data["api_0819"]["speed"]),
                    'streaming': int(data["api_0819"]["streaming"])
                }

                logger.debug(f"params={params}")

                try:
                    return await self.download_audio("cosyvoice", url, self.timeout, request_type="post", json_data=params)
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.error(f'cosyvoiceUnknown error, please check whether your CosyVoice API is started/configured correctly, error details: {e}')
                
                return None
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'CosyVoiceUnknown error, please check whether your CosyVoice WebUI is started/configured correctly, error details: {e}')
        
        return None

    # F5-TTS (gradio_client-1.4.2, version too old to use meow)
    async def f5_tts_api(self, data):
        """F5-TTS GradioAPI integration meow

        Args:
            data (dict): Parameter data meow

        Returns:
            str: Audio path
        """
        try:
            if data["type"] == "gradio_1023":
                from gradio_client import Client, handle_file

                client = Client(data["gradio_ip_port"])

                result = client.predict(
                    ref_audio_orig=handle_file(data["ref_audio_orig"]),
                    ref_text=data["ref_text"],
                    gen_text=data["content"],
                    model=data["model"],
                    remove_silence=data["remove_silence"],
                    cross_fade_duration=float(data["cross_fade_duration"]),
                    speed=float(data["speed"]),
                    api_name="/infer"
                )

                new_file_path = None

                if result:
                    voice_tmp_path = result[0]
                    new_file_path = self.common.move_file(voice_tmp_path, os.path.join(self.audio_out_path, 'f5_tts_' + self.common.get_bj_time(4)), 'f5_tts_' + self.common.get_bj_time(4))

                return new_file_path
            
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'F5-TTSUnknown error, please check whether your F5-TTS WebUI is started/configured correctly, error details: {e}')
        
        return None

    async def multitts_api(self, data):
        try:
            # http://127.0.0.1:8774/forward
            API_URL = urljoin(data["multitts"]["api_ip_port"], "/forward")

            data_json = {
                "text": data["content"],
                "speed": int(data["multitts"]["speed"]),
                "volume": int(data["multitts"]["volume"]),
                "pitch": int(data["multitts"]["pitch"])
            }

            if data["multitts"]["voice"] != "":
                data_json["voice"] = data["multitts"]["voice"]
                
            logger.debug(f"data_json={data_json}")
            logger.debug(f"url={API_URL}")

            return await self.download_audio("multitts", API_URL, self.timeout, "get", data_json)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'MultiTTSUnknown error, please check whether your MultiTTS API service is started and the config/network is correct, error details: {e}')
        
        return None

    
    async def melotts_api(self, data):
        try:
            API_URL = urljoin(data["melotts"]["api_ip_port"], "/tts")

            data_json = {
                "text": data["content"],
                "speaker_id": int(data["melotts"]["speaker_id"]),
                "sdp_ratio": float(data["melotts"]["sdp_ratio"]),
                "noise_scale": float(data["melotts"]["noise_scale"]),
                "noise_scale_w": float(data["melotts"]["noise_scale_w"]),
                "speed": float(data["melotts"]["speed"]),
            }
                
            logger.debug(f"data_json={data_json}")
            logger.debug(f"url={API_URL}")

            return await self.download_audio("melotts", API_URL, self.timeout, "post", json_data=data_json)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'MeloTTSUnknown error, please check whether your MeloTTS API service is started and the config/network is correct, error details: {e}')
        
        return None

    # Index-tts
    async def index_tts_api(self, data):
        """Index-tts APIIntegration meow

        Args:
            data (dict): Parameter data meow

        Returns:
            str: Audio path
        """
        try:
            url = f"{data['index_tts']['api_ip_port']}/tts"
            
            # Create a FormData object for the multipart/form-data request
            from aiohttp import FormData
            form_data = FormData()
            
            # Add the text parameter
            form_data.add_field('text', data["content"])
            
            # Add the temperature parameter
            form_data.add_field('temperature', str(data['index_tts']["temperature"]))
            
            # Add the audio file
            form_data.add_field(
                'prompt_audio',
                open(data['index_tts']["prompt_audio"], 'rb'),
                filename=os.path.basename(data['index_tts']["prompt_audio"]),
                content_type='audio/wav'
            )
            
            logger.debug(f"Index-tts Request parameters: text={data['content']}, temperature={data['index_tts']['temperature']}")
            
            try:
                return await self.download_audio("index_tts", url, self.timeout, request_type="post", data=form_data)
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error(f'Index-tts API Error, please check whether your Index-tts API is started/configured correctly, error details: {e}')

            return None
            
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'Index-ttsUnknown error, please check whether your Index-tts API is started/configured correctly, error details: {e}')
        
        return None
