import hashlib
import random
import string
import logging, asyncio, aiohttp, json
import websockets

def generate_session_hash(length=11):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for i in range(length))
    hash_object = hashlib.sha1(random_string.encode())
    session_hash = hash_object.hexdigest()[:length]
    return session_hash

# session_hash = generate_session_hash()

async def download_audio(type, file_url, timeout):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(file_url, timeout=timeout) as response:
                if response.status == 200:
                    content = await response.read()
                    # file_name = '_' + self.common.get_bj_time(4) + '.wav'
                    # voice_tmp_path = self.common.get_new_audio_path(audio_out_path, file_name)
                    voice_tmp_path = "2.wav"
                    with open(voice_tmp_path, 'wb') as file:
                        file.write(content)
                    return voice_tmp_path
                else:
                    logging.error(f'{type} Failed to download audio: {response.status}')
                    return None
        except asyncio.TimeoutError:
            logging.error("{type} Audio download timed out")
            return None

async def fish_speech_web_api(data):
    session_hash = generate_session_hash()

    async def websocket_client(data_json):
        try:
            async with websockets.connect("wss://fs.firefly.matce.cn/queue/join") as websocket:
                # Set the maximum connection time (e.g. 30 seconds)
                return await asyncio.wait_for(websocket_client_logic(websocket, data_json), timeout=30)
        except asyncio.TimeoutError:
            logging.error("gpt_sovits WebSocketConnection timed out")
            return None

    async def websocket_client_logic(websocket, data_json):
        async for message in websocket:
            logging.debug(f"Received message: {message}")

            # Parse the received message
            data = json.loads(message)
            # Check whether it is the expected message
            if "msg" in data:
                if data["msg"] == "send_hash":
                    # Send the response message
                    response = json.dumps({"session_hash":session_hash,"fn_index":3})
                    await websocket.send(response)
                    logging.debug(f"Sent message: {response}")
                elif data["msg"] == "send_data":
                    # Send the response message
                    response = json.dumps(
                        {
                            "data":[
                                "早上好",
                                True,
                                {
                                    "name":"/tmp/gradio/08c66bea054ca4300b08fbd52b8a4e65cade5bcc/audio.wav",
                                    "data":"https://fs.firefly.matce.cn/file=/tmp/gradio/08c66bea054ca4300b08fbd52b8a4e65cade5bcc/audio.wav",
                                    "is_file":True,
                                    "orig_name":"audio.wav"
                                },
                                "大丈夫、もう一度やってみよう。「潜爆機兵」ならたくさん用意してある。 君が戦いたがっているのはわかるが…今回はやはり「潜爆機兵」で問題を解決しよう。 やむを得ない状況でなければ、このような手は使いたくなかったんだが…… ああ。外見は「グリズリー」に似ているが、より優れた武器と堅硬な装甲を備えている。",
                                0,
                                48,
                                0.7,
                                1.5,
                                0.7,
                                "杰帕德_JP"
                            ],
                            "event_data":None,
                            "fn_index":4,
                            "session_hash":session_hash
                        }
                    )
                    await websocket.send(response)
                    logging.debug(f"Sent message: {response}")
                elif data["msg"] == "process_completed":
                    return data["output"]["data"][0]["name"]
                
    voice_tmp_path = await websocket_client(data)
    if voice_tmp_path is not None:
        file_url = f"https://fs.firefly.matce.cn/file={voice_tmp_path}"
        logging.info(file_url)
        voice_tmp_path = await download_audio("fish_speech", file_url, 30)

    return voice_tmp_path

logging.basicConfig(level=logging.DEBUG)  # Set the log level toINFO
# Run the async program
asyncio.run(fish_speech_web_api(1))