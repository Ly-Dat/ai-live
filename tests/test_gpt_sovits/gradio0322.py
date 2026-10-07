from gradio_client import Client

client = Client("http://127.0.0.1:9872/")
result = client.predict(
    "你好，Hello!!",	# str  in 'Text to synthesize' Textbox component
    "中英混合",	# Literal['Chinese', 'English', 'Japanese', 'Chinese-English mix', 'Japanese-English mix', 'Multilingual mix']  in 'Language to synthesize' Dropdown component
    "F:\\GPT-SoVITS\\raws\\ikaros\\21.wav",	# filepath  in 'Please upload a reference audio of 3-10 seconds, longer will cause an error!' Audio component
    "マスター、どうりょくろか、いいえ、なんでもありません",	# str  in 'Text of the reference audio' Textbox component
    "日文",	# Literal['Chinese', 'English', 'Japanese', 'Chinese-English mix', 'Japanese-English mix', 'Multilingual mix']  in 'Language of the reference audio' Dropdown component
    1,	# float (numeric value between 1 and 100) in 'top_k' Slider component
    0.8,	# float (numeric value between 0 and 1) in 'top_p' Slider component
    0.8,	# float (numeric value between 0 and 1) in 'temperature' Slider component
    "按标点符号切",	# Literal['No split', 'Split when reaching four sentences', 'Split when reaching 50 characters', 'Split at Chinese full stop', 'Split at English period', 'Split by punctuation']  in 'How to split' Radio component
    20,	# float (numeric value between 1 and 200) in 'batch_size' Slider component
    1,	# float (numeric value between 0.25 and 4) in 'speed_factor' Slider component
    False,	# bool  in 'Enable no-reference-text mode. Leaving the reference text empty also enables it.' Checkbox component
    True,	# bool  in 'Data bucketing (may reduce computation slightly, just pick it)' Checkbox component
    0.3,	# float (numeric value between 0.01 and 1) in 'Segment interval (seconds)' Slider component
    api_name="/inference"
)
print(result)