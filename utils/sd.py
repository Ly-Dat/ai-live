import threading
import webuiapi
# from PIL import Image
import pyvirtualcam
import numpy as np
import traceback
import asyncio
import os
from PIL import Image, ImageOps
import numpy as np

from .common import Common
from .my_log import logger

def hex_to_rgba(hex_str):
    """Convert a hex color string to an RGBA tuple."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 8:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4, 6))  # Extract separatelyRGBA
    elif len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4)) + (255,)  # RGB + Default opacity
    else:
        logger.error(f"Invalid color value: {hex_str}")
        raise ValueError(f"Invalid color value: {hex_str}")

class SD:
    def __init__(self, data): 
        self.common = Common()

        self.new_img = None
        self.sd_config = data

        try:
            if data["enable"]:
                # Create the API client
                self.api = webuiapi.WebUIApi(host=data["ip"], port=data["port"])

            self.rgba_color = hex_to_rgba(data["visual_camera"]["background_color"])

            logger.info("About to create the virtual camera thread...")
            # Update the virtual camera in a separate thread
            threading.Thread(target=lambda: asyncio.run(self.update_virtual_camera())).start()
            # threading.Thread(target=self.update_virtual_camera).start()
        except Exception as e:
            logger.error(traceback.format_exc())

    async def update_virtual_camera(self):
        try:
            # Fix the virtual camera resolution
            cam_width, cam_height = 1920, 1080  # The resolution can be changed here as needed
            with pyvirtualcam.Camera(width=cam_width, height=cam_height, fps=1, fmt=pyvirtualcam.PixelFormat.RGB) as cam:
                logger.info(f'Virtual camera created, resolution: {cam_width}x{cam_height}, device:{cam.device}')

                while True:
                    if self.new_img is not None:
                        try:
                            # Get the original image width and height
                            img_width, img_height = self.new_img.size
                            
                            # Calculate the image scale so it scales proportionally and fits the virtual camera width or height
                            scale = min(cam_width / img_width, cam_height / img_height)
                            new_size = (int(img_width * scale), int(img_height * scale))
                            
                            # Resize the image
                            resized_img = self.new_img.resize(new_size, Image.LANCZOS)

                            # Check whether there is an Alpha channel, and add one if not
                            if resized_img.mode != 'RGBA':
                                resized_img = resized_img.convert('RGBA')
                            
                            # Create a blank image with a custom background, the same size as the camera
                            custom_background = Image.new('RGBA', (cam_width, cam_height), self.rgba_color)
                            
                            # Calculate the centered position
                            paste_position = ((cam_width - new_size[0]) // 2, (cam_height - new_size[1]) // 2)
                            
                            # Paste the resized image into the center of the custom background
                            custom_background.paste(resized_img, paste_position, resized_img)
                            
                            # Convert the image to RGB (remove the Alpha channel)
                            rgb_img = custom_background.convert('RGB')
                            
                            # Convert the PIL image to a numpy array and set the data type to uint8
                            frame = np.array(rgb_img).astype(np.uint8)

                            # Send the image frame to the virtual camera
                            cam.send(frame)

                        except Exception as e:
                            logger.error(traceback.format_exc())
                            logger.error(f"Failed to update the virtual camera:{e}")

                    # Pause for a while
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to update the virtual camera:{e}")

    def save_image_locally(self, img):
        # Make sure there is a directory for saving images
        save_dir = self.sd_config["save_path"]
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        if self.sd_config["loop_cover"]:
            # Generate a file name that cycles and overwrites based on time
            filename = self.common.get_bj_time(4) + ".png"
        else:
            # Generate a unique file name based on time
            filename = self.common.get_bj_time(3) + ".png"

        # Save image
        img_path = os.path.join(save_dir, filename)
        img.save(img_path)
        logger.info(f"Image saved at:{img_path}")

    def process_input(self, user_input):

        # Call with the user input text as the prompt API
        """
            prompt: Main text prompt, specifying the subject or content of the generated image.
            negative_prompt: Negative text prompt, specifying content that contradicts or is the opposite of the generated image.
            seed: Random seed, controls the randomness of the generation process. An integer value can be set for reproducible results.
            styles: Style list, specifying the style of the generated image. Can contain multiple styles, e.g. ["anime", "portrait"].
            cfg_scale: Prompt relevance, Classifier Free Guidance Scale - how closely the image should follow the prompt; lower values produce more creative results.
            sampler_index: Sampler index, specifying the sampler used for image generation. Defaults to None.
            steps: Number of steps for image generation, controls the precision of generation.
            enable_hr: Whether to enable high-resolution generation. Defaults to False.
            hr_scale: High-resolution scale factor, specifying the high-resolution upscale level of the generated image.
            hr_upscaler: High-resolution upscaler type, specifying the upscaler used for high-resolution generation.
            hr_second_pass_steps: Number of second-pass steps for high-resolution generation.
            hr_resize_x: Horizontal size of the generated image.
            hr_resize_y: Vertical size of the generated image.
            denoising_strength: Denoising strength, controls the noise in the generated image.
        """
        try:
            result = self.api.txt2img(prompt=user_input,
                negative_prompt=self.sd_config["negative_prompt"],
                seed=self.sd_config["seed"],
                styles=self.sd_config["styles"],
                cfg_scale=self.sd_config["cfg_scale"],
                # sampler_index='DDIM',
                steps=self.sd_config["steps"],
                enable_hr=self.sd_config["enable_hr"],
                hr_scale=self.sd_config["hr_scale"],
                # hr_upscaler=webuiapi.HiResUpscaler.Latent,
                hr_second_pass_steps=self.sd_config["hr_second_pass_steps"],
                hr_resize_x=self.sd_config["hr_resize_x"],
                hr_resize_y=self.sd_config["hr_resize_y"],
                denoising_strength=self.sd_config["denoising_strength"],
            )

        
            # Get the returned image
            img = result.image
            self.new_img = img

            # Save the image locally
            if self.sd_config["save_enable"]:
                self.save_image_locally(img)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to call the SD API:{e}")
            return None

    def set_new_img(self, img_path: str):
        try:
            # Read the image
            img = Image.open(img_path)
            self.new_img = img
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Failed to read the image:{e}")
            return None
