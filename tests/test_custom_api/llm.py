import json, logging
import re, requests
import traceback

from utils.common import Common
from utils.logger import Configure_logger


class Custom_LLM:
    def __init__(self, data):
        self.config_data = data
        self.common = Common()
        # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.history = []

    def parse_headers(self, headers_text):
        headers = {}
        for line in headers_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
        return headers

    def replace_variables(self, text, variables):
        for key, value in variables.items():
            text = re.sub(f'{{{{{key}}}}}', value, text)
        return text

    def send_request(self, url="", method='GET', headers=None, body_type="json", body=None, resp_data_type="json", proxies=None, timeout=60):
        """
        Send an HTTP request and return the result

        Parameters:
            url (str): Requested URL
            method (str): Request method,'GET' Or 'POST'
            headers (str): Request headers (one key-value pair per line, e.g. Content-Type: application/json)
            body (str): Request body
            resp_data_type (str): Type of returned data (json | content)
            proxies (dict): Proxy configuration
            timeout (int): Request timeout

        Returns:
            dict|str: JSON data containing the response | string data
        """

        try:
            if body_type == "json":
                body = json.loads(body)
                response = requests.request(method=method, url=url, headers=headers, json=body, proxies=proxies, timeout=timeout)
            else:
                body = body.encode('utf-8')
                response = requests.request(method=method, url=url, headers=headers, data=body, proxies=proxies, timeout=timeout)
            logging.info(f'response.content={response.content}')

            if resp_data_type == "json":
                # Parse the JSON response data
                result = response.json()
            else:
                result = response.content
                # Use 'utf-8' Encoding used to decode the byte string
                result = result.decode('utf-8')

            return result

        except requests.exceptions.RequestException as e:
            logging.error(traceback.format_exc())
            logging.error(f"Request error: {e}")
            return None


    def get_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dcit): Request parameters

        Returns:
            str: Returned text answer
        """
        try:
            variables = {
                "cur_time": self.common.get_bj_time(0),
                "prompt": data['prompt'],
            }

            url = self.replace_variables(self.config_data['url'], variables)
            method = self.config_data['method']
            body_type = self.config_data['body_type']
            body = self.replace_variables(self.config_data['body'], variables)
            resp_data_type = self.config_data['resp_data_type']
            headers = self.parse_headers(self.replace_variables(self.config_data['headers'], variables))
            data_analysis = self.config_data['data_analysis']
            resp_template = self.config_data['resp_template']
            if self.config_data['proxies'] == '':
                proxies = None
            else:
                proxies = json.loads(self.config_data['proxies'])

            logging.info(f"url={url}\nheaders={headers}\nbody={body}")

            resp = self.send_request(url=url, method=method, headers=headers, body_type=body_type, body=body, resp_data_type=resp_data_type, proxies=proxies, timeout=60)
            if resp is None:
                return None
                
            # Use eval() to execute a string expression and get the result
            resp_content = eval(data_analysis)

            variables = {
                'cur_time': self.common.get_bj_time(5),
                'data': resp_content
            }

            # Use a dictionary for string replacement
            if any(var in resp_template for var in variables):
                resp_content = resp_template.format(**{var: value for var, value in variables.items() if var in resp_template})

            return resp_content
        except Exception as e:
            logging.error(traceback.format_exc())
            return None


# For testing
if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "url": "http://127.0.0.1:11434/v1/chat/completions",
        "headers": "Content-Type:application/json\nAuthorization:Bearer sk",
        "method": "POST",
        "proxies": "{}",
        "body_type": "json",
        "body": "{\"model\":\"qwen:latest\",\"messages\":[{\"role\":\"user\",\"content\":\"{{prompt}}\"}]}",
        "resp_data_type": "json",
        "data_analysis": "resp[\"choices\"][0][\"message\"][\"content\"]",
        "resp_template": "{data}"
    }

    custom_llm = Custom_LLM(data)

    logging.info(custom_llm.get_resp({"prompt": "Good morning"}))
    