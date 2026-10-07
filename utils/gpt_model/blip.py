import traceback
from utils.my_log import logger
from utils.common import Common
import time

from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

class Blip:
    def __init__(self, data):
        self.common = Common()

        self.config_data = data

        self.processor = BlipProcessor.from_pretrained(self.config_data["model"])
        self.model = BlipForConditionalGeneration.from_pretrained(self.config_data["model"]).to("cuda")

        logger.info("Blip Model loaded")

        #processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
        #model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")

        #img_url = 'https://storage.googleapis.com/sfr-vision-language-research/BLIP/demo.jpg' 
        #raw_image = Image.convert('RGB')

        # conditional image captioning
        #text = "a photography of"
        #inputs = processor(raw_image, text, return_tensors="pt")

        #out = model.generate(**inputs)
        #print(processor.decode(out[0], skip_special_tokens=True))

        # unconditional image captioning
        #inputs = processor(img_data, return_tensors="pt")

        #out = model.generate(**inputs)
        #print(processor.decode(out[0], skip_special_tokens=True))


    def generate_caption(self, img_data: str, prompt: str):
        try:
            # Check the type of img_data
            if isinstance(img_data, str):  # If it is a string, assume it is a file path
                # Use PIL.Image.open() to open the image file
                img = Image.open(img_data)
            elif isinstance(img_data, Image.Image):  # If it is already a PIL.Image.Image object
                # Return this image object directly
                img = img_data
            else:
                img = img_data

            raw_image = img.convert("RGB")

            inputs = self.processor(raw_image, prompt, return_tensors="pt").to("cuda")

            start_time = time.time()
            out = self.model.generate(**inputs)
            generation_time = time.time() - start_time

            caption = self.processor.decode(out[0], skip_special_tokens=True)
            return caption, generation_time
        except Exception as e:
            logger.error(traceback.format_exc())
            return None, None


    def generate_image_caption(self, img_data, conditional_text=None):
        """
        Generate an image description from the given image.
        
        Parameter:
            img_data (str): Path of the image.
            conditional_text (str, optional): Conditional text used to conditionally generate the image description, default is None.
            
        Return:
            str: The generated image description.
        """
        # Open and convert the image
        with Image.open(img_data) as img:
            raw_image = img.convert("RGB")
        
            # Prepare the input depending on whether conditional text is provided
            if conditional_text:
                inputs = self.processor(raw_image, conditional_text, return_tensors="pt").to("cuda")
            else:
                inputs = self.processor(raw_image, return_tensors="pt").to("cuda")
            
            # Generate the image description
            out = self.model.generate(**inputs)
            
            # Decode the output and return it
            return self.processor.decode(out[0], skip_special_tokens=True)
        return None


    def get_resp_with_img(self, prompt, img_data):
        try:
            caption, time = self.generate_caption(img_data, prompt)
            if caption:
                return caption
            else:
                return None
        except Exception as e:
            logger.error(traceback.format_exc())
            return None
