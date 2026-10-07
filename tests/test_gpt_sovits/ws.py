import asyncio
import websockets
import json, os, logging, traceback
import base64
import mimetypes

async def gpt_sovits_api(data):
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

    async def websocket_client(data_json):
        try:
            async with websockets.connect(data["api_ip_port"]) as websocket:
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
                    response = json.dumps({"session_hash":"3obpzfqql7f","fn_index":0})
                    await websocket.send(response)
                    logging.debug(f"Sent message: {response}")
                elif data["msg"] == "send_data":
                    # audio_path = "F:\\GPT-SoVITS\\raws\\ikaros\\1.wav"
                    audio_path = data_json["ref_audio_path"]

                    # Send the response message
                    response = json.dumps(
                        {
                            "session_hash":"3obpzfqql7f",
                            "fn_index":0,
                            "data":[
                                {
                                    "data": file_to_data_url(audio_path),
                                    "name": os.path.basename(audio_path)
                                },
                                data_json["prompt_text"], 
                                data_json["prompt_language"], 
                                data_json["content"], 
                                data_json["language"]
                            ]
                        }
                    )
                    await websocket.send(response)
                    logging.debug(f"Sent message: {response}")
                elif data["msg"] == "process_completed":
                    return data["output"]["data"][0]["name"]
                
    try:
        logging.debug(f"data={data}")
        
        # Call the function and wait for the result
        voice_tmp_path = await websocket_client(data)

        return voice_tmp_path
    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f'gpt_sovitsUnknown error, please check whether your gpt_sovits inference is started/configured correctly, error details: {e}')
    
    return None

# Run the async WebSocket client
# asyncio.get_event_loop().run_until_complete(websocket_client())

if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.INFO,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "api_ip_port": "ws://localhost:9872/queue/join",
        "ref_audio_path": "F:\\GPT-SoVITS\\raws\\ikaros\\1.wav",
        "prompt_text": "そらのおとしもの、ふぉるて",
        "prompt_language": "日文",
        "content": "おはようございます",
        "language": "日文"
    }

    # Run the async function and get the result
    result = asyncio.run(gpt_sovits_api(data))

    logging.info(f"result={result}")
    