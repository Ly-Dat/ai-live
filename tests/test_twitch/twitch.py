import socks, re
from emoji import demojize

server = 'irc.chat.twitch.tv'
port = 6667
nickname = '主人'
token = 'oauth:xxx' # Visit https://twitchapps.com/tmi/ to get it
user = 'love_ikaros' # Your Twitch username Your Twitch username
channel = '#prettyyjj' # The channel to retrieve messages from; note that # must be included at the start The channel you want to retrieve messages from

# Address and port of the proxy server
proxy_server = "127.0.0.1"
proxy_port = 10809

# Configure the proxy server
socks.set_default_proxy(socks.HTTP, proxy_server, proxy_port)

# Create the socket object
sock = socks.socksocket()

try:
    sock.connect((server, port))
    print("Connected successfully Twitch IRC server")
except Exception as e:
    print(f"Failed to connect to the Twitch IRC server: {e}")


sock.send(f"PASS {token}\n".encode('utf-8'))
sock.send(f"NICK {nickname}\n".encode('utf-8'))
sock.send(f"JOIN {channel}\n".encode('utf-8'))

regex = r":(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :(.+)"

while True:
    try:
        resp = sock.recv(2048).decode('utf-8')

        # Output all received content, includingPING/PONG
        # print(resp)

        if resp.startswith('PING'):
                sock.send("PONG\n".encode('utf-8'))

        elif not user in resp:
            resp = demojize(resp)
            match = re.match(regex, resp)

            username = match.group(1)
            message = match.group(2)
            
            
            chat = '[' + username + ']: ' + message
            print(chat)

    except Exception as e:
        print("Error receiving chat: {0}".format(e))