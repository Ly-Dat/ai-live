from gradio_client import Client

client = Client("https://xzjosh-nana7mi-bert-vits2.hf.space/--replicas/m9qdw/")
result = client.predict(
		"你好",	# str  in 'Text' Textbox component
		"Nana7mi",	# str (Option from: [('Nana7mi', 'Nana7mi')]) in 'Speaker' Dropdown component
		0.2,	# int | float (numeric value between 0.1 and 1) in 'SDP/DPMix ratio' Slider component
		0.5,	# int | float (numeric value between 0.1 and 1) in 'Emotion control' Slider component
		0.9,	# int | float (numeric value between 0.1 and 1) in 'Phoneme length' Slider component
		1,	# int | float (numeric value between 0.1 and 2) in 'Generation length' Slider component
		fn_index=0
)
print(result)