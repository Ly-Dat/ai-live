from gradio_client import Client

client = Client("https://v2.genshinvoice.top/")
result = client.predict(
		"Howdy!",	# str  in 'Input text' Textbox component
		fn_index=1
)
print(result)