import pyautogui
import time


# Simulate pressing then releasing a key
def simulate_key_press(key):
    pyautogui.keyDown(key)
    time.sleep(0.1)
    pyautogui.keyUp(key)


# Simulate pressing then releasing a key, taking a string array
def simulate_keys_press(keys, re=1):
    """Simulate pressing then releasing a key, taking a string array

    Args:
        keys (list): Key array
        re (int, optional): Number of keys. Defaults to 1.
    """
    num = 0
    # Simulate pressing and releasing a key
    for key in keys:
        # Limit the number of triggers
        if num >= re:
            break
        pyautogui.keyDown(key)
        time.sleep(0.1)
        pyautogui.keyUp(key)

        num = num + 1


# Simulate a mouse click
def simulate_mouse_press(x=0, y=0, button="left"):
    # Simulate a mouse click
    pyautogui.click(x=x, y=y, button=button)


# Parse the string and simulate key/mouse press
def parse_key_and_simulate_key_mouse_press(key):
    # Delete other unneeded strings in the array
    # def remove_needless(keys):
    #     for i in range(len(keys)):
    #         if keys[i] not in ['1', '2', 're']:
    #             keys.pop(i)
    #     return keys

    # keys = remove_needless(keys)

    if key not in ['1', '2', 're']:
        return

    if key == '1':
        key = 'w'
        simulate_key_press(key)
    elif key == '2':
        key = 'up'
        simulate_key_press(key)
    elif key == 're':
        # Set the coordinate values according to the actual situation
        x = 1076
        y = 771
        simulate_mouse_press(x, y, 'left')

        time.sleep(1)

        x = 1311
        y = 951
        simulate_mouse_press(x, y, 'left')


# Parse the string array; based on the first character of the string, decide whether the key needs converting, then press the key
def parse_keys_and_simulate_keys_press(keys, re=1):
    # print(f"keys={keys}")

    # Delete strings in the array other than w a s d 1 2 3
    def remove_needless(keys):
        for i in range(len(keys)):
            if keys[i] not in ['w', 'a', 's', 'd', '1']:
                keys.pop(i)
        return keys
    
    if isinstance(keys, list) and len(keys) > 0:
        if keys[0] == '1':
            keys = keys[1:]

            keys = remove_needless(keys)

            # Iterate over the array and change 123 toyui
            for i in range(len(keys)):
                if keys[i] == '1':
                    keys[i] = 'f'
                # elif keys[i] == '2':
                #     keys[i] = 'u'
                # elif keys[i] == '3':
                #     keys[i] = 'i'
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
                    keys[i] = 'l'
                # elif keys[i] == '2':
                #     keys[i] = '8'
                # elif keys[i] == '3':
                #     keys[i] = '9'
        elif keys[0] == 're':
            # Mouse press coordinates; please recalibrate them manually to fit your setup
            x = 1097
            y = 779

            simulate_mouse_press(x, y)

            time.sleep(1)

            x = 1314
            y = 957

            simulate_mouse_press(x, y)

            return

        simulate_keys_press(keys, re)


if __name__ == '__main__':
    # Test game: Drunken Tug of War https://www.4399.com/flash/221542_1.htm

    # Loop to get the current mouse coordinates
    def get_mouse_pos():
        # Interval (seconds) for periodically getting the mouse coordinates
        interval = 1

        try:
            while True:
                # Get the current mouse coordinates
                x, y = pyautogui.position()
                
                # Print the coordinate info
                print(f"Current mouse coordinates: x={x}, y={y}")
                
                # Wait for a while before getting the coordinates again
                time.sleep(interval)

        except KeyboardInterrupt:
            print("The program for getting mouse coordinates has finished.")
    
    get_mouse_pos()

    # game1 = Game1()
    # time.sleep(5)
    # game1.parse_key_and_simulate_key_mouse_press('re')