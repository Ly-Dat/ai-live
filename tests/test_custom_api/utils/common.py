# Import the required libraries
import re, random, requests, json
import time
import os, glob
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import traceback

from urllib.parse import urlparse

import langid

from profanity import profanity
import ahocorasick

import difflib

import shutil
from send2trash import send2trash

from pypinyin import pinyin, Style

import pyaudio

import cv2



class Common:
    def __init__(self):  
        self.count = 1

    """
    Data validation
    """
    # Check whether it is purely digits
    def is_pure_number(self, text):
        """Check whether it is purely digits

        Args:
            text (str): Text to detect

        Returns:
            bool: Whether it is purely digits
        """
        return text.isdigit()


    # Whether it isurl
    def is_url_check(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False
        
    # Whether it is an IP address
    def is_valid_ip(self, ip):
        import ipaddress

        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    # Whether it is a port
    def is_valid_port(self, port):
        try:
            port_num = int(port)
            return 0 < port_num <= 65535
        except ValueError:
            return False

    # Identify the operating system
    def detect_os(self):
        """
        Identify the operating system
        """
        import platform

        system = platform.system()
        if system == 'Linux':
            return 'Linux'
        elif system == 'Windows':
            return 'Windows'
        elif system == 'Darwin':
            return 'MacOS'
        
        # If the platform module cannot identify it, try using the os module
        # system = os.name
        # if system == 'posix':
        #     return 'May be Linux orMacOS'
        # elif system == 'nt':
        #     return 'Windows'

        return '未知系统'

    """
    Number operations
    """

    # Get Beijing time
    def get_bj_time(self, type=0):
        """Get Beijing time

        Args:
            type (int, str): Return the time type. Default is 0.
                0 Returns: year-month-day hour:minute:second
                1 Returns: year-month-day
                2 Returns: seconds of the current time
                3 Returns: seconds since January 1, 1970
                4 Returns: a counter that cycles up to 100 based on the number of calls
                5 Returns: current hour:minute
                6 Returns: hour, minute of the current time
                7 Returns: year-month-day hour-minute-second millisecond

        Returns:
            str: Return a time string in the specified format
            int, int
        """
        if type == 0:
            utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)  # Get the current UTC time
            SHA_TZ = timezone(
                timedelta(hours=8),
                name='Asia/Shanghai',
            )
            beijing_now = utc_now.astimezone(SHA_TZ)  # Convert UTC time to Beijing time
            fmt = '%Y-%m-%d %H:%M:%S'
            now_fmt = beijing_now.strftime(fmt)
            return now_fmt
        elif type == 1:
            now = datetime.now()  # Get the current time
            year = now.year  # Get the current year
            month = now.month  # Get the current month
            day = now.day  # Get the current date

            return str(year) + "-" + str(month) + "-" + str(day)
        elif type == 2:
            now = time.localtime()  # Get the current time

            # hour = now.tm_hour   # Get the current hour
            # minute = now.tm_min  # Get the current minute 
            second = now.tm_sec  # Get the current second

            return str(second)
        elif type == 3:
            current_time = time.time()  # Return the seconds since January 1, 1970

            return str(current_time)
        elif type == 4:
            self.count = (self.count % 100) + 1

            return str(self.count)
        elif type == 5:
            now = time.localtime()  # Get the current time

            hour = now.tm_hour   # Get the current hour
            minute = now.tm_min  # Get the current minute

            return str(hour) + "点" + str(minute) + "分"
        elif type == 6:
            now = time.localtime()  # Get the current time

            hour = now.tm_hour   # Get the current hour
            minute = now.tm_min  # Get the current minute 

            return hour, minute
        elif type == 7:
            utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)  # Get the current UTC time
            SHA_TZ = timezone(
                timedelta(hours=8),
                name='Asia/Shanghai',
            )
            beijing_now = utc_now.astimezone(SHA_TZ)  # Convert UTC time to Beijing time
            fmt = '%Y-%m-%d %H-%M-%S %f'
            now_fmt = beijing_now.strftime(fmt)
            return now_fmt
    
    def get_random_value(self, lower_limit, upper_limit):
        """Get a random value between 2 numbers

        Args:
            lower_limit (float): Lower bound of the random number
            upper_limit (float): Upper bound of the random number

        Returns:
            float: 2Random value between the number of
        """
        if lower_limit == upper_limit:
            return round(lower_limit, 2)

        if lower_limit > upper_limit:
            lower_limit, upper_limit = upper_limit, lower_limit

        random_float = round(random.uniform(lower_limit, upper_limit), 2)
        return random_float
    

    def find_keys_by_value(self, dictionary, target_value):
        # Return a list of all keys that have the specified value
        return [key for key, value in dictionary.items() if value == target_value]


    """
                                                                                                              
                   .,]`                    ]]]`            ,]]`                      .`    .]`                
                  ,@@@@                    @@@^            =@@^  .@@@@@@@@@@@@^      /@@@  /@@@               
         =@@@@@@@@@@@@@@@@@@@@@@^ O@@@@@@@@@@@@@@@@@@@@@ ..=@@\...@@@]]]]]]/@@^     =@@@` =@@@@@@@@@@@@@\     
         =@@@@@@@@@@@@@@@@@@@@@@^ O@@@@@@@@@@@@@@@@@@@@@ =@@@@@@^.@@@@@@@@@@@@^    ,@@@^ ,@@@@@@@@@@@@@@@     
             =@@@^      /@@@^            /@@@@@@\          =@@^ .@@@@@@O.@@@@@@@  ,@@@@^=@@@^=@@@.            
              =@@@^    =@@@/           ,@@@@@@@@@@`        =@@^..@@^.@@@.@@^.@@@ ,@@@@@^\@@` =@@@@@@@@@^      
               \@@@\ ./@@@/          ,@@@@`@@@^.@@@@`    /@@@@@@*@@@@@@@.@@@@@@@ =@@@@@^ \.  =@@@@@@@@@^      
                ,@@@@@@@@`         ,@@@@/  @@@^  =@@@@]  =@@@@/`      =@@O       .@.@@@^     =@@@.            
                 ]@@@@@@`        =@@@@@]]]]@@@\]]]]@@@@@^  =@@^ @@@@@@@@@@@@@@@@^   @@@^     =@@@@@@@@@@      
             ,/@@@@@@@@@@@@\`     ,@/.=@@@@@@@@@@@@^ \/.   =@@^    ,@@@@@@@@]       @@@^     =@@@@@@@@@@      
         =@@@@@@@@/.  .\@@@@@@@@`          @@@^          ,]/@@^,/@@@@`=@@@.\@@@@`   @@@^     =@@@.            
          ,@@@/`          ,\@@/.           @@@^          =@@@@` ,@[.  =@@@   ,\`    @@@^     =@@@.            
                                                                                                              

    """

    # Generate a hash string for gradio requests
    def generate_session_hash(self, length: int=11):
        import hashlib
        import string

        characters = string.ascii_letters + string.digits
        random_string = ''.join(random.choice(characters) for i in range(length))
        hash_object = hashlib.sha1(random_string.encode())
        session_hash = hash_object.hexdigest()[:length]

        return session_hash

    # Convert digits in the string to Chinese numerals
    def convert_digits_to_chinese(self, input_str: str):
        """Convert digits in the string to Chinese numerals

        Args:
            input_str (str): String to convert

        Returns:
            str: Converted string
        """
        # Define the mapping from Arabic numerals to Chinese numerals
        digit_to_chinese = {
            '0': '零',
            '1': '一',
            '2': '二',
            '3': '三',
            '4': '四',
            '5': '五',
            '6': '六',
            '7': '七',
            '8': '八',
            '9': '九'
        }

        # Iterate over the input string and replace digits with Chinese numerals
        result = ''.join(digit_to_chinese.get(char, char) for char in input_str)
        
        return result

    # Remove extra words
    def remove_extra_words(self, text="", max_len=30, max_char_len=50):
        words = text.split()
        if len(words) > max_len:
            words = words[:max_len]  # List slicing, keep the first 30 words
            text = ' '.join(words) + '...'  # Use join() to recombine the word list into a string and append an ellipsis at the end
        return text[:max_char_len]


    # Local sensitive word detection; pass in the sensitive word library file path and the text to check
    def check_sensitive_words(self, file_path, text):
        with open(file_path, 'r', encoding='utf-8') as file:
            sensitive_words = [line.strip() for line in file.readlines()]

        for word in sensitive_words:
            if word in text:
                return True

        return False
    

    # Local sensitive word detection with the Aho-Corasick algorithm; pass in the sensitive word library file path and the text to check
    def check_sensitive_words2(self, file_path, text):
        with open(file_path, 'r', encoding='utf-8') as file:
            sensitive_words = [line.strip() for line in file.readlines()]

        # Create the Aho-Corasick automaton
        automaton = ahocorasick.Automaton()

        # Add banned words to the automaton
        for word in sensitive_words:
            automaton.add_word(word, word)

        # Build the automaton transition function and failure function
        automaton.make_automaton()

        # Search for banned words in the text
        for _, found_word in automaton.iter(text):
            logging.warning(f"Hit local banned word: {found_word}")
            return found_word

        return None


    # Local sensitive word to pinyin detection; pass in the sensitive word library file path and the text to check
    def check_sensitive_words3(self, file_path, text):
        with open(file_path, 'r', encoding='utf-8') as file:
            sensitive_words = [line.strip() for line in file.readlines()]

        pinyin_text = self.text2pinyin(text)
        # logging.info(f"pinyin_text={pinyin_text}")

        for word in sensitive_words:
            pinyin_word = self.text2pinyin(word)
            pattern = r'\b' + re.escape(pinyin_word) + r'\b'
            if re.search(pattern, pinyin_text):
                logging.warning(f"Homophone banned pinyin: {pinyin_word}")
                return True

        return False


    # Language detection TODO: risk of memory leak
    def lang_check(self, text, need="none"):
        # Language detection: one is the language, the other is the probability
        language, score = langid.classify(text)

        if need == "none":
            return language
        else:
            if language != need:
                return None
            else:
                return language


    # Check whether the string consists entirely of punctuation
    def is_punctuation_string(self, string):
        # Match punctuation with a regular expression
        pattern = r'^[^\w\s]+$'
        return re.match(pattern, string) is not None
    
    # Check whether the string consists entirely of spaces and special characters
    def is_all_space_and_punct(self, text):
        pattern = r'^[\s\W]+$'
        return re.match(pattern, text) is not None

    # Banned word check
    def profanity_content(self, content):
        return profanity.contains_profanity(content)

    # Check whether the string starts with any string in a list
    def starts_with_any(self, string, prefixes):
        """Check whether the string starts with any string in a list

        Args:
            string (str): String to check
            prefixes (list): Array of matched strings

        Returns:
            str: The matched string that was hit/None
        """
        try:
            for prefix in prefixes:
                if string.startswith(prefix):
                    return prefix
        except AttributeError as e:
            # Handle the exception, e.g. print an error message or return False
            logging.error(f"Error: {e}")
            return None
        
        return None

    # Chinese sentence splitting (split only by specific symbols)
    def split_sentences1(self, text):
        # Split sentences with a regular expression
        # .Filtering may cause numbered replies to be split
        sentences = re.split('([。！？!?])', text)
        result = []
        for sentence in sentences:
            if sentence not in ["。", "！", "？", ".", "!", "?", ""]:
                result.append(sentence)
        
        # Replace newlines
        result = [s.replace('\n', '。') for s in result]

        # print(result)
        return result
    

    # Text splitting algorithm, old algorithm with a maximum length limit
    def split_sentences2(self, text):
        # Maximum length limit, exceeding it forces a split
        max_limit_len = 40

        # Split sentences with a regular expression
        sentences = re.split('([。！？!?])', text)
        result = []
        current_sentence = ""
        for i in range(len(sentences)):
            if sentences[i] not in ["。", "！", "？", ".", "!", "?", ""]:
                # Remove newlines and spaces
                sentence = sentences[i].replace('\n', '。')
                # If the sentence is shorter than 10 characters, merge it with the next one
                if len(current_sentence) < 10:
                    current_sentence += sentence
                    # If the merged sentence is longer than max_limit_len characters, split it a second time
                    if len(current_sentence) > max_limit_len:
                        # Check whether there is a separator available for secondary splitting
                        if i+1 < len(sentences) and len(sentences[i+1]) > 0 and sentences[i+1][0] not in ["。", "！", "？", ".", "!", "?"]:
                            next_sentence = sentences[i+1].replace('\n', '。')
                            # Look for common separators for a secondary split
                            for separator in [",", "，", ";", "；"]:
                                if separator in next_sentence:
                                    split_index = next_sentence.index(separator) + 1
                                    current_sentence += next_sentence[:split_index]
                                    result.append(current_sentence)
                                    current_sentence = next_sentence[split_index:]
                                    break
                        else:
                            # If the merged sentence is longer than max_limit_len characters, perform a secondary split
                            while len(current_sentence) > max_limit_len:
                                result.append(current_sentence[:max_limit_len])
                                current_sentence = current_sentence[max_limit_len:]
                else:
                    result.append(current_sentence)
                    current_sentence = sentence

        # Add the last sentence
        if current_sentence:
            result.append(current_sentence)

        # 2Split the long string a number of times
        result2 = []
        for string in result:
            if len(string) > max_limit_len:
                split_strings = re.split(r"[,，;；。！!]", string)
                result2.extend(split_strings)
            else:
                result2.append(string)

        return result2


    # Text splitting algorithm
    def split_sentences(self, text):
        # Split sentences with a regular expression
        sentences = re.split(r'(?<=[。！？!?])', text)
        result = []
        current_sentence = ""
        
        for sentence in sentences:
            # Remove newlines and spaces
            sentence = sentence.replace('\n', '')
            
            # Skip if the sentence is empty
            if not sentence:
                continue
            
            # If the sentence is shorter than 10 characters, merge it with the next one
            if len(current_sentence) < 10:
                current_sentence += sentence
            else:
                # Check whether the current sentence ends with punctuation
                if current_sentence[-1] in ["。", "！", "？", ".", "!", "?"]:
                    result.append(current_sentence)
                    current_sentence = sentence
                else:
                    # If the current sentence does not end with punctuation, perform a secondary split
                    split_sentences = re.split(r'(?<=[,，;；])', current_sentence)
                    if len(split_sentences) > 1:
                        result.extend(split_sentences[:-1])
                        current_sentence = split_sentences[-1] + sentence
                    else:
                        current_sentence += sentence
        
        # Add the last sentence
        if current_sentence:
            result.append(current_sentence)
        
        return result


    # String matching algorithm to compute the similarity between strings and pick the string with the highest match as the result
    def find_best_match(self, substring, string_list, similarity=0.5):
        """String matching algorithm to compute the similarity between strings and pick the string with the highest match as the result

        Args:
            substring (str): Substring to search for
            string_list (list): List of strings
            similarity (float): Minimum similarity

        Returns:
            _type_: Matched string or None
        """
        best_match = None
        best_ratio = 0
        
        for string in string_list:
            ratio = difflib.SequenceMatcher(None, substring, string).ratio()
            # print(f"String: {string}, Ratio: {ratio}")  # Add debug statements to output the similarity of each string
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = string
        
        # If the similarity is below similarity, the match is considered unsuccessful
        if best_ratio < similarity:
            return None

        return best_match
    

    # Check whether any string in the list is a substring of the query string.
    def find_substring_in_list(self, query_string, string_list):
        """
        Check whether any string in the list is a substring of the query string.

        Args:
        query_string (str): String to look up.
        string_list (list of str): List of strings being queried.

        Returns:
        str or None: If the substring is found, return it; otherwise return None.
        """
        for string in string_list:
            if string in query_string:
                return string
        return None


    def text2pinyin(self, text):
        """Text to pinyin

        Args:
            text (str): Pass in the text to convert

        Returns:
            str: Pinyin string
        """
        pinyin_list = []
        for char in text:
            # Convert each Chinese character to pinyin
            char_pinyin_list = pinyin(char, style=Style.NORMAL)
            if char_pinyin_list:
                _pinyin = char_pinyin_list[0][0]
            else:
                _pinyin = char
            
            # Convert ü etc. tov
            _pinyin = re.sub(r"ü", "v", _pinyin)
            
            pinyin_list.append(_pinyin)

        return " ".join(pinyin_list)


    def merge_consecutive_asterisks(self, s):
        """Merge the consecutive ones at the end of the string*

        Args:
            s (str): String to process

        Returns:
            str: String after processing
        """
        # Iterate from the end of the string to find the start index of the consecutive *
        idx = len(s) - 1
        while idx >= 0 and s[idx] == '*':
            idx -= 1

        # If more than 3 consecutive * are found, replace them
        if len(s) - 1 - idx > 3:
            s = s[:idx + 1] + '*' + s[len(s) - 1:]

        return s


    def replace_special_characters(self, input_string, special_characters):
        """
        Replace the specified special characters with empty strings.

        Args:
            input_string (str): Input string whose special characters are to be replaced.
            special_characters (str): String containing the special characters to be replaced.

        Returns:
            str: String after replacement.
        """
        for char in special_characters:
            input_string = input_string.replace(char, "")
        
        return input_string


    # Split the cookie data string into a list of key-value pairs
    def parse_cookie_data(self, data_str, field_name):
        """Split the cookie data string into a list of key-value pairs

        Args:
            data_str (str): Cookie string from which to extract data
            field_name (str): Key name to extract

        Returns:
            str: Value corresponding to the key
        """
        # Split the data string into a list of key-value pairs
        key_value_pairs = data_str.split(';')

        # print(key_value_pairs)

        # Iterate over the key-value list to find the specified field name
        for pair in key_value_pairs:
            key, value = pair.strip().split('=')
            if key == field_name:
                return value

        # If the specified field is not found, return an empty string
        return ""


    # Dynamic variable replacement
    def dynamic_variable_replacement(self, template, data_json):
        """Dynamic variable replacement

        Args:
            template (str): String whose variables are to be replaced
            data_json (dict): Variable JSON data used for replacement

        Returns:
            str: String after replacement is complete
        """
        pattern = r"{(\w+)}"
        var_names = re.findall(pattern, template)

        for var_name in var_names:
            if var_name in data_json:
                template = template.replace("{"+var_name+"}", str(data_json[var_name]))
            else:
                # Variable does not exist, keep as is
                pass

        logging.debug(f"template={template}")

        return template


    # [1|2]Bracket syntax randomly picks a value and returns the string after the value is substituted
    def brackets_text_randomize(self, text: str):
        """
        [1|2]Bracket syntax randomly picks a value and returns the string after the value is substituted
        Args:
            text (str): Original string

        Returns:
            str: Final string
        """
        # Find all content inside brackets
        brackets_content = re.findall(r'\[([^\]]*)\]', text)
        
        for content in brackets_content:
            # Split the options inside each bracket
            choices = content.split('|')
            # Randomly pick one from the options
            random_choice = random.choice(choices)
            # Replace the bracketed content in the text
            text = text.replace(f'[{content}]', random_choice, 1)
        
        return text

    """
    
            .@@@             @@@        @@^ =@@@@@@@@    /@@ /@@              =@@@@@*,@@\]]]]  ,@@@@@@@@@@@@*                      .@@@         @@/.\]`@@@       =@@\]]]]]]]   =@@..@@@@@@@@@   =@@\   /@@^           
      *@@@@@@@@@@@@@@@*=@@@@@@@@@@@@@@.@@@@@=@@@@@@@@   =@@`=@@@@@@@@@^       =@/[@@@@@@@@@@/.@@@`     .]@@/                 *@@@@@@@@@@@@@@@* =@@.=@@]@@@]]]. ,@@@@@@@@@@@@ ,@@@@@@@@/[[[\@@ =@@@@@@@@@@@@@^         
         =@@`   ,@@^       .@@@@@.      @@^=@@@@^@@@@@ =@@@=@@`@@^            =@@@@@,[@@@@@/  \/,@@`]/@@@@@]                    =@@`   ,@@^   ,@@@,@@@@@@@@@/.\@/,@@@`/@@@`  .[\@@[[@@@@@@@@@ ,[[[[[@@@[[[[[`         
          \@@` ,@@/       /@@@@@@@\    .@@@O@\/@^@@]@@=@@@@,@`*@@@@@@^        ]]=@@=@@@@@@@@@^,@@@,@@/`  .\@@.                   \@@` ,@@/   ,@@@@[@/  @@@       ,]@@@@[      ,@@@@\@@^   =@@.@@@@@@@@@@@@@@@`        
           =@@@@@^     ./@@/ @@@ \@@\`=@@@/`   =@@     @=@@   *@@^     =@@@@^ @@=@@@,@@@@@@@^,@@@^.@@@@@@@@@^                     =@@@@@^    .@\@@@@@@@@@@@@@/@@@@@@@@@@@@@@.,@@@@[`@@@@@@@@@.[[[[[\@@@/[[[[[`        
          ,/@@@@@\`   .\@/@@@@@@@@@\@/  @@^\@@@@@@@@@/. =@@   *@@@@@@@        @@=@@ *@@[[[@@^ .=@^    =@@.    ./`                ,/@@@@@\`     =@@     @@@      @@@      =@@..@=@@..@@^   =@@    ,/@@[@@@`            
      .@@@@@@` ,\@@@@@`      @@@      ,]@@^/@@/=@@[@@@` =@@   *@@^           =@@@@@@^@@@@@@@^  =@^@@@@@@@@@@@^,@@@`          .@@@@@@` ,\@@@@@` =@@     @@@      @@@@@@@@@@@@.  =@@..@@@@@@@@@./@@@@/   [@@@@@`        
       .[`         ,[        \@/      .[[[ ..  ,@/      ,@/   .@@`            .     .@/.  \@`  ,[`,[[[[[[[[[[.  ,[            .[`         ,[   ,@/     \@/      \@/      ,[[.  ,@/..\@`   ,@/ .[[         ,[    
    
    """
    
    # Read all text content from the specified file and return it; create the file if it does not exist
    def read_file_return_content(self, file_path):
        try:
            if not os.path.exists(file_path):
                logging.warning(f"File does not exist, a new file will be created: {file_path}")
                # Create the file
                with open(file_path, 'w', encoding='utf-8') as file:
                    content = ""
                return content
        
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except IOError as e:
            logging.error(f"Unable to write to the file:{file_path}\n{e}")
            return None


    
    # Split a file path string into the path and the file name
    def split_path_and_filename(self, file_path):
        folder_path, file_name = os.path.split(file_path)
        # Check whether the end of the path already contains'/', if none, add
        if not folder_path.endswith('/'):
            folder_path += '/'
        
        return folder_path, file_name


    # Extract the file name with extension from the file path
    def extract_filename(self, file_path, with_extension=False):
        """Extract the file name with extension from the file path

        Args:
            file_path (_type_): File path
            with_extension (bool, optional): Whether the extension is needed. Defaults to False.

        Returns:
            str: File name
        """
        file_name_with_extension = os.path.basename(file_path)
        if with_extension:
            return file_name_with_extension
        else:
            file_name_without_extension = os.path.splitext(file_name_with_extension)[0]
            return file_name_without_extension


    # Get the names of all folders under the specified folder
    def get_folder_names(self, path):
        folder_names = next(os.walk(path))[1]
        return folder_names


    # Return the absolute paths of all files in the specified folder (including file extensions)
    def get_all_file_paths(self, folder_path):
        """Return the absolute paths of all files in the specified folder (including file extensions)

        Args:
            folder_path (str): Folder path

        Returns:
            list: List of absolute file paths
        """
        file_paths = []  # List used to store absolute file paths

        # Use os.walk to traverse all files and subfolders in the folder
        for root, directories, files in os.walk(folder_path):
            for filename in files:
                file_path = os.path.join(root, filename)  # Get the absolute path of the file
                file_paths.append(file_path)

        return file_paths

    # Get the list of file names with the specified extension under the specified path
    def get_specify_extension_names_in_folder(self, path: str, extension: str):
        """
        Get the list of file names with the specified extension under the specified path

        Parameters:
            path (str): Specified path
            extension (str): Specified extension (e.g. .json, .txt, .jpg, etc.)

        Returns:
            list: File name list
        """
        if not os.path.exists(path):
            logging.error(f"Path '{path}' Does not exist")
            return []

        file_names = glob.glob(os.path.join(path, f"*{extension}"))
        return [os.path.basename(file_name) for file_name in file_names]

    def remove_extension_from_list(self, file_name_list):
        """
        Remove the extensions from a list of file names with extensions and return a new list of just the file names

        Args:
            file_name_list (list): List containing multiple file names with extensions

        Returns:
            list: New list made of file names
        """
        # Use a list comprehension to process the whole list and remove the extension of each file name
        file_name_without_extension_list = [file_name.split('.')[0] for file_name in file_name_list]
        return file_name_without_extension_list


    def is_audio_file(self, file_path):
        """Check whether the file is an audio file

        Args:
            file_path (str): File path

        Returns:
            bool: True / False
        """
        # List of supported audio file extensions
        SUPPORTED_AUDIO_EXTENSIONS = ['.mp3', '.wav', '.MP3', '.WAV', '.ogg']

        _, extension = os.path.splitext(file_path)
        return extension.lower() in SUPPORTED_AUDIO_EXTENSIONS


    def random_search_a_audio_file(self, root_dir):
        """Search all audio files in the specified folder and randomly return one audio file path

        Args:
            root_dir (str): Folder path to search

        Returns:
            str: Randomly return an audio file path
        """
        audio_files = []

        for root, dirs, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                relative_path = relative_path.replace("\\", "/")

                logging.debug(file_path)

                # Check whether the file is an audio file
                if self.is_audio_file(relative_path):
                    audio_files.append(file_path)

        if audio_files:
            # Randomly return an audio file path
            return random.choice(audio_files)
        else:
            return None

    # Get the Live2D model name
    def get_live2d_model_name(self, path):
        content = self.read_file_return_content(path)
        if content is None:
            logging.error(f"Failed to read Live2D model name")
            return None
        
        pattern = r'"(.*?)"'
        result = re.search(pattern, content)

        if result:
            content = result.group(1)
            return content
        else:
            return None



    """
                                                                                                 
              .]]@@              .@]]       @@@@        O@@`  ,]]]]]]]]]]]].      /]]   /@]`                  
               =@@@\             =@@@`.@@@^ @@@@        @@@^  =@@@@@@@@@@@@.     =@@@` =@@@`                  
      @@@@@@@@@@@@@@@@@@@@@@@   ,@@@^ =@@@` @@@@      ]]@@@\]`=@@@@@@@@@@@@.    ,@@@^ ,@@@@@@@@@@@@@@^        
      @@@@@@@@@@@@@@@@@@@@@@@  .@@@@ .@@@@@@@@@@@@@@@ @@@@@@@^,[[[[[[[[[[[[.   .@@@@..@@@@@@@@@@@@@@@`        
          \@@@`     =@@@@     .@@@@@ =@@@[[[@@@@[[[[`   @@@^ =@@@@@@^=@@@@@@^ .@@@@@,@@@/ @@@^                
          .@@@@`   ,@@@@.     /@@@@@,@@@^   @@@@        @@@\]=@@ =@@^=@@.=@@^.@@@@@@.@@/  @@@@@@@@@@          
            \@@@\./@@@@      .@@@@@@,]]]]]]]@@@@]]]]]/@@@@@@@=@@@@@@^=@@@@@@^ @@O@@@..`   @@@/[[[[[[          
             =@@@@@@@^        =/=@@@=@@@@@@@@@@@@@@@@^@@@@@^,]]]]]]@@@\]]]]]] =`=@@@.     @@@^                
            ./@@@@@@@]          =@@@        @@@@        @@@^=@@@@@@@@@@@@@@@@   =@@@.     @@@@@@@@@@^         
        ,]@@@@@@@[@@@@@@@]`     =@@@        @@@@        @@@^  .]@@@@@@@@@\.     =@@@.     @@@/[[[[[[`         
      \@@@@@@@[    .[@@@@@@@/   =@@@        @@@@     .@@@@@`@@@@@` @@@^.\@@@@.  =@@@.     @@@^                
       ,@/[            .[\@`    =@@@        @@@@      \@@@`  ,`    @@@^   .[    =@@@.     @@@^             

    """
    def ensure_directory_exists(self, path):
        # Check whether the path exists
        if not os.path.exists(path):
            # If the path does not exist, create it
            os.makedirs(path)
            logging.info(f"Path created:{path}")

    # Write content to the specified file, returnsT/F
    def write_content_to_file(self, file_path, content, write_log=True):
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)

            if write_log == True:
                logging.info(f"Write file: {file_path}, content: [{content}]")

            return True
        except IOError as e:
            logging.error(f"Unable to write [{content}] to the file:{file_path}\n{e}")
            return False

    # Move the file to the specified path src dest
    def move_file(self, source_path, destination_path, rename=None, format="wav"):
        """Move the file to the specified path

        Args:
            source_path (str): File path including file name
            destination_path (_type_): Target folder
            rename (str, optional): File name. Defaults to None.
            format (str, optional): File format (actually just a fake extension). Defaults to "wav".

        Returns:
            str: Full output path including file name
        """
        logging.debug(f"source_path={source_path},destination_path={destination_path},rename={rename}")

        # if os.path.exists(destination_path):
        #     # If a file with the same name already exists at the target location, move it to the recycle bin first
        #     send2trash(destination_path)
        
        # if rename is not None:
        #     destination_path = os.path.join(os.path.dirname(destination_path), rename)
        
        # shutil.move(source_path, destination_path)
        # logging.info(f"File moved successfully: {source_path} -> {destination_path}")
        destination_directory = os.path.dirname(destination_path)
        logging.debug(f"destination_directory={destination_directory}")
        destination_filename = os.path.basename(source_path)

        if rename is not None:
            destination_filename = rename + "." + format
        
        destination_path = os.path.join(destination_directory, destination_filename)
        
        if os.path.exists(destination_path):
            # If a file with the same name already exists at the target location, delete it first
            os.remove(destination_path)

        shutil.move(source_path, destination_path)
        print(f"File moved successfully: {source_path} -> {destination_path}")

        return destination_path


    # Delete the file
    def del_file(self, file_path) -> bool:
        """
        Delete the file

        Args:
            file_path (str): File path

        Returns:
            bool:True/False
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"File deleted successfully: {file_path}")

                return True
            
            logging.error(f"File does not exist: {file_path}")
            return False
        except Exception as e:
            logging.error(traceback.format_exc())
            return False

    """
    
                   ,@@@^              .@@@. .@@@@@@@@@@@@.  .@@@.  ,]]]]]]]]]]]]`     ]@@@`     ,@@@\.        
          .@@@@@@@@@@@@@@@@@@@@@^ .@@O.@@@\]`@@@@@@@@@@@@.  .@@@.  =@@@@@@@@@@@@^      \@@@@.  =@@@/          
              .]@@^     ,@@\`     .@@O.@@@@@^,]]/@@@]]]]`.@@@@@@@@@=@@^     .@@@^  =@@@@@@@@@@@@@@@@@@@@      
         .@@@@@@@@@@@@@@@@@@@@@@@..@@O.@@@.  =@@@@@@@@@@^.[[[@@@/[[=@@@]]]]]/@@@^  =@@@@@@@@@@@@@@@@@@@O      
         .@@@@@@@@@@@@@@@@@@@@@@@*@@@@@@@@@@@=@@^,]]`=@@^   /@@@`  =@@@@@@@@@@@@^          =@@@^              
            =@@@@@@@@@@@@@@@@@^       =@@O   =@@^=@@^=@@^  /@@@@@@@/@@^     .@@@^.@@@@@@@@@@@@@@@@@@@@@@@.    
            =@@@@@@@@@@@@@@@@@^    /@@\@@O=@@/@@^=@@^=@@^./@@@@@[@`=@@@@@@@@@@@@^.O@@@@@@@@@@@@@@@@@@@@@O.    
            =@@@]]]]]]]]]]]@@@^   =@@^=@@@@@/=@@^@@@.=@@^.@@`@@@.  =@@@@@@@@@@@@^        .@@@@@@@`            
            =@@@@@@@@@@@@@@@@@^  .,\^ ./@@@^ ,[[@@@@\,[[` =`.@@@.  =@@^     .@@@^      ,@@@@/ \@@@@]          
            =@@@]]]]]]]]]]]@@@^    .]@@@@/   ,/@@@/@@@@]    .@@@.  =@@@@@@@@@@@@^ .,/@@@@@/.   .\@@@@@@\].    
            =@@@@@@@@@@@@@@@@@^   \@@@@`   ,@@@@[   .\@@@.  .@@@.  =@@@@@@@@@@@@^ ,@@@@@`         ,\@@@/.     
            ....           ....    ,.        ,.        .     ...   ....     .....   .                        

    """
    # Get the new audio path
    def get_new_audio_path(self, audio_out_path, file_name):
        # Check whether the path is absolute
        if os.path.isabs(audio_out_path):
            # If it is an absolute path, use it directly
            voice_tmp_path = os.path.join(audio_out_path, file_name)
        else:
            # If it is not an absolute path, check whether it contains ./; if not, add ./ and then join the path
            if not audio_out_path.startswith('./'):
                audio_out_path = './' + audio_out_path
            voice_tmp_path = os.path.normpath(os.path.join(audio_out_path, file_name))

        voice_tmp_path = os.path.abspath(voice_tmp_path)

        return voice_tmp_path

    # Get info on all sound card devices
    def get_all_audio_device_info(self, type):
        """Get info on all sound card devices

        Args:
            type (str): Sound card type, "in" Or "out"

        Returns:
            list: Sound card device info list
        """
        audio = pyaudio.PyAudio()
        device_infos = []
        device_count = audio.get_device_count()

        for device_index in range(device_count):
            device_info = audio.get_device_info_by_index(device_index)
            if type == "out":
                if device_info['maxOutputChannels'] > 0:
                    device_infos.append({"device_index": device_index, "device_info": device_info['name']})
            elif type == "in":
                if device_info['maxInputChannels'] > 0:
                    device_infos.append({"device_index": device_index, "device_info": device_info['name']})
            else:
                device_infos.append({"device_index": device_index, "device_info": device_info['name']})

        return device_infos

    """

                                                                        ..        ,]]].                ,]]].  ,]            
    .@@@@.      ,@@@\ .@@@@@@@@@@@@@@`@@@@@@@@@@@@@@` =@@@@@@\]]`    =@@@^ ,]]]]]/@@@\]]]]]]          =@@@. \@@@@`         
    .@@@@.      =@@@@ *@@@@@@@@@@@@@@^@@@@@@@@@@@@@@^ =@@@@@@@@@@@\   ,@@@\,[[[[[\@@@[[[[[[[ ]]]]]]]]]/@@@\]]]/@\]]]       
    .@@@@.      =@@@@      .@@@@.         .@@@@.      =@@@^   .@@@@^   .[` .@@@@@@@@@@@@@@@. @@@@@@@@@@@@@@@@@@@@@@@       
    .@@@@.      =@@@@      .@@@@.         .@@@@.      =@@@^    =@@@@,]]]]],]]]]]]/@@@]]]]]]]`  ,@`    =@@@`     /\.        
    .@@@@@@@@@@@@@@@@      .@@@@.         .@@@@.      =@@@^  .]@@@@`=@@@@@,[[[[[[[[[[[[[[[[[` ,@@@@\. =@@@@` ./@@@@`       
    .@@@@@@@@@@@@@@@@      .@@@@.         .@@@@.      =@@@@@@@@@@/.   =@@@  =@@@@@@@@@@@@@^     .\@@` =@@@@@@@@@/.         
    .@@@@.      =@@@@      .@@@@.         .@@@@.      =@@@/[[`.       =@@@  =@@@]]]]]]]@@@^       ,/@@@@@@\@@@\            
    .@@@@.      =@@@@      .@@@@.         .@@@@.      =@@@^           =@@@.`=@@@@@@@@@@@@@^  .]@@@@@@/\@@@.,@@@@@]         
    .@@@@.      =@@@@      .@@@@.         .@@@@.      =@@@^           =@@@@@=@@@@@@@@@@@@@^  \@@@/`   =@@@.  ,@@@@@@       
    .[[[[.      ,[[[[      .[[[[.         .[[[[.      ,[[[`           =@@@@[=@@@      .@@@^   [.  @@@@@@@@.     [@/        
                                                                    .@/.  =@@@  ,@@@@@@@.       =@@@@@@`            
                                                                    
    """
    def send_request(self, url, method='GET', json_data=None, resp_data_type="json", timeout=60):
        """
        Send an HTTP request and return the result

        Parameters:
            url (str): Requested URL
            method (str): Request method,'GET' Or 'POST'
            json_data (dict): JSON Data, used for the POST request
            resp_data_type (str): Type of returned data (json | content)
            timeout (int): Request timeout

        Returns:
            dict|str: JSON data containing the response | string data
        """
        headers = {'Content-Type': 'application/json'}

        try:
            if method in ['GET', 'get']:
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method in ['POST', 'post']:
                response = requests.post(url, headers=headers, data=json.dumps(json_data), timeout=timeout)
            else:
                raise ValueError('Invalid method. Supported methods are GET and POST.')

            # Check whether the request succeeded
            response.raise_for_status()

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

    async def send_async_request(self, url, method='GET', json_data=None, resp_data_type="json", timeout=60):
        """
        Send an asynchronous HTTP request and return the result

        Parameters:
            url (str): Requested URL
            method (str): Request method,'GET' Or 'POST'
            json_data (dict): JSON Data, used for the POST request
            resp_data_type (str): Type of returned data (json | content)
            timeout (int): Request timeout

        Returns:
            dict|str: JSON data containing the response | string data
        """
        import aiohttp

        headers = {'Content-Type': 'application/json'}

        try:
            # Create aiohttp.ClientSession
            async with aiohttp.ClientSession() as session:
                if method in ['GET', 'get']:
                    async with session.get(url, headers=headers, timeout=timeout) as response:
                        # Check whether the request succeeded
                        response.raise_for_status()

                        if resp_data_type == "json":
                            # Parse the JSON response data
                            result = await response.json()
                        else:
                            result = await response.read()

                elif method in ['POST', 'post']:
                    async with session.post(url, headers=headers, data=json.dumps(json_data), timeout=timeout) as response:
                        # Check whether the request succeeded
                        response.raise_for_status()

                        if resp_data_type == "json":
                            # Parse the JSON response data
                            result = await response.json()
                        else:
                            result = await response.read()

                else:
                    raise ValueError('Invalid method. Supported methods are GET and POST.')

                return result

        except aiohttp.ClientError as e:
            logging.error("Request error: %s", e)
            return None

    # Request the web subtitle printer
    def send_to_web_captions_printer(self, api_ip_port, data):
        """Request the web subtitle printer

        Args:
            api_ip_port (str): apiRequest URL
            data (dict): Contains the username and danmaku content

        Returns:
            bool: True/False
        """

        # username = data["username"]
        content = data["content"]

        # Record database):
        try:
            response = requests.get(url=api_ip_port + f'/send_message?content={content}')
            response.raise_for_status()  # Check the response status code

            result = response.content
            ret = json.loads(result)

            logging.debug(ret)

            if ret['code'] == 200:
                logging.debug(ret['message'])
                return True
            else:
                logging.error(ret['message'])
                return False
        except Exception as e:
            logging.error('webSubtitle printer request failed! Please confirm the config is correct or the server is running!')
            logging.error(traceback.format_exc())
            return False
        
    
    # openai Test key availability
    def test_openai_key(self, data_json, type=1):
        if type == 1:
            from urllib.parse import urljoin
            
            # Check availability
            def check_useful(data_json):
                # Try calling the list engines endpoint
                try:
                    api_key = data_json["api_keys"].split('\n')[0].rstrip()

                    url = urljoin(data_json["base_url"], '/v1/chat/completions')

                    logging.debug(f"url=[{url}], api_keys=[{api_key}]")
    
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    }

                    data = {
                        "model": data_json["model"],
                        "messages": [{"role": "user", "content": "hi"}],
                        "temperature": data_json["temperature"],
                        "max_tokens": data_json["max_tokens"],
                        "top_p": data_json["top_p"],
                        "presence_penalty": data_json["presence_penalty"],
                        "frequency_penalty": data_json["frequency_penalty"]
                    }

                    response = requests.post(url, headers=headers, json=data)
                    response_data = response.json()

                    logging.debug(response_data)

                    resp = response_data["choices"][0]["message"]["content"]

                    logging.info("OpenAI API key Available")

                    return {"code": 200, "msg": "OpenAI API key 可用"}
                except Exception as e:
                    logging.error(traceback.format_exc())
                    logging.error(f"OpenAI API key Unavailable: {e}")
                    return {"code": -1, "msg": f"OpenAI API key 不可用: {e}"}
        else:
            import openai
            from packaging import version

            # os.environ['http_proxy'] = "http://127.0.0.1:10809"
            # os.environ['https_proxy'] = "http://127.0.0.1:10809"

            # Check availability
            def check_useful(data_json):
                # Try calling the list engines endpoint
                try:
                    api_key = data_json["api_keys"].split('\n')[0].rstrip()

                    logging.info(f'base_url=[{data_json["base_url"]}], api_keys=[{api_key}]')

                    # openai.base_url = self.data_openai['api']
                    # openai.api_key = self.data_openai['api_key'][0]

                    logging.debug(f"openai.__version__={openai.__version__}")

                    openai.api_base = data_json["base_url"]
                    openai.api_key = api_key

                    # Check the openai library version; 1.x.x and 0.x.x have breaking changes
                    if version.parse(openai.__version__) < version.parse('1.0.0'):
                        # Call the ChatGPT API to generate a reply message
                        resp = openai.ChatCompletion.create(
                            model=data_json["model"],
                            messages=[{"role": "user", "content": "Hi"}],
                            temperature=data_json["temperature"],
                            max_tokens=data_json["max_tokens"],
                            top_p=data_json["top_p"],
                            presence_penalty=data_json["presence_penalty"],
                            frequency_penalty=data_json["frequency_penalty"],
                            timeout=30
                        )
                    else:
                        client = openai.OpenAI(base_url=openai.api_base, api_key=openai.api_key)
                        # Call the ChatGPT API to generate a reply message
                        resp = client.chat.completions.create(
                            model=data_json["model"],
                            messages=[{"role": "user", "content": "Hi"}],
                            temperature=data_json["temperature"],
                            max_tokens=data_json["max_tokens"],
                            top_p=data_json["top_p"],
                            presence_penalty=data_json["presence_penalty"],
                            frequency_penalty=data_json["frequency_penalty"],
                            timeout=30
                        )

                    logging.debug(resp)
                    logging.info("OpenAI API key Available")

                    return {"code": 200, "msg": "OpenAI API key 可用"}
                except openai.OpenAIError as e:
                    logging.error(f"OpenAI API key Unavailable: {e}")
                    return {"code": -1, "msg": f"OpenAI API key 不可用: {e}"}
                except Exception as e:
                    logging.error(traceback.format_exc())
                    logging.error(f"OpenAI API key Unavailable: {e}")
                    return {"code": -1, "msg": f"OpenAI API key 不可用: {e}"}
        
        return check_useful(data_json)


    """
    Image operations
    """
    # Get all window objects that have titles
    def list_visible_windows(self):
        """Get all window objects that have titles

        Returns:
            list: Get the list of all window names that have titles
        """
        if self.detect_os() == "Windows":
            import pygetwindow as gw

            windows = gw.getWindowsWithTitle('')
            
            window_titles = []

            # Print the title of each window
            for win in windows:
                if win.title:  # Make sure the window has a title
                    window_titles.append(win.title)
        else:
            return []

        return window_titles

    

    def capture_window_by_title(self, img_save_path: str, window_title: str):
        """Take a screenshot by window name (the window must not be covered and must be in the foreground)

        Args:
            img_save_path (str): Image save path
            window_title (str): Window title

        Returns:
            str: Image save path including file name
        """
        try:
            if self.detect_os() == "Windows":
                import pygetwindow as gw
                import pyautogui

                # Find the window by its title
                win = gw.getWindowsWithTitle(window_title)[0]  # Get the first matching window
                if win:
                    # Get the position and size of the window
                    left, top = win.left, win.top
                    width, height = win.width, win.height

                    # Use pyautogui to capture a screenshot of the specified region
                    screenshot = pyautogui.screenshot(region=(left, top, width, height))

                    # Check that the path exists, and create it if not
                    self.ensure_directory_exists(img_save_path)

                    # logging.debug(f"img_save_path={img_save_path}")
                    destination_directory = os.path.abspath(img_save_path)
                    logging.debug(f"destination_directory={destination_directory}")

                    # Get the image path including file name
                    destination_path = os.path.join(destination_directory, f"{window_title}.png")
                    logging.debug(f"destination_path={destination_path}")

                    screenshot.save(destination_path)

                    logging.info(f"Screenshot saved to: {destination_path}")

                    return destination_path
                else:
                    logging.error(f"Specified window not found: {window_title}")
            else:
                return None
        except IndexError:
            logging.error(f"Specified window not found: {window_title}")
        except Exception as e:
            logging.error(traceback.format_exc())

        return None
    

    """
    Camera related
    """

    def list_cameras(self, max_tested=5):
        """Get the indexes of all available cameras

        Args:
            max_tested (int, optional): Maximum number of cameras to probe. Defaults to 5.

        Returns:
            list: List of indexes of available cameras
        """
        try:
            available_cameras = []
            for i in range(max_tested):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # Try to open the camera
                if cap.isOpened():  # Check whether the camera opened successfully
                    available_cameras.append(i)
                    cap.release()  # Release the camera
                else:
                    break  # If one camera index cannot be opened, assume the following ones are unavailable too
            return available_cameras
        except Exception as e:
            logging.error(traceback.format_exc())

        return []


    def capture_image(self, img_save_path="./out/图像识别", camera_index=0):
        try:
            import tempfile

            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            
            # Check whether the camera opened successfully
            if not cap.isOpened():
                logging.info(f"Unable to open the camera, index={camera_index}")
                return None

            # Read one image frame
            ret, frame = cap.read()
            if not ret:
                logging.error("Unable to get the camera stream data")
                return None
            cap.release()  # Release the camera

            # Check that the path exists, and create it if not
            self.ensure_directory_exists(img_save_path)

            # logging.debug(f"img_save_path={img_save_path}")
            destination_directory = os.path.abspath(img_save_path)
            logging.debug(f"destination_directory={destination_directory}")

            # Construct the file name and save path
            destination_path = os.path.join(destination_directory, f"camera_{camera_index}_{cv2.getTickCount()}")
            logging.debug(f"destination_path={destination_path}")

            # Create a temporary file in the system temp directory
            temp_dir = tempfile.gettempdir()
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png', dir=temp_dir)
            temp_path = temp_file.name
            temp_file.close()  # Close the file to make sure it can be used by other processes
            
            # Save the image
            save_ret = cv2.imwrite(temp_path, frame)
            if save_ret:
                logging.info(f"Image saved to: {temp_path}")
            else:
                logging.error(f"Failed to save image: {temp_path}")
                return None
            
            # Move the file from the temporary path to the target path
            final_path = self.move_file(temp_path, destination_path, f"camera_{camera_index}_{cv2.getTickCount()}", "png")
            
            return final_path
        except Exception as e:
            logging.error(traceback.format_exc())

        return None
