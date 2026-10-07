import json, logging
import requests
from urllib.parse import urljoin

import hashlib
import time
import uuid

# from utils.common import Common
# from utils.logger import Configure_logger


class QAnything:
    def __init__(self, data):
        # self.common = Common()
        # Log file path
        # file_path = "./log/log-" + self.common.get_bj_time(1) + ".txt"
        # Configure_logger(file_path)

        self.api_ip_port = data["api_ip_port"]
        self.config_data = data

        self.history = []


    # Get the knowledge base list
    def get_list_knowledge_base(self):
        url = urljoin(self.api_ip_port, "/api/local_doc_qa/list_knowledge_base")
        try:
            response = requests.post(url, json={"user_id": self.config_data["user_id"]})
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logging.debug(ret)
            logging.info(f"Local knowledge base list:{ret['data']}")

            return ret['data']
        except Exception as e:
            logging.error(e)
            return None


    # Official onlineAPI
    '''
    Add authentication-related parameters -
        appKey : ApplicationID
        salt : Random value
        curtime : Current timestamp (seconds)
        signType : Signature version
        sign : Request signature
        
        @param appKey    Your applicationID
        @param appSecret Your application secret key
        @param paramsMap Request parameter table
    '''
    def addAuthParams(self, appKey, appSecret, params):
        def returnAuthMap(appKey, appSecret, q):
            salt = str(uuid.uuid1())
            curtime = str(int(time.time()))
            sign = calculateSign(appKey, appSecret, q, salt, curtime)
            params = {'appKey': appKey,
                    'salt': salt,
                    'curtime': curtime,
                    'signType': 'v3',
                    'sign': sign}
            return params


        '''
            Compute the authentication signature -
            Calculation method : sign = sha256(appKey + input(q) + salt + curtime + appSecret)
            @param appKey    Your applicationID
            @param appSecret Your application secret key
            @param q         Request content
            @param salt      Random value
            @param curtime   Current timestamp (seconds)
            @return Authentication signaturesign
        '''
        def calculateSign(appKey, appSecret, q, salt, curtime):
            strSrc = appKey + getInput(q) + salt + curtime + appSecret
            return encrypt(strSrc)


        def encrypt(strSrc):
            hash_algorithm = hashlib.sha256()
            hash_algorithm.update(strSrc.encode('utf-8'))
            return hash_algorithm.hexdigest()


        def getInput(input):
            if input is None:
                return input
            inputLen = len(input)
            return input if inputLen <= 20 else input[0:10] + str(inputLen) + input[inputLen - 10:inputLen]



        q = params.get('q')
        if q is None:
            q = params.get('img')
        q = "".join(q)
        salt = str(uuid.uuid1())
        curtime = str(int(time.time()))
        sign = calculateSign(appKey, appSecret, q, salt, curtime)
        params['appKey'] = appKey
        params['salt'] = salt
        params['curtime'] = curtime
        params['signType'] = 'v3'
        params['sign'] = sign

        return params

    

    def createKB(self, kbName):
        data = {'q': kbName}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        header = {'Content-Type': 'application/json'}
        logging.info('Request parameters:' + json.dumps(data))
        res = self.doCall('https://openapi.youdao.com/q_anything/paas/create_kb', header, json.dumps(data), 'post')
        logging.info(str(res.content, 'utf-8'))


    def deleteKB(self, kbId):
        data = {'q': kbId}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        header = {'Content-Type': 'application/json'}
        logging.info('Request parameters:' + json.dumps(data))
        res = self.doCall('https://openapi.youdao.com/q_anything/paas/delete_kb', header, json.dumps(data), 'post')
        logging.info(str(res.content, 'utf-8'))


    def uploadDoc(self, kbId, file):
        data = {'q': kbId}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        res = requests.post('https://openapi.youdao.com/q_anything/paas/upload_file', data=data, files={'file': file})
        logging.info(str(res.content, 'utf-8'))


    def uploadUrl(self, kbId, url):
        data = {'q': kbId, 'url': url}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        header = {'Content-Type': 'application/json'}
        logging.info('Request parameters:' + json.dumps(data))
        res = self.doCall('https://openapi.youdao.com/q_anything/paas/upload_url', header, json.dumps(data), 'post')
        logging.info(str(res.content, 'utf-8'))


    def deleteFile(self, kbId, fileId):
        data = {'q': kbId, 'fileIds': [fileId]}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        header = {'Content-Type': 'application/json'}
        logging.info('Request parameters:' + json.dumps(data))
        res = self.doCall('https://openapi.youdao.com/q_anything/paas/delete_file', header, json.dumps(data), 'post')
        logging.info(str(res.content, 'utf-8'))


    def kbList(self):
        data = {'q': ''}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        header = {'Content-Type': 'application/json'}
        logging.debug('Request parameters:' + json.dumps(data))
        res = self.doCall('https://openapi.youdao.com/q_anything/paas/kb_list', header, json.dumps(data), 'post')
        logging.info(str(res.content, 'utf-8'))


    def fileList(self, kbId):
        data = {'q': kbId}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        header = {'Content-Type': 'application/json'}
        logging.info('Request parameters:' + json.dumps(data))
        res = self.doCall('https://openapi.youdao.com/q_anything/paas/file_list', header, json.dumps(data), 'post')
        logging.info(str(res.content, 'utf-8'))


    def chat(self, kbId, q):
        try:
            data = {'q': q, 'kbIds': [kbId]}
            logging.debug(f"data={data}")
            data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
            header = {'Content-Type': 'application/json'}
            logging.debug('Request parameters:' + json.dumps(data))
            res = self.doCall('https://openapi.youdao.com/q_anything/paas/chat', header, json.dumps(data), 'post')
            logging.debug(str(res.content, 'utf-8'))

            return json.loads(str(res.content, 'utf-8'))
        except Exception as e:
            logging.error(e)
            return None

    def chatStream(self, kbId, q):
        data = {'q': q, 'kbIds': [kbId]}
        data = self.addAuthParams(self.config_data["app_key"], self.config_data["app_secret"], data)
        header = {'Content-Type': 'application/json'}
        logging.debug('Request parameters:' + json.dumps(data))
        res = self.doCall('https://openapi.youdao.com/q_anything/paas/chat_stream', header, json.dumps(data), 'post')
        logging.debug(str(res.content, 'utf-8'))


    def doCall(self, url, header, params, method):
        if 'get' == method:
            return requests.get(url, params)
        elif 'post' == method:
            return requests.post(url, params, headers=header)


    def get_resp(self, data):
        """Request the corresponding API and get the return value

        Args:
            data (dict): jsonData

        Returns:
            str: Returned text answer
        """
        try:
            if self.config_data["type"] == "online":
                resp_json = self.chat(self.config_data["kb_ids"][0], data["prompt"])

                return resp_json["result"]["response"]
            elif self.config_data["type"] == "local":
                url = self.api_ip_port + "/api/local_doc_qa/local_doc_chat"

                data_json = {
                    "user_id": self.config_data["user_id"], 
                    "kb_ids": self.config_data["kb_ids"], 
                    "question": data["prompt"], 
                    "history": self.history
                }

                response = requests.post(url=url, json=data_json)
                response.raise_for_status()  # Check the response status code

                result = response.content
                ret = json.loads(result)

                logging.info(ret)

                resp_content = ret["response"]

                # If history is enabled, remember it for me!
                if self.config_data["history_enable"]:
                    self.history = ret["history"]

                    while True:
                        # Count all characters
                        total_chars = sum(len(item) for sublist in self.history for item in sublist)

                        # If it exceeds the maximum history limit, remove the first element
                        if total_chars > self.config_data["history_max_len"]:
                            self.history.pop(0)
                        else:
                            break

                return resp_content
        except Exception as e:
            logging.error(e)
            return None


if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "type": "online",
        "app_key": "",
        "app_secret": "",
        "api_ip_port": "http://127.0.0.1:8777",
        "user_id": "zzp",
        "kb_ids": ["KBace3c3bb8c204432b4dfb0ba77a8552e", "KB2435554f1fb348ad84a1eb60eaa1c466"],
        "history_enable": True,
        "history_max_len": 300
    }
    qanything = QAnything(data)

    if data["type"] == "online":
        qanything.kbList()
    elif data["type"] == "local":
        qanything.get_list_knowledge_base()

    logging.info(qanything.get_resp({"prompt": "The relationship between Icarus and Nymph"}))
    # logging.info(qanything.get_resp({"prompt": "The English name of Icarus"}))
    