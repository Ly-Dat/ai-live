from pygtrans import Translate

client = Translate(proxies={'https': 'http://localhost:10809'})

text = client.detect('Answer the question.')
print(text)

# Detect language
text = client.detect('Answer the question.')
print(text)

# Translate the sentence
text = client.translate('你好', target='en', source='zh-CN')
print(text)

# Text to speech
tts = client.tts('こにちわ', target='ja')
open('こにちわ.wav', 'wb').write(tts)