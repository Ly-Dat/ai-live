import bardapi

"""
Access https://bard.google.com/
F12 for console used for the console F12
Session: Application -> Cookies -> copy the value of __Secure-1PSID.
"""
token = ''
proxies = {
    'http': 'http://127.0.0.1:10809',
    'https': 'http://127.0.0.1:10809'
}
#proxies = None

input_text = "你好"
response = bardapi.core.Bard(token, proxies=proxies, timeout=30).get_answer(input_text)
print(response)
print(response["content"])
# bard = Bard(token=token, proxies=proxies, timeout=30)
# bard.get_answer("Hello")['content']