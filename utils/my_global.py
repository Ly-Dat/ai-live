# Idle time counter
global_idle_time = 0
last_username_list = None
last_liveroom_data = None

# Number of audio clips waiting to play (when using an audio player or projects like metahuman-stream that do not play audio through AI Vtuber, this variable records whether any audio is still unplayed)
wait_play_audio_num = 0
wait_synthesis_msg_num = 0

# Idle-time task timer automatically reset to zero
def idle_time_auto_clear(config, type: str):
    """Idle-time task timer automatically reset to zero

    Args:
        type (str): Message type (comment/gift/entrance, etc.)

    Returns:
        bool: Result of whether to reset to zero
    """
    global global_idle_time

    # List of triggered types
    type_list = config.get("idle_time_task", "trigger_type")
    if type in type_list:
        global_idle_time = 0

        return True

    return False

# Add the username to the latest username list
def add_username_to_last_username_list(data):
    """
    data(str): Username
    """
    global last_username_list

    # Add data to the list of latest entering usernames
    last_username_list.append(data)

    # Keep the latest 3 data items
    last_username_list = last_username_list[-3:]