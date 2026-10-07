import google.generativeai as genai
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Image
import os
import logging
import traceback

class Gemini:
    def __init__(self, data):
        try:
            self.config_data = data

            self.history = []
            # Set proxy
            if self.config_data["http_proxy"]:
                os.environ['http_proxy'] = self.config_data["http_proxy"]
            if self.config_data["https_proxy"]:
                os.environ['https_proxy'] = self.config_data["https_proxy"]

            genai.configure(api_key=self.config_data["api_key"])
            self.model = genai.GenerativeModel(model_name = self.config_data["model"])

            vertexai.init(project=self.config_data["project_id"], location="us-central1")
        except Exception as e:
            logging.error(traceback.format_exc())
            
    def list_models(self):
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                logging.info(m.name)

    def get_resp_with_img(self, prompt, img_data):
        try:
            img = Image.load_from_file(img_data)

            image_file = Part.from_image(img)

            model = GenerativeModel(model_name="gemini-1.0-pro-vision-001")
            response = model.generate_content(
                [
                    image_file,
                    prompt,
                ]
            )

            logging.warning(f"{response}")

            resp_content = response.text.strip()

            logging.debug(f"resp_content={resp_content}")

            return resp_content
        except Exception as e:
            logging.error(traceback.format_exc())
            return None
        
    def get_resp_with_img_old(self, prompt, img_data):
        try:
            import PIL.Image

            # Check the type of img_data
            if isinstance(img_data, str):  # If it is a string, assume it is a file path
                # Use PIL.Image.open() to open the image file
                img = PIL.Image.open(img_data)
            elif isinstance(img_data, PIL.Image.Image):  # If it is already a PIL.Image.Image object
                # Return this image object directly
                img = img_data
            else:
                img = img_data

            model = genai.GenerativeModel('gemini-pro-vision')

            response = model.generate_content(
                [
                    prompt, 
                    img
                ],
                stream=False
            )

            resp_content = response.text.strip()
        
            logging.debug(f"resp_content={resp_content}")

            return resp_content
        except Exception as e:
            logging.error(traceback.format_exc())
            return None

    def get_resp(self, prompt):
        """Request the corresponding API and get the return value

        Args:
            prompt (str): Your question

        Returns:
            str: Returned text answer
        """
        try:
            messages = []

            # Load context
            for history in self.history:
                messages.append(
                    {
                        'role':history["role"],
                        'parts': history["parts"]
                    }
                )

            messages.append(
                {
                    'role': 'user',
                    'parts': prompt
                }
            )

            response = self.model.generate_content(
                messages, 
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens = self.config_data["max_output_tokens"], 
                    temperature = self.config_data["temperature"], 
                    top_p = self.config_data["top_p"],
                    top_k = self.config_data["top_k"])
                ,
                stream = False
            )
            resp_content = response.text

            # If history is enabled, remember it for me!
            if self.config_data["history_enable"]:
                while True:
                    # Get the character count of all strings in a nested list
                    total_chars = sum(len(string) for sublist in self.history for string in sublist)
                    # If it exceeds the maximum history limit, remove the first element
                    if total_chars > self.config_data["history_max_len"]:
                        self.history.pop(0)
                        self.history.pop(0)
                    else:
                        self.history.append({"role": "user", "parts": [prompt]})
                        self.history.append({"role": "model", "parts": [resp_content]})
                        break

            return resp_content
        except Exception as e:
            logging.error(traceback.format_exc())
            return None
        

if __name__ == '__main__':
    # Configure the log output format
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level; adjust as needed
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    data = {
        "api_key": "",
        "project_id": "avian-current-437112-a3",
        "model": "gemini-pro",
        "max_output_tokens": 100, 
        "temperature": 1.0, 
        "top_p": 0.7,
        "top_k": 40,
        "http_proxy": "http://127.0.0.1:10809",
        "https_proxy": "http://127.0.0.1:10809",
        "history_enable": True,
        "history_max_len": 300
    }

    gemini = Gemini(data)

    # logging.info(gemini.get_resp("Can you play a catgirl and add meow after every sentence"))
    # logging.info(gemini.get_resp("Good morning"))
    # logging.info(gemini.get_resp("My eyes are so sore"))

    logging.info(gemini.get_resp_with_img("Guess what I am eating based on the image content", "1.png"))
    