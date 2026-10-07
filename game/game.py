import pyautogui
import time
import importlib
import traceback, logging

from utils.common import Common
from utils.logger import Configure_logger
from utils.config import Config


class Game:
    def __init__(self, config_path, data):
        self.config = Config(config_path)
        self.common = Common()

        try:
            self.module_name = importlib.import_module(data["module_name"])
        except Exception as e:
            logging.error(traceback.format_exc())
            raise e


    # Parse the string and simulate key/mouse press
    def parse_key_and_simulate_key_mouse_press(self, key):
        self.module_name.parse_key_and_simulate_key_mouse_press(key)


    # Parse the string array; based on the first character of the string, decide whether the key needs converting, then press the key
    def parse_keys_and_simulate_keys_press(self, keys):
        self.module_name.parse_keys_and_simulate_keys_press(keys)


    # Simulate pressing then releasing a key, taking a string array
    def simulate_key_press(self, keys):
        # Simulate pressing and releasing a key
        for key in keys:
            pyautogui.keyDown(key)
            time.sleep(0.1)
            pyautogui.keyUp(key)


    # Parse the string array; based on the first character of the string, decide whether the key needs converting, then press the key
    def parse_keys_and_simulate_key_press(self, keys):
        # Delete strings in the array other than w a s d 1 2 3
        def remove_needless(keys):
            for i in range(len(keys)):
                if keys[i] not in ['w', 'a', 's', 'd', '1', '2', '3']:
                    keys.pop(i)
            return keys
        
        if keys[0] == '1':
            keys = keys[1:]

            keys = remove_needless(keys)

            # Iterate over the array and change 123 toyui
            for i in range(len(keys)):
                if keys[i] == '1':
                    keys[i] = 'y'
                elif keys[i] == '2':
                    keys[i] = 'u'
                elif keys[i] == '3':
                    keys[i] = 'i'
        elif keys[0] == '2':
            keys = keys[1:]

            keys = remove_needless(keys)
            
            # Iterate over the array, change wsad to up/down/left/right and 123 to789
            for i in range(len(keys)):
                if keys[i] == 'w':
                    keys[i] = 'up'
                elif keys[i] == 's':
                    keys[i] = 'down'
                elif keys[i] == 'a':
                    keys[i] = 'left'
                elif keys[i] == 'd':
                    keys[i] = 'right'
                elif keys[i] == '1':
                    keys[i] = '7'
                elif keys[i] == '2':
                    keys[i] = '8'
                elif keys[i] == '3':
                    keys[i] = '9'

        self.simulate_key_press(keys)