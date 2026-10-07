import json
import logging
import requests

api_url = "https://api.coze.cn/v3/chat"
authorization_token = "Bearer "

def print_unicode(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            print(f"{key}: ", end='')
            print_unicode(value)
    elif isinstance(obj, list):
        for item in obj:
            print_unicode(item)
    else:
        print(ensure_unicode(obj))

def ensure_unicode(text):
    if isinstance(text, str):
        return text
    elif isinstance(text, bytes):
        return text.decode('utf-8', errors='replace')
    else:
        return str(text)

def get_chat_response():
    # Docs:https://www.coze.cn/docs/developer_guides/chat_v3
    headers = {
        "Authorization": authorization_token,
        "Content-Type": "application/json"
    }

    data_json = {
        "bot_id": "7392993441015332874",
        "user_id": "1",
        # Whether to enable streaming responses
        "stream": True,
        # Whether to save this conversation
        "auto_save_history": True,
        "additional_messages": [
            {
                "role": "user",
                "content": "早上好",
                "content_type": "text"
            }
        ],
    }

    try:
        with requests.post(url=api_url, headers=headers, json=data_json) as response:
            response.raise_for_status()  # Check the response status code
            
            # Check and set the response encoding
            if response.encoding is None:
                response.encoding = 'utf-8'  # If no encoding is specified, set it manually to utf-8

            # Iterate over the streaming response
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    # line = line.encode('utf-8').decode('utf-8')  # Make sure decoding uses utf-8
                    # Handle the event and data parts
                    if line.startswith("data:"):
                        data = line[5:].strip()  # Remove the prefix "data:" and strip extra whitespace
                        try:
                            # decoded_data = data.decode('utf-8')
                            json_data = json.loads(data)
                            #print_unicode(json_data)
                            print(json_data)  # Parse and print the JSON data
                        except json.JSONDecodeError:
                            print(f"Received non-JSON data: {data}")
                    else:
                        print(line)  # Print the event part or other non-data lines

    except Exception as e:
        logging.error(e)
        return None

# Call the function and print the response
get_chat_response()
