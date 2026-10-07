import pygetwindow as gw
import pyautogui

def capture_window_by_title(window_title):
    try:
        # Find the window by its title
        win = gw.getWindowsWithTitle(window_title)[0]  # Get the first matching window
        if win:
            # Get the position and size of the window
            left, top = win.left, win.top
            width, height = win.width, win.height

            # Use pyautogui to capture a screenshot of the specified region
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            screenshot.save(f'{window_title}.png')
            print(f"Screenshot saved as {window_title}.png")
        else:
            print("The specified window was not found")
    except IndexError:
        print("The specified window was not found")


# Get all window objects that have titles
def list_visible_windows():
    """Get all window objects that have titles

    Returns:
        list: Get the list of all window names that have titles
    """
    windows = gw.getWindowsWithTitle('')
    
    window_titles = []

    # Print the title of each window
    for win in windows:
        if win.title:  # Make sure the window has a title
            window_titles.append(win.title)

    return window_titles

# Call the function to list all visible window titles
list_visible_windows()
    
# Call the function, replace"Your Window Title Here"is the title of the window you want to capture
capture_window_by_title("伊卡酱 fans群等3个会话")
