import traceback
from copy import deepcopy
import openai
from packaging import version

from utils.common import Common
from utils.my_log import logger


class Chatgpt:
    # Set the initial session value
    # session_config = {'msg': [{"role": "system", "content": config_data['chatgpt']['preset']}]}
    session_config = {}
    sessions = {}
    current_key_index = 0
    data_openai = {}
    data_chatgpt = {}

    def __init__(self, data_openai, data_chatgpt):
        self.common = Common()
        # Set the initial session value
        self.session_config = {'msg': [{"role": "system", "content": data_chatgpt["preset"]}]}
        self.data_openai = data_openai
        self.data_chatgpt = data_chatgpt


    # chatgptRelated
    def chat(self, msg, sessionid):
        """
        ChatGPT Chat function
        :param msg: Message entered by the user
        :param sessionid: Current session ID
        :return: ChatGPT Returned reply content
        """
        try:
            # Get the current session
            session = self.get_chat_session(sessionid)

            # Add the user input message to the session
            session['msg'].append({"role": "user", "content": msg})

            # Add the current time to the session
            session['msg'][1] = {"role": "system", "content": "current time is:" + self.common.get_bj_time()}

            # Call the ChatGPT API to generate a reply message
            message = self.chat_with_gpt(session['msg'])

            if message is None:
                return None

            # If the returned message mentions the maximum context length limit, remove the overlong context and retry
            if message.__contains__("This model's maximum context length is 409"):
                del session['msg'][0:3]
                del session['msg'][len(session['msg']) - 1:len(session['msg'])]
                message = self.chat(msg, sessionid)

            # Add the reply message returned by ChatGPT to the session
            session['msg'].append({"role": "assistant", "content": message})

            # Output the session ID and the reply message returned by ChatGPT
            logger.info("SessionID: " + str(sessionid))
            logger.debug("ChatGPTReturned content: ")
            logger.debug(message)

            # Return the reply message returned by ChatGPT
            return message

        # Catch the exception and print the stack trace
        except Exception as error:
            logger.error(traceback.format_exc())
            return None


    def get_chat_session(self, sessionid):
        """
        Get the session with the specified ID; create a new session if it does not exist
        :param sessionid: Session ID
        :return: Session with the specified ID
        """
        sessionid = str(sessionid)
        if sessionid not in self.sessions:
            config = deepcopy(self.session_config)
            config['id'] = sessionid
            config['msg'].append({"role": "system", "content": "current time is:" + self.common.get_bj_time()})
            self.sessions[sessionid] = config
        return self.sessions[sessionid]


    def chat_with_gpt(self, messages):
        """
        Use the ChatGPT API to generate a reply message
        :param messages: Context message list
        :return: ChatGPT Returned reply message
        """
        max_length = len(self.data_openai['api_key']) - 1

        try:
            openai.api_base = self.data_openai['api']

            if not self.data_openai['api_key']:
                logger.error(f"Please setopenai Api Key")
                return None
            else:
                # Check whether all API keys have reached the rate limit
                if self.current_key_index > max_length:
                    self.current_key_index = 0
                    logger.warning(f"All keys have reached the rate limit, please wait one minute and try again")
                    return None
                openai.api_key = self.data_openai['api_key'][self.current_key_index]

            logger.debug(f"openai.__version__={openai.__version__}")

            # Check the openai library version; 1.x.x and 0.x.x have breaking changes
            if version.parse(openai.__version__) < version.parse('1.0.0'):
                # Call the ChatGPT API to generate a reply message
                resp = openai.ChatCompletion.create(
                    model=self.data_chatgpt['model'],
                    messages=messages,
                    timeout=30
                )

                resp = resp['choices'][0]['message']['content']
            else:
                logger.debug(f"base_url={openai.api_base}, api_key={openai.api_key}")

                client = openai.OpenAI(base_url=openai.api_base, api_key=openai.api_key)
                # Call the ChatGPT API to generate a reply message
                resp = client.chat.completions.create(
                    model=self.data_chatgpt['model'],
                    messages=messages,
                    timeout=30
                )

                resp = resp.choices[0].message.content
        # Handle OpenAIError exceptions
        except openai.OpenAIError as e:
            if str(e).__contains__("Rate limit reached for default-gpt-3.5-turbo") and self.current_key_index <= max_length:
                self.current_key_index = self.current_key_index + 1
                logger.warning("Rate limited, trying to switchkey")
                msg = self.chat_with_gpt(messages)
                return msg
            elif str(e).__contains__(
                    "Your access was terminated due to violation of our policies") and self.current_key_index <= max_length:
                logger.warning("Please confirm promptly that thisKey: " + str(openai.api_key) + " is working properly; if abnormal, please remove")

                # Check whether all API keys have been tried
                if self.current_key_index + 1 > max_length:
                    return str(e)
                else:
                    logger.warning("Access blocked, trying to switchKey")
                    self.current_key_index = self.current_key_index + 1
                    msg = self.chat_with_gpt(messages)
                    return msg
            else:
                logger.error('openai API error: ' + str(e))
                return None

        return resp

    def chat_stream(self, msg, sessionid):
        """
        ChatGPT Streaming chat function
        :param msg: Message entered by the user
        :param sessionid: Current session ID
        :return: resp - Response message
        """
        try:
            # Get the current session
            session = self.get_chat_session(sessionid)

            # Add the user input message to the session
            session['msg'].append({"role": "user", "content": msg})

            # Add the current time to the session
            session['msg'][1] = {"role": "system", "content": "current time is:" + self.common.get_bj_time()}

            # logger.warning(sessionid)
            # logger.warning(session)

            messages = session['msg']

            max_length = len(self.data_openai['api_key']) - 1

            openai.api_base = self.data_openai['api']

            if not self.data_openai['api_key']:
                logger.error(f"Please setopenai Api Key")
                return None
            else:
                # Check whether all API keys have reached the rate limit
                if self.current_key_index > max_length:
                    self.current_key_index = 0
                    logger.warning(f"All keys have reached the rate limit, please wait one minute and try again")
                    return None
                openai.api_key = self.data_openai['api_key'][self.current_key_index]

            logger.debug(f"openai.__version__={openai.__version__}")

            # Check the openai library version; 1.x.x and 0.x.x have breaking changes
            if version.parse(openai.__version__) < version.parse('1.0.0'):
                # Call the ChatGPT API to generate a reply message
                resp = openai.ChatCompletion.create(
                    model=self.data_chatgpt['model'],
                    messages=messages,
                    timeout=30,
                    stream=True,
                )

            else:
                logger.debug(f"base_url={openai.api_base}, api_key={openai.api_key}")

                client = openai.OpenAI(base_url=openai.api_base, api_key=openai.api_key)
                # Call the ChatGPT API to generate a reply message
                resp = client.chat.completions.create(
                    model=self.data_chatgpt['model'],
                    messages=messages,
                    timeout=30,
                    stream=True,
                )

            return resp

        except Exception as e:
            logger.error(traceback.format_exc())
            return None


    # Call the gpt API and get the returned content
    def get_gpt_resp(self, username, prompt, stream=False):
        try:
            if not stream:
                # Call the ChatGPT API to generate a reply message
                resp_content = self.chat(prompt, username)
            else:
                resp_content = self.chat_stream(prompt, username)

            return resp_content
        except Exception as e:
            logger.error(traceback.format_exc())
            return None
    
    # Add the AI reply message to the session to provide contextual memory
    def add_assistant_msg_to_session(self, username, message):
        try:
            # Get the session of the current user
            session = self.get_chat_session(str(username))
            # Add the reply message returned by ChatGPT to the session
            session['msg'].append({"role": "assistant", "content": message})

            # logger.warning(str(username))
            # logger.warning(session)

            return {"ret": True}
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"ret": False}

