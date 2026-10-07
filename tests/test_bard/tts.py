from bardapi import Bard

"""
Access https://bard.google.com/
F12 for console used for the console F12
Session: Application -> Cookies -> copy the value of __Secure-1PSID.
"""
token = ''

bard = Bard(token=token)
content = 'Hello, I am Bard! How can I help you today?'
content = '你好'
audio = bard.speech(content)
with open("speech.ogg", "wb") as f:
  f.write(bytes(audio['audio']))