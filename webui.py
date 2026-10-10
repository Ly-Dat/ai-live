from nicegui import ui, app
import sys, os, json, subprocess, importlib, re, threading, signal
import traceback
import time
import asyncio
from urllib.parse import urljoin
from pathlib import Path

# from functools import partial

from utils.my_log import logger
from utils.config import Config
from utils.common import Common
from utils.audio import Audio

"""

@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@.:;;;++;;;;:,@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@:;+++++;;++++;;;.@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@:++++;;;;;;;;;;+++;,@@@@@@@@@@@@@@@@@
@@@@@@@@@@@.;+++;;;;;;;;;;;;;;++;:@@@@@@@@@@@@@@@@
@@@@@@@@@@;+++;;;;;;;;;;;;;;;;;;++;:@@@@@@@@@@@@@@
@@@@@@@@@:+++;;;;;;;;;;;;;;;;;;;;++;.@@@@@@@@@@@@@
@@@@@@@@;;+;;;;;;;;;;;;;;;;;;;;;;;++:@@@@@@@@@@@@@
@@@@@@@@;+;;;;:::;;;;;;;;;;;;;;;;:;+;,@@@@@@@@@@@@
@@@@@@@:+;;:;;:::;:;;:;;;;::;;:;:::;+;.@@@@@@@@@@@
@@@@@@.;+;::;:,:;:;;+:++:;:::+;:::::++:+@@@@@@@@@@
@@@@@@:+;;:;;:::;;;+%;*?;;:,:;*;;;;:;+;:@@@@@@@@@@
@@@@@@;;;+;;+;:;;;+??;*?++;,:;+++;;;:++:@@@@@@@@@@
@@@@@.++*+;;+;;;;+?;?**??+;:;;+.:+;;;;+;;@@@@@@@@@
@@@@@,+;;;;*++*;+?+;**;:?*;;;;*:,+;;;;+;,@@@@@@@@@
@@@@@,:,+;+?+?++?+;,?#%*??+;;;*;;:+;;;;+:@@@@@@@@@
@@@@@@@:+;*?+?#%;;,,?###@#+;;;*;;,+;;;;+:@@@@@@@@@
@@@@@@@;+;??+%#%;,,,;SSS#S*+++*;..:+;?;+;@@@@@@@@@
@@@@@@@:+**?*?SS,,,,,S#S#+***?*;..;?;**+;@@@@@@@@@
@@@@@@@:+*??*??S,,,,,*%SS+???%++;***;+;;;.@@@@@@@@
@@@@@@@:*?*;*+;%:,,,,;?S?+%%S?%+,:?;+:,,,@@@@@@@@
@@@@@@@,*?,;+;+S:,,,,%?+;S%S%++:+??+:,,,:@@@@@@@@
@@@@@@@,:,@;::;+,,,,,+?%*+S%#?*???*;,,,,,.@@@@@@@@
@@@@@@@@:;,::;;:,,,,,,,,,?SS#??*?+,.,,,:,@@@@@@@@@
@@@@@@;;+;;+:,:%?%*;,,,,SS#%*??%,.,,,,,:@@@@@@@@@
@@@@@.+++,++:;???%S?%;.+#####??;.,,,,,,:@@@@@@@@@
@@@@@:++::??+S#??%#??S%?#@#S*+?*,,,,,,:,@@@@@@@@@@
@@@@@:;;:*?;+%#%?S#??%SS%+#%..;+:,,,,,,@@@@@@@@@@@
@@@@@@,,*S*;?SS?%##%?S#?,.:#+,,+:,,,,,,@@@@@@@@@@@
@@@@@@@;%?%#%?*S##??##?,..*#,,+:,,;*;.@@@@@@@@@@@
@@@@@@.*%??#S*?S#@###%;:*,.:#:,+;:;*+:@@@@@@@@@@@@
@@@@@@,%S??SS%##@@#%S+..;;.,#*;???*?+++:@@@@@@@@@@
@@@@@@:S%??%####@@S,,*,.;*;+#*;+?%??#S%+.@@@@@@@@@
@@@@@@:%???%@###@@?,,:**S##S*;.,%S?;+*?+.,..@@@@@@
@@@@@@;%??%#@###@@#:.;@@#@%%,.,%S*;++*++++;.@@@@@
@@@@@@,%S?S@@###@@@%+#@@#@?;,.:?;??++?%?***+.@@@@@
@@@@@@.*S?S####@@####@@##@?..:*,+:??**%+;;;;..@@@@
@@@@@@:+%?%####@@####@@#@%;:.;;:,+;?**;++;,:;:,@@@
@@@@@@;;*%?%@##@@@###@#S#*:;*+,;.+***?******+:.@@@
@@@@@@:;:??%@###%##@#%++;+*:+;,:;+%?*;+++++;:.@@@@
@@@@@@.+;:?%@@#%;+S*;;,:::**+,;:%??*+.@....@@@@@@@
@@@@@@@;*::?#S#S+;,..,:,;:?+?++*%?+::@@@@@@@@@@@@@
@@@@@@@.+*+++?%S++...,;:***??+;++:.@@@@@@@@@@@@@@@
@@@@@@@@:::..,;+*+;;+*?**+;;;+;:.@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@,+*++;;:,..@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@::,.@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

"""


"""
Global variables
"""
user_info = None

# Global variable indicating whether the program is running
running_flag = False

# Flag variable used to track the timer’s running state
loop_screenshot_timer_running = False
loop_screenshot_timer = None

common = None
config = None
audio = None
my_handle = None
config_path = None

# Store running subprocesses
my_subprocesses = {}

# Locally started web service, used to load local live2d
web_server_port = 12345

# Chat log message counter
scroll_area_chat_box_chat_message_num = 0
# Keep at most 100 chat log messages
scroll_area_chat_box_chat_message_max_num = 100


"""
Initialize basic configuration
"""
def init():
    """
    Initialize basic configuration
    """
    global config_path, config, common, audio

    common = Common()

    if getattr(sys, 'frozen', False):
        # Currently a packaged executable
        bundle_dir = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
        file_relative_path = bundle_dir.resolve()
    else:
        # Currently running from source code
        file_relative_path = Path(__file__).parent.resolve()

    # logger.info(file_relative_path)

    # Initialize folders
    def init_dir():
        # Create log folder
        log_dir = file_relative_path / 'log'
        # The parents=True argument of mkdir ensures parent directories are created if necessary; exist_ok=True avoids raising an exception if the directory already exists.
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create audio output folder
        audio_out_dir = file_relative_path / 'out'
        audio_out_dir.mkdir(parents=True, exist_ok=True)

    init_dir()
    logger.debug("Project folders initialized")

    # Config file path
    config_path = file_relative_path / 'config.json'
    config_path = str(config_path)

    logger.debug("Config file path=" + str(config_path))

    # Instantiate the Audio class
    audio = Audio(config_path, type=2)
    # Instantiate the Config class
    config = Config(config_path)

# Initialize basic configuration
init()

# Expose static files from local directories (CSS, JavaScript, images, etc.) to the web server so users can access them via specific URLs.
if config.get("webui", "local_dir_to_endpoint", "enable"):
    for tmp in config.get("webui", "local_dir_to_endpoint", "config"):
        app.add_static_files(tmp['url_path'], tmp['local_dir'])

# Dark mode
dark = ui.dark_mode(True)

ui.colors(primary='#4f46e5', secondary='#64748b', accent='#06b6d4',
          positive='#16a34a', negative='#dc2626')

ui.add_css('''
:root {
  --page-bg: #f4f6fb;
  --card-bg: #ffffff;
  --card-border: #e6e9f2;
}
body.body--dark {
  --page-bg: #0f172a;
  --card-bg: #1e293b;
  --card-border: #334155;
}
body { background: var(--page-bg) !important; }

.q-tabs {
  position: sticky; top: 0; z-index: 100;
  background: var(--card-bg);
  border-bottom: 1px solid var(--card-border);
  box-shadow: 0 2px 8px rgba(15,23,42,.05);
}
.q-tab { text-transform: none; font-weight: 500; }
.q-tab--active { font-weight: 700; }

.q-field--standard .q-field__control { border-radius: 8px 8px 0 0; }
.q-field { margin: 4px 6px; }

.q-expansion-item {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 12px; margin: 10px 0; overflow: hidden;
}
.q-expansion-item__container > .q-item { font-weight: 600; }

.q-tab-panels { padding-bottom: 90px; }

.bottom-bar {
  position: fixed; left: 50%; bottom: 14px; transform: translateX(-50%);
  z-index: 200; gap: 10px; padding: 10px 16px;
  background: color-mix(in srgb, var(--card-bg) 85%, transparent);
  backdrop-filter: blur(10px);
  border: 1px solid var(--card-border); border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15,23,42,.15);
}
''')

# Studio theme (dark, sidebar navigation, status header); overrides the base CSS above
from utils.webui_theme import apply_theme, build_shell, port_open
apply_theme()

"""
Common functions
"""
def textarea_data_change(data):
    """
    Convert a string array into multi-line text
    """
    tmp_str = ""
    if data is not None:
        for tmp in data:
            tmp_str = tmp_str + tmp + "\n"
        
    return tmp_str



"""
                                                                                                    
                                               .@@@@@                           @@@@@.              
                                               .@@@@@                           @@@@@.              
        ]]]]]   .]]]]`   .]]]]`   ,]@@@@@\`    .@@@@@,/@@@\`   .]]]]]   ]]]]]`  ]]]]].              
        =@@@@^  =@@@@@`  =@@@@. =@@@@@@@@@@@\  .@@@@@@@@@@@@@  *@@@@@   @@@@@^  @@@@@.              
         =@@@@ ,@@@@@@@ .@@@@` =@@@@^   =@@@@^ .@@@@@`  =@@@@^ *@@@@@   @@@@@^  @@@@@.              
          @@@@^@@@@\@@@^=@@@^  @@@@@@@@@@@@@@@ .@@@@@   =@@@@@ *@@@@@   @@@@@^  @@@@@.              
          ,@@@@@@@^ \@@@@@@@   =@@@@^          .@@@@@.  =@@@@^ *@@@@@  .@@@@@^  @@@@@.              
           =@@@@@@  .@@@@@@.    \@@@@@]/@@@@@` .@@@@@@]/@@@@@. .@@@@@@@@@@@@@^  @@@@@.              
            \@@@@`   =@@@@^      ,\@@@@@@@@[   .@@@@^\@@@@@[    .\@@@@@[=@@@@^  @@@@@.    
            
"""
# Configuration
webui_ip = config.get("webui", "ip")
webui_port = config.get("webui", "port")
webui_title = config.get("webui", "title")

# CSS
theme_choose = config.get("webui", "theme", "choose")
tab_panel_css = config.get("webui", "theme", "list", theme_choose, "tab_panel")
tab_panel_css = ""  # the studio theme styles the panels; the old per-theme gradient is not used
card_css = "margin:10px 0px;"  # background comes from the studio theme (works in dark and light)
button_bottom_css = config.get("webui", "theme", "list", theme_choose, "button_bottom")
button_bottom_color = "primary"
button_internal_css = config.get("webui", "theme", "list", theme_choose, "button_internal")
button_internal_color = config.get("webui", "theme", "list", theme_choose, "button_internal_color")
switch_internal_css = config.get("webui", "theme", "list", theme_choose, "switch_internal")
echart_css = config.get("webui", "theme", "list", theme_choose, "echart")

def goto_func_page():
    """
    Go to the function page
    """
    global audio, my_subprocesses, config

    # Expiration time
    expiration_ts = None

    def start_programs():
        """Start all programs according to the config.
        main.py -> product_tour.py -> (tour reaches round 0) -> tiktok_bridge.py
        """
        global config

        for program in config.get("coordination_program"):
            if not program["enable"]:
                continue

            name = program["name"]
            executable = program["executable"]
            app_path = program["parameters"][0]
            app_dir = os.path.dirname(app_path)
            cmd = [executable, app_path]

            logger.info(f"Running program: {name} located at: {app_dir}")
            process = subprocess.Popen(cmd, cwd=app_dir, shell=True)
            my_subprocesses[name] = process

        base_dir = os.path.dirname(os.path.abspath(__file__))

        # 1) main.py (AI + API :8082), but only if one is not already running
        import socket
        with socket.socket() as _sk:
            _sk.settimeout(0.5)
            _main_up = _sk.connect_ex(("127.0.0.1", int(config.get("api_port") or 8082))) == 0
        if _main_up:
            logger.warning("main.py is already running (API port in use): not starting a second one")
        else:
            if common.detect_os() in ['Linux', 'MacOS']:
                my_subprocesses["main"] = subprocess.Popen(["python", "main.py"], shell=False)
            else:
                my_subprocesses["main"] = subprocess.Popen(["python", "main.py"], shell=True)
            logger.info("Running program: main")

        # 2) tour after main.py's API is up, 3) bridge after the tour reaches round 0 (product image on screen)
        def _tour_then_bridge():
            from utils import setup_wizard
            from utils.webui_setup import PM as _PM
            try:
                setup = setup_wizard.load_setup()        # min/max minutes per product etc. (Setup tab -> data/setup.json)
                user = setup_wizard.clean_username(config.get("room_display_id") or setup.get("tiktok_username") or "")
                utf8 = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}   # Vietnamese text in the logs

                api_port = int(config.get("api_port") or 8082)
                logger.info(f"[start] waiting for main.py API on :{api_port} ...")
                end = time.time() + 120
                while running_flag and time.time() < end:
                    with socket.socket() as sk:
                        sk.settimeout(0.5)
                        if sk.connect_ex(("127.0.0.1", api_port)) == 0:
                            break
                    time.sleep(1)
                if not running_flag:
                    return

                ready = True
                if setup.get("mode") != "creator" and setup.get("auto_tour", True):
                    tour_log = os.path.join(base_dir, "log", "tour.log")
                    offset = os.path.getsize(tour_log) if os.path.exists(tour_log) else 0
                    cmd = setup_wizard.tour_command(setup)            # includes --min-minutes / --max-minutes / --quiet
                    cmd.insert(1, "-u")
                    if _PM.start("tour", cmd, env=utf8):
                        logger.info(f"[start] product_tour.py started ({' '.join(cmd[2:])}), overlay: http://127.0.0.1:8091/overlay")
                        ready = False
                        end = time.time() + 180
                        while running_flag and time.time() < end and _PM.running("tour"):
                            try:
                                with open(tour_log, "rb") as f:
                                    f.seek(offset)
                                    if "[tour] round 0 " in f.read().decode("utf-8", "ignore"):
                                        ready = True
                                        break
                            except OSError:
                                pass
                            time.sleep(1)
                        if not ready:
                            logger.warning("[start] tour did not reach round 0 (see log/tour.log): starting the bridge anyway")
                if not running_flag:
                    return

                if not user:
                    logger.error("[start] Live room ID (room_display_id) is empty: bridge not started")
                    return
                if not _PM.running("bridge"):
                    py = setup_wizard.ensure_bridge_env(base_dir)   # venv_tt, created on first run (can take minutes)
                    if not running_flag:
                        return
                    _PM.start("bridge", setup_wizard.bridge_command(dict(setup, tiktok_username=user), py), env=utf8)
                    logger.info(f"[start] TikTok bridge started for @{user}")
            except Exception:
                logger.error(traceback.format_exc())

        threading.Thread(target=_tour_then_bridge, daemon=True).start()


    def stop_program(name):
        """Stop a running program and all of its child processes; compatible with Windows, Linux and macOS.

        Args:
            name (str): Name of the program to stop.
        """
        if name in my_subprocesses:
            pid = my_subprocesses[name].pid  # Get the process ID
            logger.info(f"Stopping the program and all of its child processes: {name} with PID {pid}")

            try:
                if os.name == 'nt':  # Windows
                    command = ["taskkill", "/F", "/T", "/PID", str(pid)]
                    subprocess.run(command, check=True)
                else:  # POSIX systems, such as Linux and macOS
                    os.killpg(os.getpgid(pid), signal.SIGKILL)

                logger.info(f"Program {name} and all of its child processes have been terminated.")
            except Exception as e:
                logger.error(f"Failed to terminate program {name}: {e}")

            del my_subprocesses[name]  # Remove from the process dict
        else:
            logger.warning(f"Program {name} is not running.")

    def stop_programs():
        """Stop all programs according to the config.
        """
        global config

        for program in config.get("coordination_program"):
            if not program["enable"]:
                continue

            stop_program(program["name"])

        from utils.webui_setup import PM as _PM
        _PM.stop_all()                 # product_tour + tiktok_bridge
        stop_program("main")

    def check_expiration():
        try:
            import requests

            API_URL = urljoin(config.get("login", "ums_api"), '/auth/check_expiration')

            if user_info is None:
                ui.notify(position="top", type="negative", message=f"Account login info is invalid, please log in again")
                stop_programs()
                return False

            if "accessToken" not in user_info:
                ui.notify(position="top", type="negative", message=f"Account login info is invalid, please log in again")
                stop_programs()
                return False

            headers = {
                "Authorization": "Bearer " + user_info["accessToken"]
            }

            # Send POST request
            response = requests.post(API_URL, headers=headers)

            # Check the status code
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json["code"] == 0 and resp_json["success"]:
                    remainder = common.time_difference_in_seconds(resp_json["data"]["expiration_ts"])
                    logger.info(f'Account is valid, expiration time:{resp_json["data"]["expiration_ts"]}')
                    return True
                else:
                    remainder = common.time_difference_in_seconds(resp_json["data"]["expiration_ts"])
                    ui.notify(position="top", type="negative", message=f'Account expiration time:{resp_json["data"]["expiration_ts"]}, expired:{remainder}seconds ago, please contact the administrator to renew')
                    logger.error(f'Account expiration time:{resp_json["data"]["expiration_ts"]}, expired:{remainder}seconds ago, please contact the administrator to renew')
                    stop_programs()
                    return False
            # elif response.status_code == 401:
            #     ui.notify(position="top", type="negative", message=f"Account has expired, please contact the administrator to renew")
            #     logger.error(f"Account has expired, please contact the administrator to renew")
            #     stop_programs()

            #     return False
            else:
                logger.error(f"Self-check error!")
                return False
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error:{e}")
            logger.error(traceback.format_exc())

            return False

    if config.get("login", "enable"):
        # Check once every ten minutes
        ui.timer(600.0, lambda: check_expiration())


    """

      =@@^      ,@@@^        .@@@. .....   =@@.      ]@\  ,]]]]]]]]]]]]]]].  .]]]]]]]]]]]]]]]]]]]]    ,]]]]]]]]]]]]]]]]]`    ,/. @@@^ /]  ,@@@.               
      =@@^ .@@@@@@@@@@@@@@^  /@@\]]@@@@@=@@@@@@@@@.  \@@@`=@@@@@@@@@@@@@@@.  .@@@@@@@@@@@@@@@@@@@@    =@@@@@@@@@@@@@@@@@^   .\@@^@@@\@@@`.@@@^                
    @@@@@@@^@@@@@@@@@@@@@@^ =@@@@@^ =@@\]]]/@@]]@@].  =@/`=@@^  .@@@  .@@@.  .@@@^    @@@^    =@@@             ,/@@@@/`     =@@@@@@@@@@@^=@@@@@@@@@.          
    @@@@@@@^@@@^@@\`   =@@^.@@@]]]`=@@^=@@@@@@@@@@@.]]]]` =@@^=@@@@@@@^@@@.  .@@@\]]]]@@@\]]]]/@@@   @@@\/@\..@@@@[./@/@@@. ,[[\@@@@/[[[\@@@`..@@@`           
      =@@^ ,]]]/@@@]]]]]]]].\@@@@@^@@@OO=@@@@@@@@@..@@@@^ =@@^]]]@@@]]`@@@.  .@@@@@@@@@@@@@@@@@@@@   @@@^=@@@^@@@^/@@@\@@@..]@@@@@@@@@@]@@@@^ .@@@.           
      =@@@@=@@@@@@@@@@@@@@@. =@@^ .OO@@@.[[\@@[[[[.  =@@^ =@@^@@@@@@@@^@@@.  .@@@^    @@@^    =@@@   @@@^ .`,]@@@^`,` =@@@. \@/.]@@@^,@@@@@@\ =@@^            
   .@@@@@@@. .@@@`   /@@/  .@@@@@@@,.=@@=@@@@@@@@@^  =@@^,=@@^=@@@@@@@.@@@.  .@@@\]]]]@@@\]]]]/@@@   @@@^]@@@@@@@@@@@]=@@@. ]]]@@@\]]]]] .=@@\@@@.            
    @@\@@^  .@@@\.  /@@@.    =@@^ =@\@@^.../@@.....  =@@@@=@@^=@@[[\@@.@@@.  .@@@@@@@@@@@@@@@@@@@@   @@@@@@/..@@@^,@@@@@@@. O@@@@@@@@@@@  .@@@@@^             
      =@@^   ,\@@@@@@@@.     =@@^/^\@@@`@@@@@@@@@@^  /@@@/@@@`=@@OO@@@.@@@.  =@@@`    @@@^    =@@@   @@@^  \@@@@@^   .=@@@. .@@@@\`/@@/    /@@@\.             
      =@@^    ,/@@@@@@@@]    =@@@@^/@@@@]` =@@.     .\@/.=@@@ =@@[[[[[.@@@.  /@@@     @@@^   ./@@@   @@@^.............=@@@.    O@@@@@@\`,/@@@@@@@@`           
    @@@@@^.@@@@@@@/..[@@@@/. ,@@`/@@@`[@@@@@@@@@@@@.    /@@@^      =@@@@@@. /@@@^     @@@^,@@@@@@^   @@@@@@@@@@@@@@@@@@@@@..\@@@@@[,\@@\@@@@` ,@@@^           
    ,[[[.  .O[[.        [`        ,/         ......       ,^       .[[[[`     ,`      .... [[[[`                      ,[[[. .[.         ,/.     .`

    """
    # Create a function to run external programs
    def run_external_program(config_path="config.json", type="webui"):
        global running_flag

        if running_flag:
            if type == "webui":
                ui.notify(position="top", type="warning", message="Already running, please do not run it again")
            return

        try:
            running_flag = True

            # Start the coordinated programs and the main program
            start_programs()

            if type == "webui":
                ui.notify(position="top", type="positive", message="Program started running")
            logger.info("Program started running")

            return {"code": 200, "msg": "Program started running"}
        except Exception as e:
            if type == "webui":
                ui.notify(position="top", type="negative", message=f"Error:{e}")
            logger.error(traceback.format_exc())
            running_flag = False

            return {"code": -1, "msg": f"Run failed!{e}"}


    # Define a function to stop the running program
    def stop_external_program(type="webui"):
        global running_flag

        if running_flag:
            try:
                # Stop the coordinated programs
                stop_programs()

                running_flag = False
                if type == "webui":
                    ui.notify(position="top", type="positive", message="Program stopped")
                logger.info("Program stopped")
            except Exception as e:
                if type == "webui":
                    ui.notify(position="top", type="negative", message=f"Stop error:{e}")
                logger.error(f"Stop error:{e}")

                return {"code": -1, "msg": f"Restart failed!{e}"}


    # let the Setup tab's Start / Stop buttons run exactly the same code as 'Start Run' / 'Stop Run'
    from utils import webui_setup as _ws
    _ws.RUN_HOOKS.update(start=lambda: run_external_program(), stop=lambda: stop_external_program(),
                         running=lambda: bool(running_flag))

    # Toggle light
    def change_light_status(type="webui"):
        if dark.value:
            button_light.set_text("Lights Off")
        else:
            button_light.set_text("Lights On")
        dark.toggle()

    # Restart
    def restart_application(type="webui"):
        try:
            # Stop running first
            stop_external_program(type)

            logger.info(f"Restart webui")
            if type == "webui":
                ui.notify(position="top", type="ongoing", message=f"Restarting...")
            python = sys.executable
            os.execl(python, python, *sys.argv)  # Start a new instance of the application
        except Exception as e:
            logger.error(traceback.format_exc())
            return {"code": -1, "msg": f"Restart failed!{e}"}
        
    # Restore factory settings
    def factory(src_path='config.json.bak', dst_path='config.json', type="webui"):
        # src_path = 'config.json.bak'
        # dst_path = 'config.json'

        try:
            with open(src_path, 'r', encoding="utf-8") as source:
                with open(dst_path, 'w', encoding="utf-8") as destination:
                    destination.write(source.read())
            logger.info("Factory settings restored successfully!")
            if type == "webui":
                ui.notify(position="top", type="positive", message=f"Factory settings restored successfully!")
            
            # Restart
            restart_application()

            return {"code": 200, "msg": "Factory settings restored successfully!"}
        except Exception as e:
            logger.error(f"Failed to restore factory settings!\n{e}")
            if type == "webui":
                ui.notify(position="top", type="negative", message=f"Failed to restore factory settings!\n{e}")
            
            return {"code": -1, "msg": f"Failed to restore factory settings!\n{e}"}
    
    
        
    # OpenAI: test key availability
    def test_openai_key():
        data_json = {
            "base_url": input_openai_api.value, 
            "api_keys": textarea_openai_api_key.value, 
            "model": select_chatgpt_model.value,
            "temperature": round(float(input_chatgpt_temperature.value), 1),
            "max_tokens": int(input_chatgpt_max_tokens.value),
            "top_p": round(float(input_chatgpt_top_p.value), 1),
            "presence_penalty": round(float(input_chatgpt_presence_penalty.value), 1),
            "frequency_penalty": round(float(input_chatgpt_frequency_penalty.value), 1),
            "preset": input_chatgpt_preset.value
        }

        resp_json = common.test_openai_key(data_json, 2)
        if resp_json["code"] == 200:
            ui.notify(position="top", type="positive", message=resp_json["msg"])
        else:
            ui.notify(position="top", type="negative", message=resp_json["msg"])

    # GPT-SoVITS: load model
    async def gpt_sovits_set_model():
        try:
            if select_gpt_sovits_type.value == "v2_api_0821":
                async def set_gpt_weights():
                    try:

                        API_URL = urljoin(input_gpt_sovits_api_ip_port.value, '/set_gpt_weights?weights_path=' + input_gpt_sovits_gpt_model_path.value)
                        
                        # logger.debug(API_URL)

                        resp_json = await common.send_async_request(API_URL, "GET", None, resp_data_type="json")

                        if resp_json is None:
                            content = f"gpt_weights：{input_gpt_sovits_gpt_model_path.value} failed to load, please check both sides’ logs to troubleshoot"
                            logger.error(content)
                            return False
                        else:
                            if resp_json["message"] == "success":
                                content = f"gpt_weights：{input_gpt_sovits_gpt_model_path.value} loaded successfully"
                                logger.info(content)
                            else:
                                content = f"gpt_weights：{input_gpt_sovits_gpt_model_path.value} failed to load, please check both sides’ logs to troubleshoot"
                                logger.error(content)
                                return False
                        
                        return True
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        logger.error(f'gpt_sovits unknown error: {e}')
                        return False

                async def set_sovits_weights():
                    try:

                        API_URL = urljoin(input_gpt_sovits_api_ip_port.value, '/set_sovits_weights?weights_path=' + input_gpt_sovits_sovits_model_path.value)
                        
                        resp_json = await common.send_async_request(API_URL, "GET", None, resp_data_type="json")

                        if resp_json is None:
                            content = f"sovits_weights：{input_gpt_sovits_sovits_model_path.value} failed to load, please check both sides’ logs to troubleshoot"
                            logger.error(content)
                            return False
                        else:
                            if resp_json["message"] == "success":
                                content = f"sovits_weights：{input_gpt_sovits_sovits_model_path.value} loaded successfully"
                                logger.info(content)
                            else:
                                content = f"sovits_weights：{input_gpt_sovits_sovits_model_path.value} failed to load, please check both sides’ logs to troubleshoot"
                                logger.error(content)
                                return False
                        
                        return True
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        logger.error(f'sovits_weights unknown error: {e}')
                        return False
            
                if await set_gpt_weights() and await set_sovits_weights():
                    content = "gpt_sovits model loaded successfully"
                    logger.info(content)
                    ui.notify(position="top", type="positive", message=content)
                else:
                    content = "gpt_sovits model failed to load, please check both sides’ logs to troubleshoot"
                    logger.error(content)
                    ui.notify(position="top", type="negative", message=content)
            else:
                API_URL = urljoin(input_gpt_sovits_api_ip_port.value, '/set_model')

                data_json = {
                    "gpt_model_path": input_gpt_sovits_gpt_model_path.value,
                    "sovits_model_path": input_gpt_sovits_sovits_model_path.value
                }
                
                resp_data = await common.send_async_request(API_URL, "POST", data_json, resp_data_type="content")

                if resp_data is None:
                    content = "gpt_sovits failed to load model, please check both sides’ logs to troubleshoot"
                    logger.error(content)
                    ui.notify(position="top", type="negative", message=content)
                else:
                    content = "gpt_sovits loaded model successfully"
                    logger.info(content)
                    ui.notify(position="top", type="positive", message=content)
        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f'gpt_sovits unknown error: {e}')
            ui.notify(position="top", type="negative", message=f'gpt_sovits unknown error: {e}')

    # Scroll the page to the top
    def scroll_to_top():
        # This JavaScript code scrolls the page to the top
        ui.run_javascript("window.scrollTo(0, 0);")   

    # Scroll area for displaying chat data
    scroll_area_chat_box = None

    # Handle data and show chat log
    def data_handle_show_chat_log(data_json):
        global scroll_area_chat_box_chat_message_num

        if data_json["type"] == "llm":
            if data_json["data"]["content_type"] == "question":
                name = data_json["data"]['username']
                if 'user_face' in data_json["data"]:
                    # Requesting the Bilibili avatar directly returns 403, so use the default avatar for now
                    # avatar = data_json["data"]['user_face']
                    avatar = 'https://robohash.org/ui'
                else:
                    avatar = 'https://robohash.org/ui'
            else:
                name = data_json["data"]['type']
                avatar = "http://127.0.0.1:8081/favicon.ico"

            with scroll_area_chat_box:
                ui.chat_message(data_json["data"]["content"],
                    name=name,
                    stamp=data_json["data"]["timestamp"],
                    avatar=avatar
                )

                scroll_area_chat_box_chat_message_num += 1

            if scroll_area_chat_box_chat_message_num > scroll_area_chat_box_chat_message_max_num:
                scroll_area_chat_box.remove(0)

            scroll_area_chat_box.scroll_to(percent=1, duration=0.2)

    """

                  /@@@@@@@@          @@@@@@@@@@@@@@@].      =@@@@@@@       
                 =@@@@@@@@@^         @@@@@@@@@@@@@@@@@@`    =@@@@@@@       
                ,@@@@@@@@@@@`        @@@@@@@@@@@@@@@@@@@^   =@@@@@@@       
               .@@@@@@\@@@@@@.       @@@@@@@^   .\@@@@@@\   =@@@@@@@       
               /@@@@@/ \@@@@@\       @@@@@@@^    =@@@@@@@   =@@@@@@@       
              =@@@@@@. .@@@@@@^      @@@@@@@\]]]@@@@@@@@^   =@@@@@@@       
             ,@@@@@@^   =@@@@@@`     @@@@@@@@@@@@@@@@@@/    =@@@@@@@       
            .@@@@@@@@@@@@@@@@@@@.    @@@@@@@@@@@@@@@@/`     =@@@@@@@       
            /@@@@@@@@@@@@@@@@@@@\    @@@@@@@^               =@@@@@@@       
           =@@@@@@@@@@@@@@@@@@@@@^   @@@@@@@^               =@@@@@@@       
          ,@@@@@@@.       ,@@@@@@@`  @@@@@@@^               =@@@@@@@       
          @@@@@@@^         =@@@@@@@. @@@@@@@^               =@@@@@@@   

    """
    
    

    from starlette.requests import Request
    from utils.models import SendMessage, CommonResult, SysCmdMessage, SetConfigMessage

    """
    Configure config

        config_path (str): Config file path
        data (dict): Incoming json

    return:
        {"code": 200, "message": "Success"}
    """
    @app.post('/set_config')
    async def set_config(msg: SetConfigMessage):
        global config

        try:
            data_json = msg.dict()
            logger.info(f'set_config endpoint received data:{data_json}')

            config_data = None

            try:
                with open(data_json["config_path"], 'r', encoding="utf-8") as config_file:
                    config_data = json.load(config_file)
            except Exception as e:
                logger.error(f"Unable to read the config file!\n{e}")
                return CommonResult(code=-1, message=f"Unable to read the config file!{e}")
            
            # Merge dictionaries
            config_data.update(data_json["data"])

            # Write the config to the config file
            try:
                with open(data_json["config_path"], 'w', encoding="utf-8") as config_file:
                    json.dump(config_data, config_file, indent=2, ensure_ascii=False)
                    config_file.flush()  # Flush the buffer to make sure the write takes effect immediately

                logger.info("Config data was written to the file successfully!")

                return CommonResult(code=200, message="Config data was written to the file successfully!")
            except Exception as e:
                logger.error(f"Unable to write the config file!\n{str(e)}")
                return CommonResult(code=-1, message=f"Unable to write the config file!{e}")
        except Exception as e:
            logger.error(traceback.format_exc())
            return CommonResult(code=-1, message=f"{data_json['type']}Execution failed!{e}")

    """
    System command
        type Command type (run/stop/restart/factory)
        data Incoming json

    data_json = {
        "type": "Command name",
        "data": {
            "key": "value"
        }
    }

    return:
        {"code": 200, "message": "Success"}
        {"code": -1, "message": "Failure"}
    """
    @app.post('/sys_cmd')
    async def sys_cmd(msg: SysCmdMessage):
        try:
            data_json = msg.dict()
            logger.info(f'sys_cmd endpoint received data:{data_json}')
            logger.info(f"Start executing {data_json['type']}command...")

            resp_json = {}

            if data_json['type'] == 'run':
                """
                {
                    "type": "run",
                    "data": {
                        "config_path": "config.json"
                    }
                }
                """
                # Run
                resp_json = run_external_program(data_json['data']['config_path'], type="api")
            elif data_json['type'] =='stop':
                """
                {
                    "type": "stop",
                    "data": {
                        "config_path": "config.json"
                    }
                }
                """
                # Stop
                resp_json = stop_external_program(type="api")
            elif data_json['type'] =='restart':
                """
                {
                    "type": "restart",
                    "api_type": "webui",
                    "data": {
                        "config_path": "config.json"
                    }
                }
                """
                # Restart
                resp_json = restart_application(type=data_json['api_type'])
            elif data_json['type'] =='factory':
                """
                {
                    "type": "factory",
                    "api_type": "webui",
                    "data": {
                        "src_path": "config.json.bak",
                        "dst_path": "config.json"
                    }
                }
                """
                # Factory reset
                resp_json = factory(data_json['data']['src_path'], data_json['data']['dst_path'], type="api")

            return resp_json
        except Exception as e:
            logger.error(traceback.format_exc())
            return CommonResult(code=-1, message=f"{data_json['type']}Execution failed!{e}")

    """
    Send data
        type Data type (comment/gift/entrance/reread/tuning/...)
        key  Adapt according to the data type

    data_json = {
        "type": "Data type",
        "key": "value"
    }

    return:
        {"code": 200, "message": "Success"}
        {"code": -1, "message": "Failure"}
    """
    @app.post('/send')
    async def send(msg: SendMessage):
        global config

        try:
            data_json = msg.dict()
            logger.info(f'WEBUI API send endpoint received data:{data_json}')

            main_api_ip = "127.0.0.1" if config.get("api_ip") == "0.0.0.0" else config.get("api_ip")
            resp_json = await common.send_async_request(f'http://{main_api_ip}:{config.get("api_port")}/send', "POST", data_json)

            return resp_json
        except Exception as e:
            logger.error(traceback.format_exc())
            return CommonResult(code=-1, message=f"Failed to send data!{e}")



    """
    Data callback
        data Incoming json

    data_json = {
        "type": "Data type (llm)",
        "data": {
            "type": "LLM type",
            "username": "Username",
            "content_type": "Content type (question/answer)",
            "content": "Reply content",
            "timestamp": "Timestamp"
        }
    }

    return:
        {"code": 200, "message": "Success"}
        {"code": -1, "message": "Failure"}
    """
    @app.post('/callback')
    async def callback(request: Request):
        try:
            data_json = await request.json()
            logger.info(f'WEBUI API callback endpoint received data:{data_json}')

            data_handle_show_chat_log(data_json)

            return {"code": 200, "message": "Success"}
        except Exception as e:
            logger.error(traceback.format_exc())
            return CommonResult(code=-1, message=f"Failed!{e}")


    """
    TTS synthesis; get the path of the synthesized audio file
        data Incoming json

    For example:
    data_json = {
        "type": "reread",
        "tts_type": "gpt_sovits",
        "data": {
            "type": "api",
            "api_ip_port": "http://127.0.0.1:9880",
            "ref_audio_path": "F:\\GPT-SoVITS\\raws\\ikaros\\21.wav",
            "prompt_text": "Master, are you working hard? No, it is nothing",
            "prompt_language": "Japanese",
            "language": "Auto detect",
            "cut": "Split when reaching four sentences",
            "gpt_model_path": "F:\\GPT-SoVITS\\GPT_weights\\ikaros-e15.ckpt",
            "sovits_model_path": "F:\\GPT-SoVITS\\SoVITS_weights\\ikaros_e8_s280.pth",
            "webtts": {
                "api_ip_port": "http://127.0.0.1:8080",
                "spk": "sanyueqi",
                "lang": "zh",
                "speed": "1.0",
                "emotion": "Normal"
            }
        },
        "username": "Master",
        "content": "Hello, this is the text content to be synthesized"
    }

    return:
        {
            "code": 200,
            "message": "Success",
            "data": {
                "type": "reread",
                "tts_type": "gpt_sovits",
                "data": {
                    "type": "api",
                    "api_ip_port": "http://127.0.0.1:9880",
                    "ref_audio_path": "F:\\\\GPT-SoVITS\\\\raws\\\\ikaros\\\\21.wav",
                    "prompt_text": "Master, are you working hard? No, it is nothing",
                    "prompt_language": "Japanese",
                    "language": "Auto detect",
                    "cut": "Split when reaching four sentences",
                    "gpt_model_path": "F:\\GPT-SoVITS\\GPT_weights\\ikaros-e15.ckpt",
                    "sovits_model_path": "F:\\GPT-SoVITS\\SoVITS_weights\\ikaros_e8_s280.pth",
                    "webtts": {
                        "api_ip_port": "http://127.0.0.1:8080",
                        "spk": "sanyueqi",
                        "lang": "zh",
                        "speed": "1.0",
                        "emotion": "Normal"
                    }
                },
                "username": "Master",
                "content": "Hello, this is the text content to be synthesized",
                "result": {
                    "code": 200,
                    "msg": "Synthesis succeeded",
                    "audio_path": "E:\\GitHub_pro\\AI-Vtuber\\out\\gpt_sovits_4.wav"
                }
            }
        }

        {"code": -1, "message": "Failure"}
    """
    @app.post('/tts')
    async def tts(request: Request):
        try:
            data_json = await request.json()
            logger.info(f'WEBUI API tts endpoint received data:{data_json}')

            resp_json = await audio.tts_handle(data_json)

            return {"code": 200, "message": "Success", "data": resp_json}
        except Exception as e:
            logger.error(traceback.format_exc())
            return CommonResult(code=-1, message=f"Failed!{e}")


    """
    LLM inference; get the inference result
        data Incoming json

    For example:type is the actual value corresponding to the chat type
    data_json = {
        "type": "chatgpt",
        "username": "Username",
        "content": "Hello"
    }

    return:
        {
            "code": 200,
            "message": "Success",
            "data": {
                "content": "Hello, this is the content replied by the LLM"
            }
        }

        {"code": -1, "message": "Failure"}
    """
    @app.post('/llm')
    async def llm(request: Request):
        try:
            data_json = await request.json()
            logger.info(f'WEBUI API llm endpoint received data:{data_json}')

            main_api_ip = "127.0.0.1" if config.get("api_ip") == "0.0.0.0" else config.get("api_ip")
            resp_json = await common.send_async_request(f'http://{main_api_ip}:{config.get("api_port")}/llm', "POST", data_json, "json", timeout=60)
            if resp_json:
                return resp_json
            
            return CommonResult(code=-1, message="Failed!")
        except Exception as e:
            logger.error(traceback.format_exc())
            return CommonResult(code=-1, message=f"Failed!{e}")

    # Get system info endpoint
    @app.get("/overlay/state")
    def overlay_state_route():
        """JSON for the on-screen overlay (see utils/overlay_page.py)."""
        from fastapi.responses import JSONResponse
        from utils import engage as _engage, flash_sale as _flash, overlay_state as _ov, tiktok_safety as _ts
        try:
            flash = _flash.load_state(config.get("products", "flash_sale_path") or _flash.DEFAULT_PATH)
            name = ""
            if flash and flash.get("active"):
                pdata = json.load(open(config.get("products", "path") or "data/products.json", encoding="utf-8"))
                name = next((p["name"] for p in pdata.get("products", []) if p.get("id") == flash.get("product_id")), "")
            safety = _ts.TikTokSafety(config.get("filter", "tiktok_safety", "terms_path") or "data/tiktok_policy_terms.json")
            out = _ov.build(_engage.load_state(), flash, name, time.time(), safe=lambda s: not safety.check(s, "output"))
        except Exception:
            out = {"items": []}
        try:
            from utils import music as _music, live_analytics as _la
            out["music"] = _music.overlay_music(_music.load_settings(), _music.tracks(),
                                                _music.tail_events(_la.latest_session_file()), time.time())
        except Exception:
            out["music"] = {"enabled": False, "tracks": [], "volume": 0}
        try:
            from utils import novel as _novel
            out["novel"] = _novel.overlay_novel(_novel.read_status(), _novel.read_control()["settings"], time.time())
        except Exception:
            out["novel"] = None
        try:
            from utils import story as _story
            out["story"] = _story.overlay_story(_story.read_status(), _story.read_control()["settings"], time.time())
        except Exception:
            out["story"] = None
        try:
            from utils import avatar as _av, host_control as _hc, music as _m2, live_analytics as _la2, webui_avatar as _wa
            _wa._mount()
            out["avatar"] = _av.overlay_avatar(_av.load_settings(), _av.pack_files(), _m2.tail_events(_la2.latest_session_file()),
                                               time.time(), _hc.load()["state"])
        except Exception:
            out["avatar"] = None
        return JSONResponse(out, headers={"Cache-Control": "no-store"})


    @app.get("/overlay")
    def overlay_page_route():
        from fastapi.responses import HTMLResponse
        from utils.overlay_page import OVERLAY_HTML
        return HTMLResponse(OVERLAY_HTML)


    @app.get("/get_sys_info")
    async def get_sys_info():
        try:
            # logger.info(f'WEBUI API get_sys_infoInterface received a request')

            main_api_ip = "127.0.0.1" if config.get("api_ip") == "0.0.0.0" else config.get("api_ip")
            resp_json = await common.send_async_request(f'http://{main_api_ip}:{config.get("api_port")}/get_sys_info', "GET", None, "json", timeout=60)
            if resp_json:
                return resp_json
            return CommonResult(code=-1, message="Failed!")
        except Exception as e:
            logger.error(f"get_sys_info handling failed!{e}")
            return CommonResult(code=-1, message=f"get_sys_info handling failed!{e}")


    
        
    """
                                                     ./@\]                    
                   ,@@@@\*                             \@@^ ,]]]              
                      [[[*                      /@@]@@@@@/[[\@@@@/            
                        ]]@@@@@@\              /@@^  @@@^]]`[[                
                ]]@@@@@@@[[*                   ,[`  /@@\@@@@@@@@@@@@@@^       
             [[[[[`   @@@/                 \@@@@[[[\@@^ =@@/                  
              .\@@\* *@@@`                           [\@@@@@@\`               
                 ,@@\=@@@                         ,]@@@/`  ,\@@@@*            
                   ,@@@@`                     ,[[[[`  =@@@   ]]/O             
                   /@@@@@`                    ]]]@@@@@@@@@/[[[[[`             
                ,@@@@[ \@@@\`                      ./@@@@@@@]                 
          ,]/@@@@/`      \@@@@@\]]               ,@@@/,@@^ \@@@\]             
                           ,@@@@@@@@/[*       ,/@@/*  /@@^   [@@@@@@@\*       
                                                      ,@@^                    
                                                              
    """

    # Copywriting page - add
    def copywriting_add():
        data_len = len(copywriting_config_var)
        tmp_config = {
            "file_path": f"data/copywriting{int(data_len / 5) + 1}/",
            "audio_path": f"out/copywriting{int(data_len / 5) + 1}/",
            "continuous_play_num": 2,
            "max_play_time": 10.0,
            "play_list": []
        }

        with copywriting_config_card.style(card_css):
            with ui.row():
                copywriting_config_var[str(data_len)] = ui.input(label=f"Copywriting storage path#{int(data_len / 5) + 1}", value=tmp_config["file_path"], placeholder='Path where copywriting files are stored. Changing it is not recommended.').style("width:200px;")
                copywriting_config_var[str(data_len + 1)] = ui.input(label=f"Audio storage path#{int(data_len / 5) + 1}", value=tmp_config["audio_path"], placeholder='Path where copywriting audio files are stored. Changing it is not recommended.').style("width:200px;")
                copywriting_config_var[str(data_len + 2)] = ui.input(label=f"Continuous play count#{int(data_len / 5) + 1}", value=tmp_config["continuous_play_num"], placeholder='Number of audio files played consecutively from the play list; once exceeded, it switches to the next copywriting list').style("width:200px;")
                copywriting_config_var[str(data_len + 3)] = ui.input(label=f"Continuous play time#{int(data_len / 5) + 1}", value=tmp_config["max_play_time"], placeholder='Duration of audio played consecutively from the play list; once exceeded, it switches to the next copywriting list').style("width:200px;")
                copywriting_config_var[str(data_len + 4)] = ui.textarea(label=f"Play list#{int(data_len / 5) + 1}", value=textarea_data_change(tmp_config["play_list"]), placeholder='Enter the full names of the audio files to play here, then click Save Config. Copy the full file names from the audio list, separated by line breaks; do not fill in arbitrarily').style("width:500px;")

    # Copywriting page - delete
    def copywriting_del(index):
        try:
            copywriting_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(5 * (int(index) - 1) + i) for i in range(5)]
            for key in keys_to_delete:
                if key in copywriting_config_var:
                    del copywriting_config_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(copywriting_config_var.keys(), key=int):
                new_key = str(int(key) - 5 if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = copywriting_config_var[key]

            # Apply the update
            copywriting_config_var.clear()
            copywriting_config_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())

    # Copywriting page - load text
    def copywriting_text_load():
        copywriting_text_path = input_copywriting_text_path.value
        if "" == copywriting_text_path:
            logger.warning(f"Please enter the copywriting text path~")
            ui.notify(position="top", type="warning", message="Please enter the copywriting text path~")
            return
        
        # Pass the full file path, absolute or relative
        logger.info(f"Preparing to load file:[{copywriting_text_path}]")
        new_file_path = os.path.join(copywriting_text_path)

        content = common.read_file_return_content(new_file_path)
        if content is None:
            logger.error(f"Read failed! Please check the config, file path and file name")
            ui.notify(position="top", type="negative", message="Read failed! Please check the config, file path and file name")
            return
        
        # Write the data into the text input box
        textarea_copywriting_text.value = content

        logger.info(f"Successfully loaded copywriting:{copywriting_text_path}")
        ui.notify(position="top", type="positive", message=f"Successfully loaded copywriting:{copywriting_text_path}")


    # Copywriting page - save copywriting
    def copywriting_save_text():
        content = textarea_copywriting_text.value
        copywriting_text_path = input_copywriting_text_path.value
        if "" == copywriting_text_path:
            logger.warning(f"Please enter the copywriting text path~")
            ui.notify(position="top", type="warning", message="Please enter the copywriting text path~")
            return
        
        new_file_path = os.path.join(copywriting_text_path)
        if common.write_content_to_file(new_file_path, content):
            ui.notify(position="top", type="positive", message=f"Saved successfully~")
        else:
            ui.notify(position="top", type="negative", message=f"Save failed! Please check the log to troubleshoot")


    # Copywriting page - synthesize audio
    async def copywriting_audio_synthesis():
        ui.notify(position="top", type="warning", message="Copywriting audio is being synthesized and will block other tasks. Please do not do anything else, check the log and wait patiently")
        logger.warning("Copywriting audio is being synthesized and will block other tasks. Please do not do anything else, check the log and wait patiently")
        
        copywriting_text_path = input_copywriting_text_path.value
        copywriting_audio_save_path = input_copywriting_audio_save_path.value
        audio_synthesis_type = select_copywriting_audio_synthesis_type.value

        file_path = await audio.copywriting_synthesis_audio(copywriting_text_path, copywriting_audio_save_path, audio_synthesis_type)

        if file_path:
            ui.notify(position="top", type="positive", message=f"Copywriting audio synthesized successfully, stored at:{file_path}")
        else:
            ui.notify(position="top", type="negative", message=f"Copywriting audio synthesis failed! Please check the log to troubleshoot")
            return

        def clear_copywriting_audio_card(file_path):
            copywriting_audio_card.clear()
            if common.del_file(file_path):
                ui.notify(position="top", type="positive", message=f"File deleted successfully:{file_path}")
            else:
                ui.notify(position="top", type="negative", message=f"Failed to delete file:{file_path}")
        
        # Clear the card
        copywriting_audio_card.clear()
        tmp_label = ui.label(f"Copywriting audio synthesized successfully, stored at:{file_path}")
        tmp_label.move(copywriting_audio_card)
        audio_copywriting = ui.audio(src=file_path)
        audio_copywriting.move(copywriting_audio_card)
        button_copywriting_audio_del = ui.button('Delete audio', on_click=lambda: clear_copywriting_audio_card(file_path), color=button_internal_color).style(button_internal_css)
        button_copywriting_audio_del.move(copywriting_audio_card)
        

    # Copywriting page - loop play
    def copywriting_loop_play():
        if running_flag != 1:
            ui.notify(position="top", type="warning", message=f"Please click “Run” first, then play")
            return
        
        logger.info("Started looping the copywriting~")
        ui.notify(position="top", type="positive", message="Started looping the copywriting~")
        
        audio.unpause_copywriting_play()

    # Copywriting page - pause play
    def copywriting_pause_play():
        if running_flag != 1:
            ui.notify(position="top", type="warning", message=f"Please click “Run” first, then pause")
            return
        
        audio.pause_copywriting_play()
        logger.info("Copywriting paused~")
        ui.notify(position="top", type="positive", message="Copywriting paused~")

    """
    Scheduled tasks
    """
    # - Add
    def schedule_add():
        data_len = len(schedule_var)
        tmp_config = {
            "enable": False,
            "time_min": 60,
            "time_max": 120,
            "copy": []
        }

        with schedule_config_card.style(card_css):
            with ui.row():
                schedule_var[str(data_len)] = ui.switch(text=f"Enable task#{int(data_len / 4) + 1}", value=tmp_config["enable"]).style(switch_internal_css)
                schedule_var[str(data_len + 1)] = ui.input(label=f"Min loop period#{int(data_len / 4) + 1}", value=tmp_config["time_min"], placeholder='Minimum duration (seconds) of the scheduled task loop; the task runs once every such period').style("width:100px;")
                schedule_var[str(data_len + 2)] = ui.input(label=f"Max loop period#{int(data_len / 4) + 1}", value=tmp_config["time_max"], placeholder='Maximum duration (seconds) of the scheduled task loop; the task runs once every such period').style("width:100px;")
                schedule_var[str(data_len + 3)] = ui.textarea(label=f"Copywriting list#{int(data_len / 4) + 1}", value=textarea_data_change(tmp_config["copy"]), placeholder='List of copywriting, separated by spaces or line breaks; use {variable} to replace key data; you can modify the source code to customize the function').style("width:500px;")


    # - Delete
    def schedule_del(index):
        try:
            schedule_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(4 * (int(index) - 1) + i) for i in range(4)]
            for key in keys_to_delete:
                if key in schedule_var:
                    del schedule_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(schedule_var.keys(), key=int):
                new_key = str(int(key) - 4 if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = schedule_var[key]

            # Apply the update
            schedule_var.clear()
            schedule_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())



    """
    Dynamic copywriting
    """
    # Dynamic copywriting - add
    def trends_copywriting_add():
        data_len = len(trends_copywriting_copywriting_var)
        tmp_config = {
            "folder_path": "",
            "prompt_change_enable": False,
            "prompt_change_content": ""
        }

        with trends_copywriting_config_card.style(card_css):
            with ui.row():
                trends_copywriting_copywriting_var[str(data_len)] = ui.input(label=f"Copywriting path#{int(data_len / 3) + 1}", value=tmp_config["folder_path"], placeholder='Folder path where copywriting files are stored').style("width:200px;")
                trends_copywriting_copywriting_var[str(data_len + 1)] = ui.switch(text=f"Prompt conversion#{int(data_len / 3) + 1}", value=tmp_config["prompt_change_enable"])
                trends_copywriting_copywriting_var[str(data_len + 2)] = ui.input(label=f"Prompt conversion content#{int(data_len / 3) + 1}", value=tmp_config["prompt_change_content"], placeholder='Use this prompt to convert the copywriting content before synthesis; the LLM used is the one configured as the chat type').style("width:500px;")


    # Dynamic copywriting - delete
    def trends_copywriting_del(index):
        try:
            trends_copywriting_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(3 * (int(index) - 1) + i) for i in range(3)]
            for key in keys_to_delete:
                if key in trends_copywriting_copywriting_var:
                    del trends_copywriting_copywriting_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(trends_copywriting_copywriting_var.keys(), key=int):
                new_key = str(int(key) - 3 if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = trends_copywriting_copywriting_var[key]

            # Apply the update
            trends_copywriting_copywriting_var.clear()
            trends_copywriting_copywriting_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())

    
    """
    Linked programs
    """
    # Linked programs - add
    def coordination_program_add():
        data_len = len(coordination_program_var)
        tmp_config = {
            "enable": True,
            "name": "",
            "executable": "",
            "parameters": []
        }

        with coordination_program_config_card.style(card_css):
            with ui.row():
                coordination_program_var[str(data_len)] = ui.switch(f'Enable#{int(data_len / 4) + 1}', value=tmp_config["enable"]).style(switch_internal_css)
                coordination_program_var[str(data_len + 1)] = ui.input(label=f"Program name#{int(data_len / 4) + 1}", value=tmp_config["name"], placeholder='Give your program a name, and do not use special characters!').style("width:200px;")
                coordination_program_var[str(data_len + 2)] = ui.input(label=f"Executable#{int(data_len / 4) + 1}", value=tmp_config["executable"], placeholder='Path to the executable, preferably an absolute path, e.g. for a python program').style("width:400px;")
                coordination_program_var[str(data_len + 3)] = ui.textarea(label=f'Parameters#{int(data_len / 4) + 1}', value=textarea_data_change(tmp_config["parameters"]), placeholder='Parameters; multiple parameters can be passed, separated by line breaks, e.g. the path of the program to launch, arguments carried by the command, etc.').style("width:500px;")


    # Linked programs - delete
    def coordination_program_del(index):
        try:
            coordination_program_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(4 * (int(index) - 1) + i) for i in range(4)]
            for key in keys_to_delete:
                if key in coordination_program_var:
                    del coordination_program_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(coordination_program_var.keys(), key=int):
                new_key = str(int(key) - 4 if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = coordination_program_var[key]

            # Apply the update
            coordination_program_var.clear()
            coordination_program_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())


    """
    Key/copywriting mapping
    """
    def key_mapping_add():
        data_len = len(key_mapping_config_var)
        tmp_config = {
            "keywords": [],
            "gift": [],
            "keys": [],
            "similarity": 1,
            "copywriting": [],
            "local_audio": [],
            "img_path": []
        }

        with key_mapping_config_card.style(card_css):
            with ui.row():
                num = int(data_len / 9) + 1
                key_mapping_config_var[str(data_len)] = ui.textarea(label=f"Keywords#{num}", value=textarea_data_change(tmp_config["keywords"]), placeholder='Enter the trigger keywords here; separate multiple ones with line breaks').style("width:100px;")
                key_mapping_config_var[str(data_len + 1)] = ui.textarea(label=f"Gift#{num}", value=textarea_data_change(tmp_config["gift"]), placeholder='Enter the trigger gift names here; separate multiple ones with line breaks').style("width:100px;")
                key_mapping_config_var[str(data_len + 2)] = ui.textarea(label=f"Key#{num}", value=textarea_data_change(tmp_config["keys"]), placeholder='Enter the keys you want to map here; separate multiple keys with line breaks (key names follow pyautogui rules)').style("width:100px;")
                key_mapping_config_var[str(data_len + 3)] = ui.input(label=f"Similarity#{num}", value=tmp_config["similarity"], placeholder='Similarity between the keywords and the user input; default 1 means 100%').style("width:50px;")
                key_mapping_config_var[str(data_len + 4)] = ui.textarea(label=f"Copywriting#{num}", value=textarea_data_change(tmp_config["copywriting"]), placeholder='Enter the copywriting content to synthesize after triggering; separate multiple ones with line breaks').style("width:300px;")
                key_mapping_config_var[str(data_len + 5)] = ui.textarea(label=f"Copywriting#{num}", value=textarea_data_change(tmp_config["copywriting"]), placeholder='Enter the copywriting content to synthesize after triggering; separate multiple ones with line breaks').style("width:300px;")
                key_mapping_config_var[str(data_len + 6)] = ui.input(label=f"Serial port name#{num}", value=tmp_config["serial_name"], placeholder='e.g. COM1').style("width:100px;").tooltip('Serial port name configured on the serial page, e.g. COM1')
                key_mapping_config_var[str(data_len + 7)] = ui.textarea(label=f"Serial send content#{num}", value=textarea_data_change(tmp_config["serial_send_data"]), placeholder='Separate multiple ones with line breaks. ASCII example: open led\nHEX example (2-character hexadecimal): 313233').style("width:300px;").tooltip('Enter the data to send to the serial port here; the data type is determined by the serial page settings; separate multiple ones with line breaks')
                key_mapping_config_var[str(data_len + 8)] = ui.textarea(label=f"Serial send content#{num}", value=textarea_data_change(tmp_config["serial_send_data"]), placeholder='Separate multiple ones with line breaks. ASCII example: open led\nHEX example (2-character hexadecimal): 313233').style("width:300px;").tooltip('Enter the data to send to the serial port here; the data type is determined by the serial page settings; separate multiple ones with line breaks')
                          
    
    def key_mapping_del(index):
        try:
            num = 9
            key_mapping_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(num * (int(index) - 1) + i) for i in range(num)]
            for key in keys_to_delete:
                if key in key_mapping_config_var:
                    del key_mapping_config_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(key_mapping_config_var.keys(), key=int):
                new_key = str(int(key) - num if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = key_mapping_config_var[key]

            # Apply the update
            key_mapping_config_var.clear()
            key_mapping_config_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())


    """
    Custom commands
    """
    
    # Custom commands - add
    def custom_cmd_add():
        data_len = len(custom_cmd_config_var)

        tmp_config = {
            "keywords": [],
            "similarity": 1,
            "api_url": "",
            "api_type": "",
            "resp_data_type": "",
            "data_analysis": "",
            "resp_template": ""
        }

        with custom_cmd_config_card.style(card_css):
            with ui.row():
                custom_cmd_config_var[str(data_len)] = ui.textarea(label=f"Keywords#{int(data_len / 7) + 1}", value=textarea_data_change(tmp_config["keywords"]), placeholder='Enter the trigger keywords here; separate multiple ones with line breaks').style("width:200px;")
                custom_cmd_config_var[str(data_len + 1)] = ui.input(label=f"Similarity#{int(data_len / 7) + 1}", value=tmp_config["similarity"], placeholder='Similarity between the keywords and the user input; default 1 means 100%').style("width:100px;")
                custom_cmd_config_var[str(data_len + 2)] = ui.textarea(label=f"API URL#{int(data_len / 7) + 1}", value=tmp_config["api_url"], placeholder='API link for sending HTTP requests', validation={'Please enter a URL in the correct format': lambda value: common.is_url_check(value),}).style("width:300px;")
                custom_cmd_config_var[str(data_len + 3)] = ui.select(label=f"API type#{int(data_len / 7) + 1}", value=tmp_config["api_type"], options={"GET": "GET"}).style("width:100px;")
                custom_cmd_config_var[str(data_len + 4)] = ui.select(label=f"Response data type#{int(data_len / 7) + 1}", value=tmp_config["resp_data_type"], options={"json": "json", "content": "content"}).style("width:150px;")
                custom_cmd_config_var[str(data_len + 5)] = ui.textarea(label=f"Data parsing (executed with eval)#{int(data_len / 7) + 1}", value=tmp_config["data_analysis"], placeholder='Data parsing; do not modify the resp variable arbitrarily, it is used to parse the final returned data').style("width:200px;")
                custom_cmd_config_var[str(data_len + 6)] = ui.textarea(label=f"Response content template#{int(data_len / 7) + 1}", value=tmp_config["resp_template"], placeholder='Do not delete the data variable arbitrarily; dynamic variables are supported; it will finally be merged into the complete content for audio synthesis').style("width:300px;")


    # Custom commands - delete
    def custom_cmd_del(index):
        try:
            custom_cmd_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(7 * (int(index) - 1) + i) for i in range(7)]
            for key in keys_to_delete:
                if key in custom_cmd_config_var:
                    del custom_cmd_config_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(custom_cmd_config_var.keys(), key=int):
                new_key = str(int(key) - 7 if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = custom_cmd_config_var[key]

            # Apply the update
            custom_cmd_config_var.clear()
            custom_cmd_config_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())

    """
    Serial port
    """
    
    def serial_config_add():
        data_len = len(serial_config_var)

        tmp_config = {
            "serial_name": "COM1",
            "baudrate": "115200",
            "serial_data_type": "ASCII"
        }

        with serial_config_card.style(card_css):
            with ui.row():
                serial_config_var[str(data_len)] = ui.select(label=f"Serial port name#{int(data_len / 8) + 1}", value=tmp_config["serial_name"], options={f'{tmp_config["serial_name"]}': f'{tmp_config["serial_name"]}'}).style("width:200px;").tooltip('Path where copywriting files are stored. Changing it is not recommended.')
                serial_config_var[str(data_len + 1)] = ui.select(
                    label=f"Baud rate#{int(data_len / 8) + 1}", 
                    value=tmp_config["baudrate"], 
                    options={'9600': '9600', '19200': '19200', '38400': '38400', '115200': '115200'}
                ).style("width:200px;").tooltip('Baud rate')
                serial_config_var[str(data_len + 2)] = ui.button('Refresh serial ports', on_click=lambda: refresh_serial(int(data_len / 8)))
                serial_config_var[str(data_len + 3)] = ui.button('Open serial port', on_click=lambda: connect_serial(int(data_len / 8)))
                serial_config_var[str(data_len + 4)] = ui.button('Close serial port', on_click=lambda: disconnect_serial(int(data_len / 8)))

                serial_config_var[str(data_len + 5)] = ui.select(label=f"Send data type#{int(data_len / 8) + 1}", value=tmp_config["serial_data_type"], options={'ASCII': 'ASCII', 'HEX': 'HEX'},).style("width:100px;").tooltip('Data type to send')
                serial_config_var[str(data_len + 6)] = ui.input(label=f"Send data#{int(data_len / 8) + 1}", value="", placeholder='Enter the content to send; after connecting, click Send').style("width:200px;").tooltip('Enter the content to send; after connecting, click Send')
                serial_config_var[str(data_len + 7)] = ui.button('Send', on_click=lambda: send_data_to_serial(int(data_len / 8)))

    def serial_config_del(index):
        try:
            serial_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(8 * (int(index) - 1) + i) for i in range(8)]
            for key in keys_to_delete:
                if key in serial_config_var:
                    del serial_config_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(serial_config_var.keys(), key=int):
                new_key = str(int(key) - 8 if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = serial_config_var[key]

            # Apply the update
            serial_config_var.clear()
            serial_config_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())


    """
    Add local path to URL path
    """
    # - Add
    def webui_local_dir_to_endpoint_add():
        data_len = len(webui_local_dir_to_endpoint_config_var)
        tmp_config = {
            "url_path": "",
            "local_dir": "",
        }

        with webui_local_dir_to_endpoint_config_card.style(card_css):
            with ui.row():
                webui_local_dir_to_endpoint_config_var[str(data_len)] = ui.input(label=f"URL path#{int(data_len / 2) + 1}", value=tmp_config["url_path"], placeholder='A string starting with a slash (“/”) that identifies the URL path under which files should be served to clients').style("width:300px;")
                webui_local_dir_to_endpoint_config_var[str(data_len + 1)] = ui.input(label=f"Local folder path#{int(data_len / 2) + 1}", value=tmp_config["local_dir"], placeholder='Local folder path; a relative path is recommended, preferably one inside the project').style("width:300px;")


    # - Delete
    def webui_local_dir_to_endpoint_del(index):
        try:
            webui_local_dir_to_endpoint_config_card.remove(int(index) - 1)
            # Delete operation
            keys_to_delete = [str(2 * (int(index) - 1) + i) for i in range(2)]
            for key in keys_to_delete:
                if key in webui_local_dir_to_endpoint_config_var:
                    del webui_local_dir_to_endpoint_config_var[key]

            # Renumber the remaining keys
            updates = {}
            for key in sorted(webui_local_dir_to_endpoint_config_var.keys(), key=int):
                new_key = str(int(key) - 2 if int(key) > int(keys_to_delete[-1]) else key)
                updates[new_key] = webui_local_dir_to_endpoint_config_var[key]

            # Apply the update
            webui_local_dir_to_endpoint_config_var.clear()
            webui_local_dir_to_endpoint_config_var.update(updates)
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Error, the index value is configured incorrectly:{e}")
            logger.error(traceback.format_exc())


    # Save config template
    def config_template_save(file_path: str):
        try:
            with open(config_path, 'r', encoding="utf-8") as config_file:
                config_data = json.load(config_file)

            config_data = webui_config_to_dict(config_data)

            # Save the JSON data to a file
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(config_data, file, indent=2, ensure_ascii=False)
                file.flush()  # Flush the buffer to make sure the write takes effect immediately

            logger.info("Config template saved successfully!")
            ui.notify(position="top", type="positive", message=f"Config template saved successfully!")

            return True
        except Exception as e:
            logger.error(f"Failed to save the config template!\n{e}")
            ui.notify(position="top", type="negative", message=f"Failed to save the config template!{e}")
            return False


    # Load config template
    def config_template_load(file_path: str):
        try:
            with open(file_path, 'r', encoding="utf-8") as config_file:
                config_data = json.load(config_file)

            # Save the JSON data to a file
            with open(config_path, "w", encoding="utf-8") as file:
                json.dump(config_data, file, indent=2, ensure_ascii=False)
                file.flush()  # Flush the buffer to make sure the write takes effect immediately

            logger.info("Config template loaded successfully! It will be read after restart! If you change your mind, just save the current config and then restart!!!")
            ui.notify(position="top", type="positive", message=f"Config template loaded successfully! It will be read after restart! If you change your mind, just save the current config and then restart!!!")
            
            return True
        except Exception as e:
            logger.error(f"Failed to read the config template!\n{e}")
            ui.notify(position="top", type="negative", message=f"Failed to read the config template!{e}")
            return False


    """
    Config operations
    """
    # Config check
    def check_config():
        try:
            # Validate the config on the Common Config page
            if select_platform.value == 'bilibili2' and select_bilibili_login_type.value == 'cookie' and input_bilibili_cookie.value == '':
                ui.notify(position="top", type="warning", message="Please go to Common Config - Bilibili first and fill in the Bilibili cookie")
                return False
            elif select_platform.value == 'bilibili2' and select_bilibili_login_type.value == 'open_live' and \
                (input_bilibili_open_live_ACCESS_KEY_ID.value == '' or input_bilibili_open_live_ACCESS_KEY_SECRET.value == '' or \
                input_bilibili_open_live_APP_ID.value == '' or input_bilibili_open_live_ROOM_OWNER_AUTH_CODE.value == ''):
                ui.notify(position="top", type="warning", message="Please go to Common Config - Bilibili first and fill in the Open Platform config")
                return False


            """
            Show hints based on the config
            """
            tip_config = f'Platform:{platform_options[select_platform.value]} | ' +\
                f'Large language model:{chat_type_options[select_chat_type.value]} | ' +\
                f'Speech synthesis:{audio_synthesis_type_options[select_audio_synthesis_type.value]} | ' +\
                f'Virtual body:{visual_body_options[select_visual_body.value]}'
            ui.notify(position="top", type="info", message=tip_config)

            # Check the platform config and show hints
            if select_platform.value == "dy":
                ui.notify(position="top", type="warning", message="When connecting to the Douyin platform, please start the Douyin danmaku listener first! The live room ID does not need to be filled in")
            elif select_platform.value == "bilibili":
                ui.notify(position="top", type="info", message="Bilibili 1 listening is not very stable; Bilibili 2 is recommended")
            elif select_platform.value == "bilibili2":
                if select_bilibili_login_type.value == "No login":
                    ui.notify(position="top", type="warning", message="Bilibili 2 cannot get the user’s full username without logging in")

            if select_visual_body.value == "metahuman_stream":
                ui.notify(position="top", type="warning", message="When connecting to metahuman_stream, speech synthesis is hosted by metahuman_stream and not controlled by AI Vtuber; please refer to the official docs to connect TTS yourself")

            if config.get("webui", "show_card", "common_config", "local_qa"):
                if not common.is_json_convertible(textarea_local_qa_text_json_file_content.value):
                    ui.notify(position="top", type="negative", message="The local Q&A json data format is incorrect, please check the JSON syntax!")
                    return False

            return True
        except Exception as e:
            ui.notify(position="top", type="negative", message=f"Config error:{e}")
            return False

    """
    
.................................................................................................................................................................
.................................................................................................................................................................
.................................................................................................................................................................
.................................................................................................................................................................
.............................................................................................................:**.................................................
........+++..........-++:....:++:...*##############:%%%%%%%%%#.....%%%%%%%%%%%%%%%%%%%%%%%.....%@#...........-@%..........+%%%%%%%%%%%%%+-----------:............
........%@#..........=@@=....-@@=....::::%#:=@+::::.........%%.....%%.....%%.....%#.....%%......+@@*..#%%%%%%%@@%%%%%%%%....=@#.....%@-.*%@#######%@=............
........%@#..........=@@=....-@@=........%*.-@+.............%%.....%@%%%%%@@%%%%%@@%%%%%@%........%%:........-@%............=@#.....%@-..#@-......#@-............
........%@#..........=@@=....-@@=....%%%%@@%%@%%%%=.........%%.....::........#%=........::...................=@%:...........=@%#####%@-..=@=.....-%%.............
........%@#..........=@@=....-@@=....%%..%*.-@+.=@=.........%%...%%%%%%%%%%%%@@%%%%%%%%%%%%*.:-----..#%%%%%%%%%%%%%%%%%@-...=@#-----%@-..:%#.....*@=.............
........%@#..........=@@=....-@@=....%%.:%*.-@+.=@=.-%@@@@@@@%...............%@=.............+##%@%.....=%%+:..=@#....#%:...=@#.....%@-...#@-....%%..............
........%@#..........=@@=....-@@=....%%.+@=.-@+.=@=.=@+.....##.......@%***************#@+.......=@%....-..:*%#.=@#....+*....=@#-----%@-...-%#...#@=..............
........%@#..........=@@=....-@@=....%%+@#...*%%%@=.=@+..............@#===============*@+.......=@%...-#@%*:...+@*..........=@%*****%@-....*@=.=%*...............
........#@%..........+@@:....-@@=....%%-*.......=@=.=@+..............@#-::::::::::::::+@+.......=@%......:**...*@+..........=@#.....%@-.....%@#%%................
........*@@=........:%@#.....-@@=....%@%%%%%%%%%%@=.=@+......-*:.....@%%%%%%%%%%%%%%%%%@+.......=@%.:%@@@@@@@@@@@@@@@@@@%...=@#.....%@++*=...%@#.................
.........*@@%-.....*%@%......-@@=....%%.........=@=.-@+......+@=.....@*...............=@+.......=@%..:........%@*.........+#%@%%%@@@@@#+-..:%@%@%................
..........:%%@@@@@@%%-.......-@@=....%%.........=@=.-@+......%@-.....@%%%%%%%%%%%%%%%%%@+.......=@%#@%:....:#@%*%@%*......+*=:......%@-...#@%..:%@*..............
.....................................%@@@@@@@@@@@@=.:%@#+==+%@%.....:@#...............=@*.......#@@#-..:+%@@%-....=#@@#-............%@--%@%-.....+%@%=...........
.....................................%%.........=%=...=*****+:..-***************************-...-+...#@%#+:..........-#%:...........%@=%#:.........+#............
.................................................................................................................................................................
.................................................................................................................................................................
.................................................................................................................................................................
.................................................................................................................................................................

    """

    # Read the webui config into the dict variable
    def webui_config_to_dict(config_data):
        """Read the webui config into the dict variable

        Args:
            config_data (dict): dict data read from the local config file
        """

        def common_textarea_handle(content):
            """Generic handling of textEdit multi-line text content

            Args:
                content (str): Original multi-line text content

            Returns:
                _type_: Processed multi-line text content
            """
            ret = [token.strip() for token in content.split("\n") if token.strip()]
            return ret

        # Type handler functions
        def handle_int(value):
            if value.value == '' or value.value is None:
                return 0
            return int(value.value)

        def handle_float(value):
            if value.value == '' or value.value is None:
                return 0
            return round(float(value.value), 2)

        def handle_string(value):
            return str(value.value)

        def handle_bool(value):
            return bool(value.value)

        def handle_textarea(value):
            return common_textarea_handle(value.value)

        # Handler mapping
        type_handlers = {
            'int': handle_int,
            'float': handle_float,
            'str': handle_string,
            'bool': handle_bool,
            'textarea': handle_textarea,
        }

        def update_nested_dict(target, keys, value):
            """Recursively update the nested dict"""
            if len(keys) == 1:
                target[keys[0]] = value
                return
            if keys[0] not in target:
                target[keys[0]] = {}
            update_nested_dict(target[keys[0]], keys[1:], value)

        def process_config_mapping(config_data, mapping, show_card_check=None):
            """Process the config mapping, supporting nesting at different levels"""
            def recurse_mapping(current_mapping, current_path=[]):
                for key, value in current_mapping.items():
                    new_path = current_path + [key]
                    if isinstance(value, dict):
                        recurse_mapping(value, new_path)
                    else:
                        component, type_name = value
                        handler = type_handlers[type_name]
                        processed_value = handler(component)
                        update_nested_dict(config_data, new_path, processed_value)

            recurse_mapping(mapping)
            return config_data


        def update_config(config_mapping, config, config_data, type="common_config"):
            # Process regular config
            for section, section_mapping in config_mapping.items():
                if type is not None:
                    if config.get("webui", "show_card", type, section):
                        if section not in config_data:
                            config_data[section] = {}
                        
                        process_config_mapping(config_data[section], section_mapping)
                else:
                    if section not in config_data:
                        config_data[section] = {}
                    
                    process_config_mapping(config_data[section], section_mapping)

            return config_data



        try:
            """
            Common Config
            """
            if True:
                config_data["platform"] = select_platform.value
                config_data["room_display_id"] = input_room_display_id.value
                config_data["chat_type"] = select_chat_type.value
                config_data["visual_body"] = select_visual_body.value
                config_data["need_lang"] = select_need_lang.value
                config_data["before_prompt"] = input_before_prompt.value
                config_data["after_prompt"] = input_after_prompt.value
                config_data["audio_synthesis_type"] = select_audio_synthesis_type.value

                config_mapping = {
                    "comment_template": {
                        "enable": (switch_comment_template_enable, 'bool'),
                        "copywriting": (input_comment_template_copywriting, 'str'),
                    },
                    "reply_template": {
                        "enable": (switch_reply_template_enable, 'bool'),
                        "username_max_len": (input_reply_template_username_max_len, 'int'),
                        "copywriting": (textarea_reply_template_copywriting, 'textarea'),
                    },
                    "bilibili": {
                        "login_type": (select_bilibili_login_type, 'str'),
                        "cookie": (input_bilibili_cookie, 'str'),
                        "ac_time_value": (input_bilibili_ac_time_value, 'str'),
                        "username": (input_bilibili_username, 'str'),
                        "password": (input_bilibili_password, 'str'),
                        "open_live": {
                            "ACCESS_KEY_ID": (input_bilibili_open_live_ACCESS_KEY_ID, 'str'),
                            "ACCESS_KEY_SECRET": (input_bilibili_open_live_ACCESS_KEY_SECRET, 'str'),
                            "APP_ID": (input_bilibili_open_live_APP_ID, 'int'),
                            "ROOM_OWNER_AUTH_CODE": (input_bilibili_open_live_ROOM_OWNER_AUTH_CODE, 'str'),
                        },
                    },
                    "ordinaryroad_barrage_fly": {
                        "ws_ip_port": (input_ordinaryroad_barrage_fly_ws_ip_port, 'str'),
                        "taskIds": (textarea_ordinaryroad_barrage_fly_taskIds, 'textarea'),
                    },
                    "twitch": {
                        "token": (input_twitch_token, 'str'),
                        "user": (input_twitch_user, 'str'),
                        "proxy_server": (input_twitch_proxy_server, 'str'),
                        "proxy_port": (input_twitch_proxy_port, 'str'),
                    },
                }
                config_data = update_config(config_mapping, config, config_data, None)
                
                config_mapping = {}
                # Log
                if config.get("webui", "show_card", "common_config", "log"):
                    config_data["comment_log_type"] = select_comment_log_type.value
                    config_data["captions"]["enable"] = switch_captions_enable.value
                    config_data["captions"]["file_path"] = input_captions_file_path.value
                    config_data["captions"]["raw_file_path"] = input_captions_raw_file_path.value

            
                # Audio playback
                if config.get("webui", "show_card", "common_config", "play_audio"):
                    # audio_player
                    config_data["audio_player"]["api_ip_port"] = input_audio_player_api_ip_port.value

                    config_mapping = {
                        "play_audio": {
                            "enable": (switch_play_audio_enable, 'bool'),
                            "text_split_enable": (switch_play_audio_text_split_enable, 'bool'),
                            "info_to_callback": (switch_play_audio_info_to_callback, 'bool'),
                            "interval_num_min": (input_play_audio_interval_num_min, 'int'),
                            "interval_num_max": (input_play_audio_interval_num_max, 'int'),
                            "normal_interval_min": (input_play_audio_normal_interval_min, 'float'),
                            "normal_interval_max": (input_play_audio_normal_interval_max, 'float'),
                            "out_path": (input_play_audio_out_path,'str'),
                            "player": (select_play_audio_player,'str'),
                        }
                    }

                if config.get("webui", "show_card", "common_config", "read_comment"):
                    config_mapping["read_comment"] = {
                        "enable": (switch_read_comment_enable, 'bool'),
                        "read_username_enable": (switch_read_comment_read_username_enable, 'bool'),
                        "username_max_len": (input_read_comment_username_max_len, 'int'),
                        "voice_change": (switch_read_comment_voice_change, 'bool'),
                        "read_username_copywriting": (textarea_read_comment_read_username_copywriting, 'textarea'),
                        "periodic_trigger": {
                            "enable": (switch_read_comment_periodic_trigger_enable, 'bool'),
                            "periodic_time_min": (input_read_comment_periodic_trigger_periodic_time_min, 'int'),
                            "periodic_time_max": (input_read_comment_periodic_trigger_periodic_time_max, 'int'),
                            "trigger_num_min": (input_read_comment_periodic_trigger_trigger_num_min, 'int'),
                            "trigger_num_max": (input_read_comment_periodic_trigger_trigger_num_max, 'int'),
                        },
                    }

                if config.get("webui", "show_card", "common_config", "local_qa"):
                    config_mapping["local_qa"] = {
                        "periodic_trigger": {
                            "enable": (switch_local_qa_periodic_trigger_enable, 'bool'),
                            "periodic_time_min": (input_local_qa_periodic_trigger_periodic_time_min, 'int'),
                            "periodic_time_max": (input_local_qa_periodic_trigger_periodic_time_max, 'int'),
                            "trigger_num_min": (input_local_qa_periodic_trigger_trigger_num_min, 'int'),
                            "trigger_num_max": (input_local_qa_periodic_trigger_trigger_num_max, 'int'),
                        },
                        "text": {
                            "enable": (switch_local_qa_text_enable, 'bool'),
                            "type": (select_local_qa_text_type, 'str'),
                            "file_path": (input_local_qa_text_file_path, 'str'),
                            "similarity": (input_local_qa_text_similarity, 'float'),
                            "username_max_len": (input_local_qa_text_username_max_len, 'int'),
                        },
                        "audio": {
                            "enable": (switch_local_qa_audio_enable, 'bool'),
                            "file_path": (input_local_qa_audio_file_path, 'str'),
                            "similarity": (input_local_qa_audio_similarity, 'float'),
                        },
                    }

                if config.get("webui", "show_card", "common_config", "filter"):
                    config_mapping["filter"] = {
                        "before_must_str": (textarea_filter_before_must_str, 'textarea'),
                        "after_must_str": (textarea_filter_after_must_str, 'textarea'),
                        "before_filter_str": (textarea_filter_before_filter_str, 'textarea'),
                        "after_filter_str": (textarea_filter_after_filter_str, 'textarea'),
                        "before_must_str_for_llm": (textarea_filter_before_must_str_for_llm, 'textarea'),
                        "after_must_str_for_llm": (textarea_filter_after_must_str_for_llm, 'textarea'),
                        "badwords": {
                            "enable": (switch_filter_badwords_enable, 'bool'),
                            "discard": (switch_filter_badwords_discard, 'bool'),
                            "path": (input_filter_badwords_path,'str'),
                            "bad_pinyin_path": (input_filter_badwords_bad_pinyin_path,'str'),
                            "replace": (input_filter_badwords_replace,'str'),
                        },
                        "username_convert_digits_to_chinese": (switch_filter_username_convert_digits_to_chinese, 'bool'),
                        "emoji": (switch_filter_emoji, 'bool'),
                        "max_len": (input_filter_max_len, 'int'),
                        "max_char_len": (input_filter_max_char_len, 'int'),
                        "comment_forget_duration": (input_filter_comment_forget_duration, 'float'),
                        "comment_forget_reserve_num": (input_filter_comment_forget_reserve_num, 'int'),
                        "gift_forget_duration": (input_filter_gift_forget_duration, 'float'),
                        "gift_forget_reserve_num": (input_filter_gift_forget_reserve_num, 'int'),
                        "entrance_forget_duration": (input_filter_entrance_forget_duration, 'float'),
                        "entrance_forget_reserve_num": (input_filter_entrance_forget_reserve_num, 'int'),
                        "follow_forget_duration": (input_filter_follow_forget_duration, 'float'),
                        "follow_forget_reserve_num": (input_filter_follow_forget_reserve_num, 'int'),
                        "talk_forget_duration": (input_filter_talk_forget_duration, 'float'),
                        "talk_forget_reserve_num": (input_filter_talk_forget_reserve_num, 'int'),
                        "schedule_forget_duration": (input_filter_schedule_forget_duration, 'float'),
                        "schedule_forget_reserve_num": (input_filter_schedule_forget_reserve_num, 'int'),
                        "idle_time_task_forget_duration": (input_filter_idle_time_task_forget_duration, 'float'),
                        "idle_time_task_forget_reserve_num": (input_filter_idle_time_task_forget_reserve_num, 'int'),
                        "image_recognition_schedule_forget_duration": (input_filter_image_recognition_schedule_forget_duration, 'float'),
                        "image_recognition_schedule_forget_reserve_num": (input_filter_image_recognition_schedule_forget_reserve_num, 'int'),
                        "limited_time_deduplication": {
                            "enable": (switch_filter_limited_time_deduplication_enable, 'bool'),
                            "comment": (input_filter_limited_time_deduplication_comment, 'int'),
                            "gift": (input_filter_limited_time_deduplication_gift, 'int'),
                            "entrance": (input_filter_limited_time_deduplication_entrance, 'int'),
                        },
                        "message_queue_max_len": (input_filter_message_queue_max_len, 'int'),
                        "voice_tmp_path_queue_max_len": (input_filter_voice_tmp_path_queue_max_len, 'int'),
                        "voice_tmp_path_queue_min_start_play": (input_filter_voice_tmp_path_queue_min_start_play, 'int'),
                        "priority_mapping": {
                            "idle_time_task": (input_filter_priority_mapping_idle_time_task, 'int'),
                            "image_recognition_schedule": (input_filter_priority_mapping_image_recognition_schedule, 'int'),
                            "local_qa_audio": (input_filter_priority_mapping_local_qa_audio, 'int'),
                            "comment": (input_filter_priority_mapping_comment, 'int'),
                            "song": (input_filter_priority_mapping_song, 'int'),
                            "read_comment": (input_filter_priority_mapping_read_comment, 'int'),
                            "entrance": (input_filter_priority_mapping_entrance, 'int'),
                            "gift": (input_filter_priority_mapping_gift, 'int'),
                            "follow": (input_filter_priority_mapping_follow, 'int'),
                            "talk": (input_filter_priority_mapping_talk, 'int'),
                            "reread": (input_filter_priority_mapping_reread, 'int'),
                            "key_mapping": (input_filter_priority_mapping_key_mapping, 'int'),
                            "integral": (input_filter_priority_mapping_integral, 'int'),
                            "reread_top_priority": (input_filter_priority_mapping_reread_top_priority, 'int'),
                            "copywriting": (input_filter_priority_mapping_copywriting, 'int'),
                            "abnormal_alarm": (input_filter_priority_mapping_abnormal_alarm, 'int'),
                            "trends_copywriting": (input_filter_priority_mapping_trends_copywriting, 'int'),
                            "schedule": (input_filter_priority_mapping_schedule, 'int'),
                            "assistant_anchor_text": (input_filter_priority_mapping_assistant_anchor_text, 'int'),
                            "assistant_anchor_audio": (input_filter_priority_mapping_assistant_anchor_audio, 'int'),
                        },
                        "blacklist": {
                            "enable": (switch_filter_blacklist_enable, 'bool'),
                            "username": (textarea_filter_blacklist_username, 'textarea'),
                        }
                    }

                if config.get("webui", "show_card", "common_config", "thanks"):
                    config_mapping["thanks"] = {
                        "username_max_len": (input_thanks_username_max_len, 'int'),
                        "entrance_enable": (switch_thanks_entrance_enable, 'bool'),
                        "entrance_random": (switch_thanks_entrance_random, 'bool'),
                        "entrance_copy": (textarea_thanks_entrance_copy, 'textarea'),
                        "entrance": {
                            "periodic_trigger": {
                                "enable": (switch_thanks_entrance_periodic_trigger_enable, 'bool'),
                                "periodic_time_min": (input_thanks_entrance_periodic_trigger_periodic_time_min, 'int'),
                                "periodic_time_max": (input_thanks_entrance_periodic_trigger_periodic_time_max, 'int'),
                                "trigger_num_min": (input_thanks_entrance_periodic_trigger_trigger_num_min, 'int'),
                                "trigger_num_max": (input_thanks_entrance_periodic_trigger_trigger_num_max, 'int'),
                            }
                        },
                        "gift_enable": (switch_thanks_gift_enable, 'bool'),
                        "gift_random": (switch_thanks_gift_random, 'bool'),
                        "gift_copy": (textarea_thanks_gift_copy, 'textarea'),
                        "gift": {
                            "periodic_trigger": {
                                "enable": (switch_thanks_gift_periodic_trigger_enable, 'bool'),
                                "periodic_time_min": (input_thanks_gift_periodic_trigger_periodic_time_min, 'int'),
                                "periodic_time_max": (input_thanks_gift_periodic_trigger_periodic_time_max, 'int'),
                                "trigger_num_min": (input_thanks_gift_periodic_trigger_trigger_num_min, 'int'),
                                "trigger_num_max": (input_thanks_gift_periodic_trigger_trigger_num_max, 'int'),
                            }
                        },
                        "follow_enable": (switch_thanks_follow_enable, 'bool'),
                        "follow_random": (switch_thanks_follow_random, 'bool'),
                        "follow_copy": (textarea_thanks_follow_copy, 'textarea'),
                        "follow": {
                            "periodic_trigger": {
                                "enable": (switch_thanks_follow_periodic_trigger_enable, 'bool'),
                                "periodic_time_min": (input_thanks_follow_periodic_trigger_periodic_time_min, 'int'),
                                "periodic_time_max": (input_thanks_follow_periodic_trigger_periodic_time_max, 'int'),
                                "trigger_num_min": (input_thanks_follow_periodic_trigger_trigger_num_min, 'int'),
                                "trigger_num_max": (input_thanks_follow_periodic_trigger_trigger_num_max, 'int'),
                            }
                        },
                        "lowest_price": (input_thanks_lowest_price, 'float')
                    }

                if config.get("webui", "show_card", "common_config", "audio_random_speed"):
                    config_mapping["audio_random_speed"] = {
                        "normal": {
                            "enable": (switch_audio_random_speed_normal_enable, 'bool'),
                            "speed_min": (input_audio_random_speed_normal_speed_min, 'float'),
                            "speed_max": (input_audio_random_speed_normal_speed_max, 'float'),
                        },
                        "copywriting": {
                            "enable": (switch_audio_random_speed_copywriting_enable, 'bool'),
                            "speed_min": (input_audio_random_speed_copywriting_speed_min, 'float'),
                            "speed_max": (input_audio_random_speed_copywriting_speed_max, 'float'),
                        },
                    }
                if config.get("webui", "show_card", "common_config", "choose_song"):
                    config_mapping["choose_song"] = {
                        "enable": (switch_choose_song_enable, 'bool'),
                        "start_cmd": (textarea_choose_song_start_cmd,'textarea'),
                        "stop_cmd": (textarea_choose_song_stop_cmd,'textarea'),
                        "random_cmd": (textarea_choose_song_random_cmd,'textarea'),
                        "song_path": (input_choose_song_song_path,'str'),
                        "match_fail_copy": (input_choose_song_match_fail_copy,'str'),
                        "similarity": (input_choose_song_similarity,'float'),
                    }
                if config.get("webui", "show_card", "common_config", "sd"):
                    config_mapping["sd"] = {
                        "enable": (switch_sd_enable, 'bool'),
                        "translate_type": (select_sd_translate_type, 'str'),
                        "prompt_llm": {
                            "type": (select_sd_prompt_llm_type, 'str'),
                            "before_prompt": (input_sd_prompt_llm_before_prompt, 'str'),
                            "after_prompt": (input_sd_prompt_llm_after_prompt, 'str'),
                        },
                        "trigger": (input_sd_trigger, 'str'),
                        "ip": (input_sd_ip, 'str'),
                        "port": (input_sd_port, 'int'),
                        "negative_prompt": (input_sd_negative_prompt, 'str'),
                        "seed": (input_sd_seed, 'float'),
                        "styles": (textarea_sd_styles, 'textarea'),
                        "cfg_scale": (input_sd_cfg_scale, 'int'),
                        "steps": (input_sd_steps, 'int'),
                        "hr_resize_x": (input_sd_hr_resize_x, 'int'),
                        "hr_resize_y": (input_sd_hr_resize_y, 'int'),
                        "enable_hr": (switch_sd_enable_hr, 'bool'),
                        "hr_scale": (input_sd_hr_scale, 'int'),
                        "hr_second_pass_steps": (input_sd_hr_second_pass_steps, 'int'),
                        "denoising_strength": (input_sd_denoising_strength, 'float'),
                        "save_enable": (switch_sd_save_enable, 'bool'),
                        "loop_cover": (switch_sd_loop_cover, 'bool'),
                        "save_path": (input_sd_save_path, 'str'),
                    }
                if config.get("webui", "show_card", "common_config", "search_online"):
                    config_mapping["search_online"] = {
                        "enable": (switch_search_online_enable, 'bool'),
                        "keyword_enable": (switch_search_online_keyword_enable, 'bool'),
                        "before_keyword": (textarea_search_online_before_keyword, 'textarea'),
                        "engine": (select_search_online_engine, 'str'),
                        "engine_id": (input_search_online_engine_id, 'int'),
                        "count": (input_search_online_count, 'int'),
                        "resp_template": (input_search_online_resp_template, 'str'),
                        "http_proxy": (input_search_online_http_proxy, 'str'),
                        "https_proxy": (input_search_online_https_proxy, 'str'),
                    }
                if config.get("webui", "show_card", "common_config", "web_captions_printer"):
                    config_mapping["web_captions_printer"] = {
                        "enable": (switch_web_captions_printer_enable, 'bool'),
                        "api_ip_port": (input_web_captions_printer_api_ip_port, 'str'),
                    }
                if config.get("webui", "show_card", "common_config", "database"):
                    config_mapping["database"] = {
                        "path": (input_database_path, 'str'),
                        "comment_enable": (switch_database_comment_enable, 'bool'),
                        "entrance_enable": (switch_database_entrance_enable, 'bool'),
                        "gift_enable": (switch_database_gift_enable, 'bool'),
                    }
                if config.get("webui", "show_card", "common_config", "abnormal_alarm"):
                    config_mapping["abnormal_alarm"] = {
                        "platform": {
                            "enable": (switch_abnormal_alarm_platform_enable, 'bool'),
                            "type": (select_abnormal_alarm_platform_type, 'str'),
                            "start_alarm_error_num": (input_abnormal_alarm_platform_start_alarm_error_num, 'int'),
                            "auto_restart_error_num": (input_abnormal_alarm_platform_auto_restart_error_num, 'int'),
                            "local_audio_path": (input_abnormal_alarm_platform_local_audio_path, 'str'),
                        },
                        "llm": {
                            "enable": (switch_abnormal_alarm_llm_enable, 'bool'),
                            "type": (select_abnormal_alarm_llm_type, 'str'),
                            "start_alarm_error_num": (input_abnormal_alarm_llm_start_alarm_error_num, 'int'),
                            "auto_restart_error_num": (input_abnormal_alarm_llm_auto_restart_error_num, 'int'),
                            "local_audio_path": (input_abnormal_alarm_llm_local_audio_path, 'str'),
                        },
                        "tts": {
                            "enable": (switch_abnormal_alarm_tts_enable, 'bool'),
                            "type": (select_abnormal_alarm_tts_type, 'str'),
                            "start_alarm_error_num": (input_abnormal_alarm_tts_start_alarm_error_num, 'int'),
                            "auto_restart_error_num": (input_abnormal_alarm_tts_auto_restart_error_num, 'int'),
                            "local_audio_path": (input_abnormal_alarm_tts_local_audio_path, 'str'),
                        },
                        "svc": {
                            "enable": (switch_abnormal_alarm_svc_enable, 'bool'),
                            "type": (select_abnormal_alarm_svc_type, 'str'),
                            "start_alarm_error_num": (input_abnormal_alarm_svc_start_alarm_error_num, 'int'),
                            "auto_restart_error_num": (input_abnormal_alarm_svc_auto_restart_error_num, 'int'),
                            "local_audio_path": (input_abnormal_alarm_svc_local_audio_path, 'str'),
                        },
                        "visual_body": {
                            "enable": (switch_abnormal_alarm_visual_body_enable, 'bool'),
                            "type": (select_abnormal_alarm_visual_body_type, 'str'),
                            "start_alarm_error_num": (input_abnormal_alarm_visual_body_start_alarm_error_num, 'int'),
                            "auto_restart_error_num": (input_abnormal_alarm_visual_body_auto_restart_error_num, 'int'),
                            "local_audio_path": (input_abnormal_alarm_visual_body_local_audio_path, 'str'),
                        },
                        "other": {
                            "enable": (switch_abnormal_alarm_other_enable, 'bool'),
                            "type": (select_abnormal_alarm_other_type, 'str'),
                            "start_alarm_error_num": (input_abnormal_alarm_other_start_alarm_error_num, 'int'),
                            "auto_restart_error_num": (input_abnormal_alarm_other_auto_restart_error_num, 'int'),
                            "local_audio_path": (input_abnormal_alarm_other_local_audio_path, 'str'),
                        },
                    }

                config_data = update_config(config_mapping, config, config_data, "common_config")
                
                # Scheduled tasks
                if config.get("webui", "show_card", "common_config", "schedule"):
                    tmp_arr = []
                    # logger.info(schedule_var)
                    for index in range(len(schedule_var) // 4):
                        tmp_json = {
                            "enable": False,
                            "time_min": 60,
                            "time_max": 120,
                            "copy": []
                        }
                        tmp_json["enable"] = schedule_var[str(4 * index)].value
                        tmp_json["time_min"] = round(float(schedule_var[str(4 * index + 1)].value), 1)
                        tmp_json["time_max"] = round(float(schedule_var[str(4 * index + 2)].value), 1)
                        tmp_json["copy"] = common_textarea_handle(schedule_var[str(4 * index + 3)].value)

                        tmp_arr.append(tmp_json)
                    # logger.info(tmp_arr)
                    config_data["schedule"] = tmp_arr

                # Idle-time task
                if config.get("webui", "show_card", "common_config", "idle_time_task"):
                    config_data["idle_time_task"]["enable"] = switch_idle_time_task_enable.value
                    config_data["idle_time_task"]["type"] = select_idle_time_task_type.value

                    config_data["idle_time_task"]["min_msg_queue_len_to_trigger"] = int(input_idle_time_task_idle_min_msg_queue_len_to_trigger.value)
                    config_data["idle_time_task"]["min_audio_queue_len_to_trigger"] = int(input_idle_time_task_idle_min_audio_queue_len_to_trigger.value)

                    config_data["idle_time_task"]["idle_time_min"] = int(input_idle_time_task_idle_time_min.value)
                    config_data["idle_time_task"]["idle_time_max"] = int(input_idle_time_task_idle_time_max.value)
                    config_data["idle_time_task"]["wait_play_audio_num_threshold"] = int(input_idle_time_task_wait_play_audio_num_threshold.value)
                    config_data["idle_time_task"]["idle_time_reduce_to"] = int(input_idle_time_task_idle_time_reduce_to.value)

                    tmp_arr = []
                    for index in range(len(idle_time_task_trigger_type_var)):
                        if idle_time_task_trigger_type_var[str(index)].value:
                            tmp_arr.append(common.find_keys_by_value(idle_time_task_trigger_type_mapping, idle_time_task_trigger_type_var[str(index)].text)[0])
                    # logger.info(tmp_arr)
                    config_data["idle_time_task"]["trigger_type"] = tmp_arr

                    config_data["idle_time_task"]["comment"]["enable"] = switch_idle_time_task_comment_enable.value
                    config_data["idle_time_task"]["comment"]["random"] = switch_idle_time_task_comment_random.value
                    config_data["idle_time_task"]["copywriting"]["copy"] = common_textarea_handle(textarea_idle_time_task_copywriting_copy.value)
                    config_data["idle_time_task"]["copywriting"]["enable"] = switch_idle_time_task_copywriting_enable.value
                    config_data["idle_time_task"]["copywriting"]["random"] = switch_idle_time_task_copywriting_random.value
                    config_data["idle_time_task"]["comment"]["copy"] = common_textarea_handle(textarea_idle_time_task_comment_copy.value)
                    config_data["idle_time_task"]["local_audio"]["enable"] = switch_idle_time_task_local_audio_enable.value
                    config_data["idle_time_task"]["local_audio"]["random"] = switch_idle_time_task_local_audio_random.value
                    config_data["idle_time_task"]["local_audio"]["path"] = common_textarea_handle(textarea_idle_time_task_local_audio_path.value)


                # Dynamic copywriting
                if config.get("webui", "show_card", "common_config", "trends_copywriting"):
                    config_data["trends_copywriting"]["enable"] = switch_trends_copywriting_enable.value
                    config_data["trends_copywriting"]["llm_type"] = select_trends_copywriting_llm_type.value
                    config_data["trends_copywriting"]["random_play"] = switch_trends_copywriting_random_play.value
                    config_data["trends_copywriting"]["play_interval"] = int(input_trends_copywriting_play_interval.value)
                    tmp_arr = []
                    for index in range(len(trends_copywriting_copywriting_var) // 3):
                        tmp_json = {
                            "folder_path": "",
                            "prompt_change_enable": False,
                            "prompt_change_content": ""
                        }
                        tmp_json["folder_path"] = trends_copywriting_copywriting_var[str(3 * index)].value
                        tmp_json["prompt_change_enable"] = trends_copywriting_copywriting_var[str(3 * index + 1)].value
                        tmp_json["prompt_change_content"] = trends_copywriting_copywriting_var[str(3 * index + 2)].value

                        tmp_arr.append(tmp_json)
                    # logger.info(tmp_arr)
                    config_data["trends_copywriting"]["copywriting"] = tmp_arr

                
                # Key mapping
                if config.get("webui", "show_card", "common_config", "key_mapping"):
                    config_data["key_mapping"]["enable"] = switch_key_mapping_enable.value
                    config_data["key_mapping"]["type"] = select_key_mapping_type.value
                    config_data["key_mapping"]["key_trigger_type"] = select_key_mapping_key_trigger_type.value
                    config_data["key_mapping"]["key_single_sentence_trigger_once"] = switch_key_mapping_key_single_sentence_trigger_once_enable.value
                    config_data["key_mapping"]["copywriting_trigger_type"] = select_key_mapping_copywriting_trigger_type.value
                    config_data["key_mapping"]["copywriting_single_sentence_trigger_once"] = switch_key_mapping_copywriting_single_sentence_trigger_once_enable.value
                    config_data["key_mapping"]["local_audio_trigger_type"] = select_key_mapping_local_audio_trigger_type.value
                    config_data["key_mapping"]["local_audio_single_sentence_trigger_once"] = switch_key_mapping_local_audio_single_sentence_trigger_once_enable.value
                    config_data["key_mapping"]["serial_trigger_type"] = select_key_mapping_serial_trigger_type.value
                    config_data["key_mapping"]["serial_single_sentence_trigger_once"] = switch_key_mapping_serial_single_sentence_trigger_once_enable.value
                    config_data["key_mapping"]["img_path_trigger_type"] = select_key_mapping_img_path_trigger_type.value
                    config_data["key_mapping"]["img_path_single_sentence_trigger_once"] = switch_key_mapping_img_path_single_sentence_trigger_once_enable.value
                    

                    config_data["key_mapping"]["start_cmd"] = input_key_mapping_start_cmd.value
                    tmp_arr = []
                    # logger.info(key_mapping_config_var)

                    num = 9

                    for index in range(len(key_mapping_config_var) // num):
                        tmp_json = {
                            "keywords": [],
                            "gift": [],
                            "keys": [],
                            "similarity": 0.8,
                            "copywriting": [],
                            "serial_name": "",
                            "serial_send_data": [],
                            "img_path": []
                        }
                        tmp_json["keywords"] = common_textarea_handle(key_mapping_config_var[str(num * index)].value)
                        tmp_json["gift"] = common_textarea_handle(key_mapping_config_var[str(num * index + 1)].value)
                        tmp_json["keys"] = common_textarea_handle(key_mapping_config_var[str(num * index + 2)].value)
                        tmp_json["similarity"] = key_mapping_config_var[str(num * index + 3)].value
                        tmp_json["copywriting"] = common_textarea_handle(key_mapping_config_var[str(num * index + 4)].value)
                        tmp_json["local_audio"] = common_textarea_handle(key_mapping_config_var[str(num * index + 5)].value)
                        tmp_json["serial_name"] = key_mapping_config_var[str(num * index + 6)].value
                        tmp_json["serial_send_data"] = common_textarea_handle(key_mapping_config_var[str(num * index + 7)].value)
                        tmp_json["img_path"] = common_textarea_handle(key_mapping_config_var[str(num * index + 8)].value)

                        tmp_arr.append(tmp_json)
                    # logger.info(tmp_arr)
                    config_data["key_mapping"]["config"] = tmp_arr

                # Custom commands
                if config.get("webui", "show_card", "common_config", "custom_cmd"):
                    config_data["custom_cmd"]["enable"] = switch_custom_cmd_enable.value
                    config_data["custom_cmd"]["type"] = select_custom_cmd_type.value
                    tmp_arr = []
                    # logger.info(custom_cmd_config_var)
                    for index in range(len(custom_cmd_config_var) // 7):
                        tmp_json = {
                            "keywords": [],
                            "similarity": 1,
                            "api_url": "",
                            "api_type": "",
                            "resp_data_type": "",
                            "data_analysis": "",
                            "resp_template": ""
                        }
                        tmp_json["keywords"] = common_textarea_handle(custom_cmd_config_var[str(7 * index)].value)
                        tmp_json["similarity"] = float(custom_cmd_config_var[str(7 * index + 1)].value)
                        tmp_json["api_url"] = custom_cmd_config_var[str(7 * index + 2)].value
                        tmp_json["api_type"] = custom_cmd_config_var[str(7 * index + 3)].value
                        tmp_json["resp_data_type"] = custom_cmd_config_var[str(7 * index + 4)].value
                        tmp_json["data_analysis"] = custom_cmd_config_var[str(7 * index + 5)].value
                        tmp_json["resp_template"] = custom_cmd_config_var[str(7 * index + 6)].value

                        tmp_arr.append(tmp_json)
                    # logger.info(tmp_arr)
                    config_data["custom_cmd"]["config"] = tmp_arr

                # Dynamic config
                if config.get("webui", "show_card", "common_config", "trends_config"):
                    config_data["trends_config"]["enable"] = switch_trends_config_enable.value
                    tmp_arr = []
                    # logger.info(trends_config_path_var)
                    for index in range(len(trends_config_path_var) // 2):
                        tmp_json = {
                            "online_num": "0-999999999",
                            "path": "config.json"
                        }
                        tmp_json["online_num"] = trends_config_path_var[str(2 * index)].value
                        tmp_json["path"] = trends_config_path_var[str(2 * index + 1)].value

                        tmp_arr.append(tmp_json)
                    # logger.info(tmp_arr)
                    config_data["trends_config"]["path"] = tmp_arr

                
                # Linked programs
                if config.get("webui", "show_card", "common_config", "coordination_program"):
                    tmp_arr = []
                    for index in range(len(coordination_program_var) // 4):
                        tmp_json = {
                            "enable": True,
                            "name": "",
                            "executable": "",
                            "parameters": []
                        }
                        tmp_json["enable"] = coordination_program_var[str(4 * index)].value
                        tmp_json["name"] = coordination_program_var[str(4 * index + 1)].value
                        tmp_json["executable"] = coordination_program_var[str(4 * index + 2)].value
                        tmp_json["parameters"] = common_textarea_handle(coordination_program_var[str(4 * index + 3)].value)

                        tmp_arr.append(tmp_json)
                    # logger.info(tmp_arr)
                    config_data["coordination_program"] = tmp_arr
                
                tmp_arr = []
                for index in range(len(luoxi_project_Live_Comment_Assistant_type_var)):
                    if luoxi_project_Live_Comment_Assistant_type_var[str(index)].value:
                        tmp_arr.append(
                            common.find_keys_by_value(
                                luoxi_project_Live_Comment_Assistant_type_mapping, 
                                luoxi_project_Live_Comment_Assistant_type_var[str(index)].text
                            )[0]
                        )
                # logger.info(tmp_arr)
                config_data["luoxi_project"]["Live_Comment_Assistant"]["type"] = tmp_arr

                tmp_arr = []
                for index in range(len(luoxi_project_Live_Comment_Assistant_trigger_position_var)):
                    if luoxi_project_Live_Comment_Assistant_trigger_position_var[str(index)].value:
                        tmp_arr.append(
                            common.find_keys_by_value(
                                luoxi_project_Live_Comment_Assistant_trigger_position_mapping, 
                                luoxi_project_Live_Comment_Assistant_trigger_position_var[str(index)].text
                            )[0]
                        )
                # logger.info(tmp_arr)
                config_data["luoxi_project"]["Live_Comment_Assistant"]["trigger_position"] = tmp_arr

                config_mapping = {
                    "luoxi_project": {
                        "Live_Comment_Assistant": {
                            "enable": (switch_luoxi_project_Live_Comment_Assistant_enable, 'bool'),
                            "version": (select_luoxi_project_Live_Comment_Assistant_version, 'str'),
                            "api_ip_port": (input_luoxi_project_Live_Comment_Assistant_api_ip_port, 'str'),
                        }
                    }
                }

                config_data = update_config(config_mapping, config, config_data, None)

            """
            LLM
            """
            if True:
                config_mapping = {}
                if config.get("webui", "show_card", "llm", "chatgpt"):
                    config_data["openai"]["api"] = input_openai_api.value
                    config_data["openai"]["api_key"] = common_textarea_handle(textarea_openai_api_key.value)
                    # logger.info(select_chatgpt_model.value)

                    config_mapping["chatgpt"] = {
                        "model": (select_chatgpt_model, 'str'),
                        "temperature": (input_chatgpt_temperature, 'float'),
                        "max_tokens": (input_chatgpt_max_tokens, 'int'),
                        "top_p": (input_chatgpt_top_p, 'float'),
                        "presence_penalty": (input_chatgpt_presence_penalty, 'float'),
                        "frequency_penalty": (input_chatgpt_frequency_penalty, 'float'),
                        "preset": (input_chatgpt_preset, 'str'),
                        "stream": (switch_chatgpt_stream, 'bool'),
                    }

                    config_data = update_config(config_mapping, config, config_data, "llm")


                if config.get("webui", "show_card", "llm", "chat_with_file"):
                    config_mapping["chat_with_file"] = {
                        "chat_mode": (select_chat_with_file_chat_mode, 'str'),
                        "data_path": (input_chat_with_file_data_path, 'str'),
                        "separator": (input_chat_with_file_separator, 'str'),
                        "chunk_size": (input_chat_with_file_chunk_size, 'int'),
                        "chunk_overlap": (input_chat_with_file_chunk_overlap, 'int'),
                        "local_vector_embedding_model": (select_chat_with_file_local_vector_embedding_model, 'str'),
                        "chain_type": (input_chat_with_file_chain_type, 'str'),
                        "question_prompt": (input_chat_with_file_question_prompt, 'str'),
                        "local_max_query": (input_chat_with_file_local_max_query, 'int'),
                        "show_token_cost": (switch_chat_with_file_show_token_cost, 'bool'),
                    }
                if config.get("webui", "show_card", "llm", "chatterbot"):
                    config_mapping["chatterbot"] = {
                        "name": (input_chatterbot_name, 'str'),
                        "db_path": (input_chatterbot_db_path, 'str'),
                    }
                if config.get("webui", "show_card", "llm", "text_generation_webui"):
                    config_mapping["text_generation_webui"] = {
                        "type": (select_text_generation_webui_type, 'str'),
                        "api_ip_port": (input_text_generation_webui_api_ip_port, 'str'),
                        "max_new_tokens": (input_text_generation_webui_max_new_tokens, 'int'),
                        "history_enable": (switch_text_generation_webui_history_enable, 'bool'),
                        "history_max_len": (input_text_generation_webui_history_max_len, 'int'),
                        "mode": (select_text_generation_webui_mode, 'str'),
                        "character": (input_text_generation_webui_character, 'str'),
                        "instruction_template": (input_text_generation_webui_instruction_template, 'str'),
                        "your_name": (input_text_generation_webui_your_name, 'str'),
                        "top_p": (input_text_generation_webui_top_p, 'float'),
                        "top_k": (input_text_generation_webui_top_k, 'int'),
                        "temperature": (input_text_generation_webui_temperature, 'float'),
                        "seed": (input_text_generation_webui_seed, 'float'),
                    }
                if config.get("webui", "show_card", "llm", "sparkdesk"):
                    config_mapping["sparkdesk"] = {
                        "type": (select_sparkdesk_type, 'str'),
                        "cookie": (input_sparkdesk_cookie, 'str'),
                        "fd": (input_sparkdesk_fd, 'str'),
                        "GtToken": (input_sparkdesk_GtToken, 'str'),
                        "app_id": (input_sparkdesk_app_id, 'str'),
                        "api_secret": (input_sparkdesk_api_secret, 'str'),
                        "api_key": (input_sparkdesk_api_key, 'str'),
                        "version": (select_sparkdesk_version, 'float'),
                        "assistant_id": (input_sparkdesk_assistant_id, 'str'),
                    }
                if config.get("webui", "show_card", "llm", "langchain_chatchat"):
                    config_mapping["langchain_chatchat"] = {
                        "api_ip_port": (input_langchain_chatchat_api_ip_port, 'str'),
                        "chat_type": (select_langchain_chatchat_chat_type, 'str'),
                        "history_enable": (switch_langchain_chatchat_history_enable, 'bool'),
                        "history_max_len": (input_langchain_chatchat_history_max_len, 'int'),
                        "llm": {
                            "model_name": (input_langchain_chatchat_llm_model_name, 'str'),
                            "temperature": (input_langchain_chatchat_llm_temperature, 'float'),
                            "max_tokens": (input_langchain_chatchat_llm_max_tokens, 'int'),
                            "prompt_name": (input_langchain_chatchat_llm_prompt_name, 'str'),
                        },
                        "knowledge_base": {
                            "knowledge_base_name": (input_langchain_chatchat_knowledge_base_knowledge_base_name, 'str'),
                            "top_k": (input_langchain_chatchat_knowledge_base_top_k, 'int'),
                            "score_threshold": (input_langchain_chatchat_knowledge_base_score_threshold, 'float'),
                            "model_name": (input_langchain_chatchat_knowledge_base_model_name, 'str'),
                            "temperature": (input_langchain_chatchat_knowledge_base_temperature, 'float'),
                            "max_tokens": (input_langchain_chatchat_knowledge_base_max_tokens, 'int'),
                            "prompt_name": (input_langchain_chatchat_knowledge_base_prompt_name, 'str'),
                        },
                        "search_engine": {
                            "search_engine_name": (select_langchain_chatchat_search_engine_search_engine_name, 'str'),
                            "top_k": (input_langchain_chatchat_search_engine_top_k, 'int'),
                            "model_name": (input_langchain_chatchat_search_engine_model_name, 'str'),
                            "temperature": (input_langchain_chatchat_search_engine_temperature, 'float'),
                            "max_tokens": (input_langchain_chatchat_search_engine_max_tokens, 'int'),
                            "prompt_name": (input_langchain_chatchat_search_engine_prompt_name, 'str'),
                        },
                    }
                if config.get("webui", "show_card", "llm", "zhipu"):
                    config_mapping["zhipu"] = {
                        "api_key": (input_zhipu_api_key, 'str'),
                        "model": (select_zhipu_model, 'str'),
                        "app_id": (input_zhipu_app_id, 'str'),
                        "top_p": (input_zhipu_top_p, 'str'),
                        "temperature": (input_zhipu_temperature, 'str'),
                        "history_enable": (switch_zhipu_history_enable, 'bool'),
                        "history_max_len": (input_zhipu_history_max_len, 'str'),
                        "user_info": (input_zhipu_user_info, 'str'),
                        "bot_info": (input_zhipu_bot_info, 'str'),
                        "bot_name": (input_zhipu_bot_name, 'str'),
                        "username": (input_zhipu_username, 'str'),
                        "remove_useless": (switch_zhipu_remove_useless, 'bool'),
                        "stream": (switch_zhipu_stream, 'bool'),
                        "assistant_api": {
                            "api_key": (input_zhipu_assistant_api_api_key, 'str'),
                            "api_secret": (input_zhipu_assistant_api_api_secret, 'str'),
                            "assistant_id": (input_zhipu_assistant_api_assistant_id, 'str'),
                        },
                    }
                if config.get("webui", "show_card", "llm", "bard"):
                    config_mapping["bard"] = {
                        "token": (input_bard_token, 'str'),
                    }
                if config.get("webui", "show_card", "llm", "tongyi"):
                    config_mapping["tongyi"] = {
                        "type": (select_tongyi_type, 'str'),
                        "cookie_path": (input_tongyi_cookie_path, 'str'),
                        "api_key": (input_tongyi_api_key, 'str'),
                        "model": (select_tongyi_model, 'str'),
                        "preset": (input_tongyi_preset, 'str'),
                        "temperature": (input_tongyi_temperature, 'float'),
                        "top_p": (input_tongyi_top_p, 'float'),
                        "top_k": (input_tongyi_top_k, 'int'),
                        "enable_search": (switch_tongyi_enable_search, 'bool'),
                        "history_enable": (switch_tongyi_history_enable, 'bool'),
                        "history_max_len": (input_tongyi_history_max_len, 'int'),
                        "stream": (switch_tongyi_stream, 'bool'),
                    }
                if config.get("webui", "show_card", "llm", "tongyixingchen"):
                    config_mapping["tongyixingchen"] = {
                        "access_token": (input_tongyixingchen_access_token, 'str'),
                        "type": (select_tongyixingchen_type, 'str'),
                        "history_enable": (switch_tongyixingchen_history_enable, 'bool'),
                        "history_max_len": (input_tongyixingchen_history_max_len, 'int'),
                        "stream": (switch_tongyixingchen_stream, 'bool'),
                        "Fixed role": {
                            "character_id": (input_tongyixingchen_GDJS_character_id, 'str'),
                            "top_p": (input_tongyixingchen_GDJS_top_p, 'float'),
                            "temperature": (input_tongyixingchen_GDJS_temperature, 'float'),
                            "seed": (input_tongyixingchen_GDJS_seed, 'int'),
                            "user_id": (input_tongyixingchen_GDJS_user_id, 'str'),
                            "username": (input_tongyixingchen_GDJS_username, 'str'),
                            "role_name": (input_tongyixingchen_GDJS_role_name, 'str'),
                        },
                    }
                if config.get("webui", "show_card", "llm", "my_wenxinworkshop"):
                    config_mapping["my_wenxinworkshop"] = {
                        "type": (select_my_wenxinworkshop_type, 'str'),
                        "model": (select_my_wenxinworkshop_model, 'str'),
                        "api_key": (input_my_wenxinworkshop_api_key, 'str'),
                        "secret_key": (input_my_wenxinworkshop_secret_key, 'str'),
                        "top_p": (input_my_wenxinworkshop_top_p, 'float'),
                        "temperature": (input_my_wenxinworkshop_temperature, 'float'),
                        "penalty_score": (input_my_wenxinworkshop_penalty_score, 'float'),
                        "history_enable": (switch_my_wenxinworkshop_history_enable, 'bool'),
                        "history_max_len": (input_my_wenxinworkshop_history_max_len, 'int'),
                        "stream": (switch_my_wenxinworkshop_stream, 'bool'),
                        "app_id": (input_my_wenxinworkshop_app_id, 'str'),
                        "app_token": (input_my_wenxinworkshop_app_token, 'str'),
                    }
                if config.get("webui", "show_card", "llm", "gemini"):
                    config_mapping["gemini"] = {
                        "api_key": (input_gemini_api_key, 'str'),
                        "model": (select_gemini_model, 'str'),
                        "history_enable": (switch_gemini_history_enable, 'bool'),
                        "history_max_len": (input_gemini_history_max_len, 'int'),
                        "http_proxy": (input_gemini_http_proxy, 'str'),
                        "https_proxy": (input_gemini_https_proxy, 'str'),
                        "max_output_tokens": (input_gemini_max_output_tokens, 'int'),
                        "temperature": (input_gemini_max_temperature, 'float'),
                        "top_p": (input_gemini_top_p, 'float'),
                        "top_k": (input_gemini_top_k, 'int'),
                    }
                
                if config.get("webui", "show_card", "llm", "koboldcpp"):
                    config_mapping["koboldcpp"] = {
                        "api_ip_port": (input_koboldcpp_api_ip_port, 'str'),
                        "max_context_length": (input_koboldcpp_max_context_length, 'int'),
                        "max_length": (input_koboldcpp_max_length, 'int'),
                        "quiet": (switch_koboldcpp_quiet, 'bool'),
                        "rep_pen": (input_koboldcpp_rep_pen, 'float'),
                        "rep_pen_range": (input_koboldcpp_rep_pen_range, 'int'),
                        "rep_pen_slope": (input_koboldcpp_rep_pen_slope, 'int'),
                        "temperature": (input_koboldcpp_temperature, 'float'),
                        "tfs": (input_koboldcpp_tfs, 'int'),
                        "top_a": (input_koboldcpp_top_a, 'int'),
                        "top_p": (input_koboldcpp_top_p, 'float'),
                        "top_k": (input_koboldcpp_top_k, 'int'),
                        "typical": (input_koboldcpp_typical, 'int'),
                        "history_enable": (switch_koboldcpp_history_enable, 'bool'),
                        "history_max_len": (input_koboldcpp_history_max_len, 'int'),
                    }
                if config.get("webui", "show_card", "llm", "anythingllm"):
                    config_mapping["anythingllm"] = {
                        "api_ip_port": (input_anythingllm_api_ip_port, 'str'),
                        "api_key": (input_anythingllm_api_key, 'str'),
                        "mode": (select_anythingllm_mode, 'str'),
                        "workspace_slug": (select_anythingllm_workspace_slug, 'str'),
                    }
                if config.get("webui", "show_card", "llm", "dify"):
                    config_mapping["dify"] = {
                        "api_ip_port": (input_dify_api_ip_port, 'str'),
                        "api_key": (input_dify_api_key, 'str'),
                        "type": (select_dify_type, 'str'),
                        "history_enable": (switch_dify_history_enable, 'bool'),
                        "stream": (switch_dify_stream, 'bool'),
                        "custom_params": (textarea_dify_custom_params, 'str'),  
                    }
                if config.get("webui", "show_card", "llm", "gpt4free"):
                    config_mapping["gpt4free"] = {
                        "provider": (select_gpt4free_provider, 'str'),
                        "api_key": (input_gpt4free_api_key, 'str'),
                        "model": (select_gpt4free_model, 'str'),
                        "proxy": (input_gpt4free_proxy, 'str'),
                        "max_tokens": (input_gpt4free_max_tokens, 'int'),
                        "preset": (input_gpt4free_preset, 'str'),
                        "history_enable": (switch_gpt4free_history_enable, 'bool'),
                        "history_max_len": (input_gpt4free_history_max_len, 'int'),
                    }
                if config.get("webui", "show_card", "llm", "volcengine"):
                    config_mapping["volcengine"] = {
                        "api_key": (input_volcengine_api_key, 'str'),
                        "model": (input_volcengine_model, 'str'),
                        "preset": (input_volcengine_preset, 'str'),
                        "history_enable": (switch_volcengine_history_enable, 'bool'),
                        "history_max_len": (input_volcengine_history_max_len, 'int'),
                        "stream": (switch_volcengine_stream, 'bool'),
                    }
                if config.get("webui", "show_card", "llm", "custom_llm"):
                    config_mapping["custom_llm"] = {
                        "url": (textarea_custom_llm_url, 'str'),
                        "method": (textarea_custom_llm_method, 'str'),
                        "headers": (textarea_custom_llm_headers, 'str'),
                        "proxies": (textarea_custom_llm_proxies, 'str'),
                        "body_type": (select_custom_llm_body_type, 'str'),
                        "body": (textarea_custom_llm_body, 'str'),
                        "resp_data_type": (select_custom_llm_resp_data_type, 'str'),
                        "data_analysis": (textarea_custom_llm_data_analysis, 'str'),
                        "resp_template": (textarea_custom_llm_resp_template, 'str'),
                    }
                if config.get("webui", "show_card", "llm", "llm_tpu"):
                    config_mapping["llm_tpu"] = {
                        "api_ip_port": (input_llm_tpu_api_ip_port, 'str'),
                        "history_enable": (switch_llm_tpu_history_enable, 'bool'),
                        "history_max_len": (input_llm_tpu_history_max_len, 'int'),
                        "max_length": (input_llm_tpu_max_length, 'float'),
                        "temperature": (input_llm_tpu_temperature, 'float'),
                        "top_p": (input_llm_tpu_top_p, 'float'),
                    }

                config_data = update_config(config_mapping, config, config_data, "llm")

            """
            TTS
            """
            if True:
                config_mapping = {}

                if config.get("webui", "show_card", "tts", "edge-tts"):
                    config_mapping["edge-tts"] = {
                        "voice": (select_edge_tts_voice, 'str'),
                        "rate": (input_edge_tts_rate, 'str'),
                        "volume": (input_edge_tts_volume, 'str'),
                        "proxy": (input_edge_tts_proxy, 'str'),
                    }
                if config.get("webui", "show_card", "tts", "vits"):
                    config_mapping["vits"] = {
                        "type": (select_vits_type, 'str'),
                        "config_path": (input_vits_config_path, 'str'),
                        "api_ip_port": (input_vits_api_ip_port, 'str'),
                        "id": (select_vits_id, 'str'),
                        "lang": (select_vits_lang, 'str'),
                        "length": (input_vits_length, 'str'),
                        "noise": (input_vits_noise, 'str'),
                        "noisew": (input_vits_noisew, 'str'),
                        "max": (input_vits_max, 'str'),
                        "format": (input_vits_format, 'str'),
                        "sdp_radio": (input_vits_sdp_radio, 'str'),
                        "gpt_sovits": {
                            "id": (select_vits_gpt_sovits_id, 'str'),
                            "lang": (select_vits_gpt_sovits_lang, 'str'),
                            "format": (input_vits_gpt_sovits_format, 'str'),
                            "segment_size": (input_vits_gpt_sovits_segment_size, 'str'),
                            "reference_audio": (input_vits_gpt_sovits_reference_audio, 'str'),
                            "prompt_text": (input_vits_gpt_sovits_prompt_text, 'str'),
                            "prompt_lang": (select_vits_gpt_sovits_prompt_lang, 'str'),
                            "top_k": (input_vits_gpt_sovits_top_k, 'str'),
                            "top_p": (input_vits_gpt_sovits_top_p, 'str'),
                            "temperature": (input_vits_gpt_sovits_temperature, 'str'),
                            "preset": (input_vits_gpt_sovits_preset, 'str'),
                        }
                    }
                if config.get("webui", "show_card", "tts", "bert_vits2"):
                    config_mapping["bert_vits2"] = {
                        "type": (select_bert_vits2_type, 'str'),
                        "api_ip_port": (input_bert_vits2_api_ip_port, 'str'),
                        "model_id": (input_bert_vits2_model_id, 'int'),
                        "speaker_name": (input_bert_vits2_speaker_name, 'str'),
                        "speaker_id": (input_bert_vits2_speaker_id, 'int'),
                        "language": (select_bert_vits2_language, 'str'),
                        "length": (input_bert_vits2_length, 'int'),
                        "noise": (input_bert_vits2_noise, 'float'),
                        "noisew": (input_bert_vits2_noisew, 'float'),
                        "sdp_radio": (input_bert_vits2_sdp_radio, 'float'),
                        "emotion": (input_bert_vits2_emotion, 'str'),
                        "style_text": (input_bert_vits2_style_text, 'str'),
                        "style_weight": (input_bert_vits2_style_weight, 'float'),
                        "auto_translate": (switch_bert_vits2_auto_translate, 'bool'),
                        "auto_split": (switch_bert_vits2_auto_split, 'bool'),
                        "刘悦-中文特化API": {
                            "api_ip_port": (input_bert_vits2_liuyue_zh_api_api_ip_port, 'str'),
                            "speaker": (input_bert_vits2_liuyue_zh_api_speaker, 'str'),
                            "language": (select_bert_vits2_liuyue_zh_api_language, 'str'),
                            "length_scale": (input_bert_vits2_liuyue_zh_api_length_scale, 'str'),
                            "interval_between_para": (input_bert_vits2_liuyue_zh_api_interval_between_para, 'str'),
                            "interval_between_sent": (input_bert_vits2_liuyue_zh_api_interval_between_sent, 'str'),
                            "noise_scale": (input_bert_vits2_liuyue_zh_api_noise_scale, 'str'),
                            "noise_scale_w": (input_bert_vits2_liuyue_zh_api_noise_scale_w, 'str'),
                            "sdp_radio": (input_bert_vits2_liuyue_zh_api_sdp_radio, 'str'),
                            "emotion": (input_bert_vits2_liuyue_zh_api_emotion, 'str'),
                            "style_text": (input_bert_vits2_liuyue_zh_api_style_text, 'str'),
                            "style_weight": (input_bert_vits2_liuyue_zh_api_style_weight, 'str'),
                            "cut_by_sent": (switch_bert_vits2_cut_by_sent, 'bool'),
                        }
                    }
                if config.get("webui", "show_card", "tts", "vits_fast"):
                    config_mapping["vits_fast"] = {
                        "config_path": (input_vits_fast_config_path, 'str'),
                        "api_ip_port": (input_vits_fast_api_ip_port, 'str'),
                        "character": (input_vits_fast_character, 'str'),
                        "language": (select_vits_fast_language, 'str'),
                        "speed": (input_vits_fast_speed, 'float'),
                    }
                if config.get("webui", "show_card", "tts", "elevenlabs"):
                    config_mapping["elevenlabs"] = {
                        "api_key": (input_elevenlabs_api_key, 'str'),
                        "voice": (input_elevenlabs_voice, 'str'),
                        "model": (input_elevenlabs_model, 'str'),
                    }
                
                if config.get("webui", "show_card", "tts", "openai_tts"):
                    config_mapping["openai_tts"] = {
                        "type": (select_openai_tts_type, 'str'),
                        "api_ip_port": (input_openai_tts_api_ip_port, 'str'),
                        "model": (select_openai_tts_model, 'str'),
                        "voice": (select_openai_tts_voice, 'str'),
                        "api_key": (input_openai_tts_api_key, 'str'),
                    }
                
                if config.get("webui", "show_card", "tts", "gradio_tts"):
                    config_mapping["gradio_tts"] = {
                        "request_parameters": (textarea_gradio_tts_request_parameters, 'str'),
                    }
                if config.get("webui", "show_card", "tts", "gpt_sovits"):
                    config_mapping["gpt_sovits"] = {
                        "type": (select_gpt_sovits_type, 'str'),
                        "gradio_ip_port": (input_gpt_sovits_gradio_ip_port, 'str'),
                        "api_ip_port": (input_gpt_sovits_api_ip_port, 'str'),
                        "ref_audio_path": (input_gpt_sovits_ref_audio_path, 'str'),
                        "prompt_text": (input_gpt_sovits_prompt_text, 'str'),
                        "prompt_language": (select_gpt_sovits_prompt_language, 'str'),
                        "language": (select_gpt_sovits_language, 'str'),
                        "cut": (select_gpt_sovits_cut, 'str'),
                        "gpt_model_path": (input_gpt_sovits_gpt_model_path, 'str'),
                        "sovits_model_path": (input_gpt_sovits_sovits_model_path, 'str'),
                        "api_0322": {
                            "ref_audio_path": (input_gpt_sovits_api_0322_ref_audio_path, 'str'),
                            "prompt_text": (input_gpt_sovits_api_0322_prompt_text, 'str'),
                            "prompt_lang": (select_gpt_sovits_api_0322_prompt_lang, 'str'),
                            "text_lang": (select_gpt_sovits_api_0322_text_lang, 'str'),
                            "text_split_method": (select_gpt_sovits_api_0322_text_split_method, 'str'),
                            "top_k": (input_gpt_sovits_api_0322_top_k, 'int'),
                            "top_p": (input_gpt_sovits_api_0322_top_p, 'float'),
                            "temperature": (input_gpt_sovits_api_0322_temperature, 'float'),
                            "batch_size": (input_gpt_sovits_api_0322_batch_size, 'int'),
                            "speed_factor": (input_gpt_sovits_api_0322_speed_factor, 'float'),
                            "fragment_interval": (input_gpt_sovits_api_0322_fragment_interval, 'str'),
                            "split_bucket": (switch_gpt_sovits_api_0322_split_bucket, 'bool'),
                            "return_fragment": (switch_gpt_sovits_api_0322_return_fragment, 'bool'),
                        },
                        "api_0706": {
                            "refer_wav_path": (input_gpt_sovits_api_0706_refer_wav_path, 'str'),
                            "prompt_text": (input_gpt_sovits_api_0706_prompt_text, 'str'),
                            "prompt_language": (select_gpt_sovits_api_0706_prompt_language, 'str'),
                            "text_language": (select_gpt_sovits_api_0706_text_language, 'str'),
                            "cut_punc": (input_gpt_sovits_api_0706_cut_punc, 'str'),
                        },
                        "v2_api_0821": {
                            "ref_audio_path": (input_gpt_sovits_v2_api_0821_ref_audio_path, 'str'),
                            "prompt_text": (input_gpt_sovits_v2_api_0821_prompt_text, 'str'),
                            "prompt_lang": (select_gpt_sovits_v2_api_0821_prompt_lang, 'str'),
                            "text_lang": (select_gpt_sovits_v2_api_0821_text_lang, 'str'),
                            "text_split_method": (select_gpt_sovits_v2_api_0821_text_split_method, 'str'),
                            "top_k": (input_gpt_sovits_v2_api_0821_top_k, 'int'),
                            "top_p": (input_gpt_sovits_v2_api_0821_top_p, 'float'),
                            "temperature": (input_gpt_sovits_v2_api_0821_temperature, 'float'),
                            "batch_size": (input_gpt_sovits_v2_api_0821_batch_size, 'int'),
                            "batch_threshold": (input_gpt_sovits_v2_api_0821_batch_threshold, 'float'),
                            "split_bucket": (switch_gpt_sovits_v2_api_0821_split_bucket, 'bool'),
                            "speed_factor": (input_gpt_sovits_v2_api_0821_speed_factor, 'float'),
                            "fragment_interval": (input_gpt_sovits_v2_api_0821_fragment_interval, 'float'),
                            "seed": (input_gpt_sovits_v2_api_0821_seed, 'int'),
                            "media_type": (input_gpt_sovits_v2_api_0821_media_type, 'str'),
                            "parallel_infer": (switch_gpt_sovits_v2_api_0821_parallel_infer, 'bool'),
                            "repetition_penalty": (input_gpt_sovits_v2_api_0821_repetition_penalty, 'float'),
                        },
                        "webtts": {
                            "version": (select_gpt_sovits_webtts_version, 'str'),
                            "api_ip_port": (input_gpt_sovits_webtts_api_ip_port, 'str'),
                            "spk": (input_gpt_sovits_webtts_spk, 'str'),
                            "lang": (select_gpt_sovits_webtts_lang, 'str'),
                            "speed": (input_gpt_sovits_webtts_speed, 'str'),
                            "emotion": (input_gpt_sovits_webtts_emotion, 'str'),
                        }
                    }

                if config.get("webui", "show_card", "tts", "azure_tts"):
                    config_mapping["azure_tts"] = {
                        "subscription_key": (input_azure_tts_subscription_key, 'str'),
                        "region": (input_azure_tts_region, 'str'),
                        "voice_name": (input_azure_tts_voice_name, 'str'),
                    }
                if config.get("webui", "show_card", "tts", "cosyvoice"):
                    config_mapping["cosyvoice"] = {
                        "type": (select_cosyvoice_type, 'str'),
                        "gradio_ip_port": (input_cosyvoice_gradio_ip_port, 'str'),
                        "api_ip_port": (input_cosyvoice_api_ip_port, 'str'),
                        "gradio_0707": {
                            "mode_checkbox_group": (select_cosyvoice_gradio_0707_mode_checkbox_group, 'str'),
                            "sft_dropdown": (select_cosyvoice_gradio_0707_sft_dropdown, 'str'),
                            "prompt_text": (input_cosyvoice_gradio_0707_prompt_text, 'str'),
                            "prompt_wav_upload": (input_cosyvoice_gradio_0707_prompt_wav_upload, 'str'),
                            "instruct_text": (input_cosyvoice_gradio_0707_instruct_text, 'str'),
                            "seed": (input_cosyvoice_gradio_0707_seed, 'int'),
                        },
                        "api_0819": {
                            "speaker": (input_cosyvoice_api_0819_speaker, 'str'),
                            "new": (input_cosyvoice_api_0819_new, 'int'),
                            "speed": (input_cosyvoice_api_0819_speed, 'float'),
                        },
                    }
                if config.get("webui", "show_card", "tts", "f5_tts"):
                    config_mapping["f5_tts"] = {
                        "type": (select_f5_tts_type, 'str'),
                        "gradio_ip_port": (input_f5_tts_gradio_ip_port, 'str'),
                        "ref_audio_orig": (input_f5_tts_ref_audio_orig, 'str'),
                        "ref_text": (input_f5_tts_ref_text, 'str'),
                        "model": (select_f5_tts_model, 'str'),
                        "remove_silence": (switch_f5_tts_remove_silence, 'bool'),
                        "cross_fade_duration": (input_f5_tts_cross_fade_duration, 'float'),
                        "speed": (input_f5_tts_speed, 'float'),
                    }
                if config.get("webui", "show_card", "tts", "multitts"):
                    config_mapping["multitts"] = {
                        "api_ip_port": (input_multitts_api_ip_port, 'str'),
                        "speed": (input_multitts_speed, 'int'),
                        "volume": (input_multitts_volume, 'int'),
                        "pitch": (input_multitts_pitch, 'int'),
                        "voice": (input_multitts_voice, 'str'),
                    }
                if config.get("webui", "show_card", "tts", "melotts"):
                    config_mapping["melotts"] = {
                        "api_ip_port": (input_melotts_api_ip_port, 'str'),
                        "language": (input_melotts_language, 'str'),
                        "device": (select_melotts_device, 'str'),
                        "use_hf": (switch_melotts_use_hf, 'bool'),
                        "config_path": (input_melotts_config_path, 'str'),
                        "ckpt_path": (input_melotts_ckpt_path, 'str'),
                        "speaker_id": (input_melotts_speaker_id, 'int'),
                        "sdp_ratio": (input_melotts_sdp_ratio, 'float'),
                        "noise_scale": (input_melotts_noise_scale, 'float'),
                        "noise_scale_w": (input_melotts_noise_scale_w, 'float'),
                        "speed": (input_melotts_speed, 'float'),
                    }
                if config.get("webui", "show_card", "tts", "index_tts"):
                    config_mapping["index_tts"] = {
                        "api_ip_port": (input_index_tts_api_ip_port, 'str'),
                        "prompt_audio": (input_index_tts_prompt_audio, 'str'),
                        "temperature": (input_index_tts_temperature, 'float'),
                    }

                config_data = update_config(config_mapping, config, config_data, "tts")

            """
            SVC
            """
            if True:
                config_mapping = {}
                if config.get("webui", "show_card", "svc", "ddsp_svc"):
                    config_mapping["ddsp_svc"] = {
                        "enable": (switch_ddsp_svc_enable, 'bool'),
                        "config_path": (input_ddsp_svc_config_path, 'str'),
                        "api_ip_port": (input_ddsp_svc_api_ip_port, 'str'),
                        "fSafePrefixPadLength": (input_ddsp_svc_fSafePrefixPadLength, 'float'),
                        "fPitchChange": (input_ddsp_svc_fPitchChange, 'float'),
                        "sSpeakId": (input_ddsp_svc_sSpeakId, 'int'),
                        "sampleRate": (input_ddsp_svc_sampleRate, 'int'),
                    }
                if config.get("webui", "show_card", "svc", "so_vits_svc"):  
                    config_mapping["so_vits_svc"] = {
                        "enable": (switch_so_vits_svc_enable, 'bool'),
                        "config_path": (input_so_vits_svc_config_path, 'str'),
                        "api_ip_port": (input_so_vits_svc_api_ip_port, 'str'),
                        "spk": (input_so_vits_svc_spk, 'str'),
                        "tran": (input_so_vits_svc_tran, 'float'),
                        "wav_format": (input_so_vits_svc_wav_format, 'str'),
                    }

                config_data = update_config(config_mapping, config, config_data, "svc")
                  
            """
            Virtual Body
            """
            if True:
                config_mapping = {}
                if config.get("webui", "show_card", "visual_body", "live2d"):  
                    config_mapping["live2d"] = {
                        "enable": (switch_live2d_enable, 'bool'),
                        "port": (input_live2d_port, 'int'),
                        "name": (select_live2d_name, 'str'),
                    }
                if config.get("webui", "show_card", "visual_body", "live2d_TTS_LLM_GPT_SoVITS_Vtuber"):  
                    config_mapping["live2d_TTS_LLM_GPT_SoVITS_Vtuber"] = {
                        "api_ip_port": (input_live2d_TTS_LLM_GPT_SoVITS_Vtuber_api_ip_port, 'str'),
                    } 
                if config.get("webui", "show_card", "visual_body", "xuniren"):  
                    config_mapping["xuniren"] = {
                        "api_ip_port": (input_xuniren_api_ip_port, 'str'),
                    } 
                if config.get("webui", "show_card", "visual_body", "metahuman_stream"):  
                    config_mapping["metahuman_stream"] = {
                        "type": (select_metahuman_stream_type, 'str'),
                        "api_ip_port": (input_metahuman_stream_api_ip_port, 'str'),
                    } 
                if config.get("webui", "show_card", "visual_body", "unity"):  
                    config_mapping["unity"] = {
                        "api_ip_port": (input_unity_api_ip_port, 'str'),
                        "password": (input_unity_password, 'str'),
                    } 
                if config.get("webui", "show_card", "visual_body", "EasyAIVtuber"):  
                    config_mapping["EasyAIVtuber"] = {
                        "api_ip_port": (input_EasyAIVtuber_api_ip_port, 'str'),
                    } 
                if config.get("webui", "show_card", "visual_body", "digital_human_video_player"):  
                    config_mapping["digital_human_video_player"] = {
                        "type": (select_digital_human_video_player_type, 'str'),
                        "api_ip_port": (input_digital_human_video_player_api_ip_port, 'str'),
                    }         
                
                config_data = update_config(config_mapping, config, config_data, None)

                if config.get("webui", "show_card", "visual_body", "live2d"):
                    tmp_str = f"var model_name = \"{select_live2d_name.value}\";"
                    # The path is hard-coded, be careful
                    common.write_content_to_file("Live2D/js/model_name.js", tmp_str)

                
            """
            Copywriting
            """
            if True:
                config_data["copywriting"]["auto_play"] = switch_copywriting_auto_play.value
                config_data["copywriting"]["random_play"] = switch_copywriting_random_play.value
                config_data["copywriting"]["audio_interval"] = input_copywriting_audio_interval.value
                config_data["copywriting"]["switching_interval"] = input_copywriting_switching_interval.value
                config_data["copywriting"]["text_path"] = input_copywriting_text_path.value
                config_data["copywriting"]["audio_save_path"] = input_copywriting_audio_save_path.value
                config_data["copywriting"]["audio_synthesis_type"] = select_copywriting_audio_synthesis_type.value
                
                tmp_arr = []
                # logger.info(copywriting_config_var)
                for index in range(len(copywriting_config_var) // 5):
                    tmp_json = {
                        "file_path": "",
                        "audio_path": "",
                        "continuous_play_num": 1,
                        "max_play_time": 10.0,
                        "play_list": []
                    }
                    tmp_json["file_path"] = copywriting_config_var[str(5 * index)].value
                    tmp_json["audio_path"] = copywriting_config_var[str(5 * index + 1)].value
                    tmp_json["continuous_play_num"] = int(copywriting_config_var[str(5 * index + 2)].value)
                    tmp_json["max_play_time"] = float(copywriting_config_var[str(5 * index + 3)].value)
                    tmp_json["play_list"] = common_textarea_handle(copywriting_config_var[str(5 * index + 4)].value)
                    

                    tmp_arr.append(tmp_json)
                # logger.info(tmp_arr)
                config_data["copywriting"]["config"] = tmp_arr

            """
            Points
            """
            if True:
                config_data["integral"]["enable"] = switch_integral_enable.value

                config_data["integral"]["sign"]["enable"] = switch_integral_sign_enable.value
                config_data["integral"]["sign"]["get_integral"] = int(input_integral_sign_get_integral.value)
                config_data["integral"]["sign"]["cmd"] = common_textarea_handle(textarea_integral_sign_cmd.value)
                tmp_arr = []
                # logger.info(integral_sign_copywriting_var)
                for index in range(len(integral_sign_copywriting_var) // 2):
                    tmp_json = {
                        "sign_num_interval": "",
                        "copywriting": []
                    }
                    tmp_json["sign_num_interval"] = integral_sign_copywriting_var[str(2 * index)].value
                    tmp_json["copywriting"] = common_textarea_handle(integral_sign_copywriting_var[str(2 * index + 1)].value)

                    tmp_arr.append(tmp_json)
                # logger.info(tmp_arr)
                config_data["integral"]["sign"]["copywriting"] = tmp_arr

                config_data["integral"]["gift"]["enable"] = switch_integral_gift_enable.value
                config_data["integral"]["gift"]["get_integral_proportion"] = float(input_integral_gift_get_integral_proportion.value)
                tmp_arr = []
                for index in range(len(integral_gift_copywriting_var) // 2):
                    tmp_json = {
                        "gift_price_interval": "",
                        "copywriting": []
                    }
                    tmp_json["gift_price_interval"] = integral_gift_copywriting_var[str(2 * index)].value
                    tmp_json["copywriting"] = common_textarea_handle(integral_gift_copywriting_var[str(2 * index + 1)].value)

                    tmp_arr.append(tmp_json)
                # logger.info(tmp_arr)
                config_data["integral"]["gift"]["copywriting"] = tmp_arr

                config_data["integral"]["entrance"]["enable"] = switch_integral_entrance_enable.value
                config_data["integral"]["entrance"]["get_integral"] = int(input_integral_entrance_get_integral.value)
                tmp_arr = []
                for index in range(len(integral_entrance_copywriting_var) // 2):
                    tmp_json = {
                        "entrance_num_interval": "",
                        "copywriting": []
                    }
                    tmp_json["entrance_num_interval"] = integral_entrance_copywriting_var[str(2 * index)].value
                    tmp_json["copywriting"] = common_textarea_handle(integral_entrance_copywriting_var[str(2 * index + 1)].value)

                    tmp_arr.append(tmp_json)
                # logger.info(tmp_arr)
                config_data["integral"]["entrance"]["copywriting"] = tmp_arr

                config_data["integral"]["crud"]["query"]["enable"] = switch_integral_crud_query_enable.value
                config_data["integral"]["crud"]["query"]["cmd"] = common_textarea_handle(textarea_integral_crud_query_cmd.value)
                config_data["integral"]["crud"]["query"]["copywriting"] = common_textarea_handle(textarea_integral_crud_query_copywriting.value)

            """
            Chat
            """
            if True:
                tmp_arr = []
                for index in range(len(talk_interrupt_clean_type_var)):
                    if talk_interrupt_clean_type_var[str(index)].value:
                        tmp_arr.append(
                            common.find_keys_by_value(
                                talk_interrupt_clean_type_mapping, 
                                talk_interrupt_clean_type_var[str(index)].text
                            )[0]
                        )
                # logger.info(tmp_arr)
                config_data["talk"]["interrupt_talk"]["clean_type"] = tmp_arr

                config_mapping = {
                    "talk": {
                        "key_listener_enable": (switch_talk_key_listener_enable, 'bool'),
                        "direct_run_talk": (switch_talk_direct_run_talk, 'bool'),
                        "device_index": (select_talk_device_index, 'str'),
                        "no_recording_during_playback": (switch_talk_no_recording_during_playback, 'bool'),
                        "no_recording_during_playback_sleep_interval": (input_talk_no_recording_during_playback_sleep_interval, 'float'),
                        "username": (input_talk_username, 'str'),
                        "continuous_talk": (switch_talk_continuous_talk, 'bool'),
                        "trigger_key": (select_talk_trigger_key, 'str'),
                        "stop_trigger_key": (select_talk_stop_trigger_key, 'str'),
                        "volume_threshold": (input_talk_volume_threshold, 'float'),
                        "silence_threshold": (input_talk_silence_threshold, 'float'),
                        "CHANNELS": (input_talk_silence_CHANNELS, 'int'),
                        "RATE": (input_talk_silence_RATE, 'int'),
                        "show_chat_log": (switch_talk_show_chat_log, 'bool'),
                        "interrupt_talk": {
                            "enable": (switch_talk_interrupt_talk_enable, 'bool'),
                            "keywords": (textarea_talk_interrupt_talk_keywords, 'textarea'),
                        },
                        "wakeup_sleep": {
                            "enable": (switch_talk_wakeup_sleep_enable, 'bool'),
                            "mode": (select_talk_wakeup_sleep_mode, 'str'),
                            "wakeup_word": (textarea_talk_wakeup_sleep_wakeup_word, 'textarea'),
                            "sleep_word": (textarea_talk_wakeup_sleep_sleep_word, 'textarea'),
                            "wakeup_copywriting": (textarea_talk_wakeup_sleep_wakeup_copywriting, 'textarea'),
                            "sleep_copywriting": (textarea_talk_wakeup_sleep_sleep_copywriting, 'textarea'),
                        },
                        "type": (select_talk_type, 'str'),
                        "google": {
                            "tgt_lang": (select_talk_google_tgt_lang, 'str'),
                        },
                        "baidu": {
                            "app_id": (input_talk_baidu_app_id, 'str'),
                            "api_key": (input_talk_baidu_api_key, 'str'),
                            "secret_key": (input_talk_baidu_secret_key, 'str'),
                        },
                        "faster_whisper": {
                            "model_size": (input_faster_whisper_model_size, 'str'),
                            "language": (select_faster_whisper_language, 'str'),
                            "device": (select_faster_whisper_device, 'str'),
                            "compute_type": (select_faster_whisper_compute_type, 'str'),
                            "download_root": (input_faster_whisper_download_root, 'str'),
                            "beam_size": (input_faster_whisper_beam_size, 'int'),
                        },
                        "sensevoice": {
                            "asr_model_path": (input_sensevoice_asr_model_path, 'str'),
                            "vad_model_path": (input_sensevoice_vad_model_path, 'str'),
                            "vad_max_single_segment_time": (input_sensevoice_vad_max_single_segment_time, 'int'),
                            "device": (input_sensevoice_vad_device, 'str'),
                            "language": (select_sensevoice_language, 'str'),
                            "text_norm": (input_sensevoice_text_norm, 'str'),
                            "batch_size_s": (input_sensevoice_batch_size_s, 'int'),
                            "batch_size": (input_sensevoice_batch_size, 'int'),
                        },
                    }
                }

                config_data = update_config(config_mapping, config, config_data, None)

            """
            Image Recognition
            """
            if True:
                config_mapping = {
                    "image_recognition": {
                        "enable": (button_image_recognition_enable, 'bool'),
                        "model": (select_image_recognition_model, 'str'),
                        "img_save_path": (input_image_recognition_img_save_path, 'str'),
                        "prompt": (input_image_recognition_prompt, 'str'),
                        "screenshot_window_title": (select_image_recognition_screenshot_window_title, 'str'),
                        "screenshot_delay": (input_image_recognition_screenshot_delay, 'float'),
                        "loop_screenshot_enable": (switch_image_recognition_loop_screenshot_enable, 'bool'),
                        "loop_screenshot_delay": (input_image_recognition_loop_screenshot_delay, 'int'),
                        "cam_screenshot_enable": (switch_image_recognition_cam_screenshot_enable, 'bool'),
                        "cam_index": (select_image_recognition_cam_index, 'int'), 
                        "cam_screenshot_delay": (input_image_recognition_cam_screenshot_delay, 'float'),
                        "loop_cam_screenshot_enable": (switch_image_recognition_loop_cam_screenshot_enable, 'bool'),
                        "loop_cam_screenshot_delay": (input_image_recognition_loop_cam_screenshot_delay, 'int'),
                        "gemini": {
                            "model": (select_image_recognition_gemini_model, 'str'),
                            "api_key": (input_image_recognition_gemini_api_key, 'str'),
                            "http_proxy": (input_image_recognition_gemini_http_proxy, 'str'),
                            "https_proxy": (input_image_recognition_gemini_https_proxy, 'str'),
                        },
                        "zhipu": {
                            "model": (select_image_recognition_zhipu_model, 'str'),
                            "api_key": (input_image_recognition_zhipu_api_key, 'str'),
                        },
                    }
                }


                config_data = update_config(config_mapping, config, config_data, None)

            """
            Assistant Streamer
            """
            if True:
                
                tmp_arr = []
                for index in range(len(assistant_anchor_type_var)):
                    if assistant_anchor_type_var[str(index)].value:
                        tmp_arr.append(common.find_keys_by_value(assistant_anchor_type_mapping, assistant_anchor_type_var[str(index)].text)[0])
                # logger.info(tmp_arr)
                config_data["assistant_anchor"]["type"] = tmp_arr

                config_mapping = {
                    "assistant_anchor": {
                        "enable": (switch_assistant_anchor_enable, 'bool'),
                        "username": (input_assistant_anchor_username, 'str'),
                        "audio_synthesis_type": (select_assistant_anchor_audio_synthesis_type, 'str'),
                        "local_qa": {
                            "text": {
                                "enable": (switch_assistant_anchor_local_qa_text_enable, 'bool'),
                                "format": (select_assistant_anchor_local_qa_text_format, 'str'),
                                "file_path": (input_assistant_anchor_local_qa_text_file_path, 'str'),
                                "similarity": (input_assistant_anchor_local_qa_text_similarity, 'float')
                            },
                            "audio": {
                                "enable": (switch_assistant_anchor_local_qa_audio_enable, 'bool'),
                                "type": (select_assistant_anchor_local_qa_audio_type, 'str'),
                                "file_path": (input_assistant_anchor_local_qa_audio_file_path, 'str'),
                                "similarity": (input_assistant_anchor_local_qa_audio_similarity, 'float')
                            }
                        }
                    }
                }

                config_data = update_config(config_mapping, config, config_data, None)

            """
            Translation
            """
            if True:
                config_mapping = {
                    "translate": {
                        "enable": (switch_translate_enable, 'bool'),
                        "type": (select_translate_type, 'str'),
                        "trans_type": (select_translate_trans_type, 'str'),
                        "baidu": {
                            "appid": (input_translate_baidu_appid, 'str'),
                            "appkey": (input_translate_baidu_appkey, 'str'),
                            "from_lang": (select_translate_baidu_from_lang, 'str'),
                            "to_lang": (select_translate_baidu_to_lang, 'str'),
                        },
                        "google": {
                            "proxy": (input_translate_google_proxy, 'str'),
                            "src_lang": (select_translate_google_src_lang, 'str'),
                            "tgt_lang": (select_translate_google_tgt_lang, 'str'),
                        },
                    }
                }

                config_data = update_config(config_mapping, config, config_data, None)

            """
            Serial port
            """
            if True:
                tmp_arr = []
                for index in range(len(serial_config_var) // 8):
                    tmp_json = {
                        "serial_name": "COM1",
                        "baudrate": "115200",
                        "serial_data_type": "ASCII"
                    }
                    tmp_json["serial_name"] = serial_config_var[str(8 * index)].value
                    tmp_json["baudrate"] = serial_config_var[str(8 * index + 1)].value
                    tmp_json["serial_data_type"] = serial_config_var[str(8 * index + 5)].value

                    tmp_arr.append(tmp_json)
                # logger.info(tmp_arr)
                config_data["serial"]["config"] = tmp_arr

            """
            Data Analysis
            """
            if True:
                config_mapping = {
                    "data_analysis": {
                        "comment_word_cloud": {
                            "top_num": (input_data_analysis_comment_word_cloud_top_num, 'int'),
                        },
                        "integral": {
                            "top_num": (input_data_analysis_integral_top_num, 'int'),
                        },
                        "gift": {
                            "top_num": (input_data_analysis_gift_top_num, 'int'),
                        },
                    }
                }
                config_data = update_config(config_mapping, config, config_data, None)

            """
            UI config
            """
            if True:
                config_mapping = {
                    "webui": {
                        "title": (input_webui_title, 'str'),
                        "ip": (input_webui_ip, 'str'),
                        "port": (input_webui_port, 'int'),
                        "auto_run": (switch_webui_auto_run, 'bool'),
                        "local_dir_to_endpoint": {
                            "enable": (switch_webui_local_dir_to_endpoint_enable, 'bool'),
                        },
                        "show_card": {
                            "common_config": {
                                "read_comment": (switch_webui_show_card_common_config_read_comment, 'bool'),
                                "filter": (switch_webui_show_card_common_config_filter, 'bool'),
                                "thanks": (switch_webui_show_card_common_config_thanks, 'bool'),
                                "local_qa": (switch_webui_show_card_common_config_local_qa, 'bool'),
                                "choose_song": (switch_webui_show_card_common_config_choose_song, 'bool'),
                                "sd": (switch_webui_show_card_common_config_sd, 'bool'),
                                "log": (switch_webui_show_card_common_config_log, 'bool'),
                                "schedule": (switch_webui_show_card_common_config_schedule, 'bool'),
                                "idle_time_task": (switch_webui_show_card_common_config_idle_time_task, 'bool'),
                                "trends_copywriting": (switch_webui_show_card_common_config_trends_copywriting, 'bool'),
                                "database": (switch_webui_show_card_common_config_database, 'bool'),
                                "play_audio": (switch_webui_show_card_common_config_play_audio, 'bool'),
                                "web_captions_printer": (switch_webui_show_card_common_config_web_captions_printer, 'bool'),
                                "key_mapping": (switch_webui_show_card_common_config_key_mapping, 'bool'),
                                "custom_cmd": (switch_webui_show_card_common_config_custom_cmd, 'bool'),
                                "trends_config": (switch_webui_show_card_common_config_trends_config, 'bool'),
                                "abnormal_alarm": (switch_webui_show_card_common_config_abnormal_alarm, 'bool'),
                                "coordination_program": (switch_webui_show_card_common_config_coordination_program, 'bool'),
                            },
                            "llm": {
                                "chatgpt": (switch_webui_show_card_llm_chatgpt, 'bool'),
                                "zhipu": (switch_webui_show_card_llm_zhipu, 'bool'),
                                "chat_with_file": (switch_webui_show_card_llm_chat_with_file, 'bool'),
                                "langchain_chatchat": (switch_webui_show_card_llm_langchain_chatchat, 'bool'),
                                "chatterbot": (switch_webui_show_card_llm_chatterbot, 'bool'),
                                "text_generation_webui": (switch_webui_show_card_llm_text_generation_webui, 'bool'),
                                "sparkdesk": (switch_webui_show_card_llm_sparkdesk, 'bool'),
                                "bard": (switch_webui_show_card_llm_bard, 'bool'),
                                "tongyi": (switch_webui_show_card_llm_tongyi, 'bool'),
                                "tongyixingchen": (switch_webui_show_card_llm_tongyixingchen, 'bool'),
                                "my_wenxinworkshop": (switch_webui_show_card_llm_my_wenxinworkshop, 'bool'),
                                "gemini": (switch_webui_show_card_llm_gemini, 'bool'),
                                "koboldcpp": (switch_webui_show_card_llm_koboldcpp, 'bool'),
                                "anythingllm": (switch_webui_show_card_llm_anythingllm, 'bool'),
                                "gpt4free": (switch_webui_show_card_llm_gpt4free, 'bool'),
                                "custom_llm": (switch_webui_show_card_llm_custom_llm, 'bool'),
                                "llm_tpu": (switch_webui_show_card_llm_llm_tpu, 'bool'),
                                "dify": (switch_webui_show_card_llm_dify, 'bool'),
                                "volcengine": (switch_webui_show_card_llm_volcengine, 'bool'),
                            },
                            "tts": {
                                "edge-tts": (switch_webui_show_card_tts_edge_tts, 'bool'),
                                "vits": (switch_webui_show_card_tts_vits, 'bool'),
                                "bert_vits2": (switch_webui_show_card_tts_bert_vits2, 'bool'),
                                "vits_fast": (switch_webui_show_card_tts_vits_fast, 'bool'),
                                "elevenlabs": (switch_webui_show_card_tts_elevenlabs, 'bool'),
                                "openai_tts": (switch_webui_show_card_tts_openai_tts, 'bool'),
                                "gradio_tts": (switch_webui_show_card_tts_gradio_tts, 'bool'),
                                "gpt_sovits": (switch_webui_show_card_tts_gpt_sovits, 'bool'),
                                "azure_tts": (switch_webui_show_card_tts_azure_tts, 'bool'),
                                "cosyvoice": (switch_webui_show_card_tts_cosyvoice, 'bool'),
                                "f5_tts": (switch_webui_show_card_tts_f5_tts, 'bool'),
                                "multitts": (switch_webui_show_card_tts_multitts, 'bool'),
                                "melotts": (switch_webui_show_card_tts_melotts, 'bool'),
                                "index_tts": (switch_webui_show_card_tts_index_tts, 'bool'),
                            },
                            "svc": {
                                "ddsp_svc": (switch_webui_show_card_svc_ddsp_svc, 'bool'),
                                "so_vits_svc": (switch_webui_show_card_svc_so_vits_svc, 'bool'),
                            },
                            "visual_body": {
                                "live2d": (switch_webui_show_card_visual_body_live2d, 'bool'),
                                "xuniren": (switch_webui_show_card_visual_body_xuniren, 'bool'),
                                "metahuman_stream": (switch_webui_show_card_visual_body_metahuman_stream, 'bool'),
                                "unity": (switch_webui_show_card_visual_body_unity, 'bool'),
                                "EasyAIVtuber": (switch_webui_show_card_visual_body_EasyAIVtuber, 'bool'),
                                "digital_human_video_player": (switch_webui_show_card_visual_body_digital_human_video_player, 'bool'),
                                "live2d_TTS_LLM_GPT_SoVITS_Vtuber": (switch_webui_show_card_visual_body_live2d_TTS_LLM_GPT_SoVITS_Vtuber, 'bool'),
                            },
                        },
                        "theme": {
                            "choose": (select_webui_theme_choose, 'str'),
                        },
                    },
                    "login": {
                        "enable": (switch_login_enable, 'bool'),
                        "username": (input_login_username, 'str'),
                        "password": (input_login_password, 'str'),
                    }
                }

                config_data = update_config(config_mapping, config, config_data, None)

                tmp_arr = []
                for index in range(len(webui_local_dir_to_endpoint_config_var) // 2):
                    tmp_json = {
                        "url_path": "",
                        "local_dir": ""
                    }
                    tmp_json["url_path"] = webui_local_dir_to_endpoint_config_var[str(2 * index)].value
                    tmp_json["local_dir"] = webui_local_dir_to_endpoint_config_var[str(2 * index + 1)].value

                    tmp_arr.append(tmp_json)
                # logger.info(tmp_arr)
                config_data["webui"]["local_dir_to_endpoint"]["config"] = tmp_arr

                
            return config_data
        except Exception as e:
            logger.error(f"Unable to read the webui config into variables!\n{e}")
            ui.notify(position="top", type="negative", message=f"Unable to read the webui config into variables!\n{e}")
            logger.error(traceback.format_exc())

            return None

    # Save configuration
    def save_config():
        """
        Save the config to the local config file
        """
        global config, config_path

        # Config check
        if not check_config():
            return False

        try:
            with open(config_path, 'r', encoding="utf-8") as config_file:
                config_data = json.load(config_file)
        except Exception as e:
            logger.error(f"Unable to read the config file!\n{e}")
            ui.notify(position="top", type="negative", message=f"Unable to read the config file!{e}")
            return False

        # Read the webui config into the dict variable
        config_data = webui_config_to_dict(config_data)
        if config_data is None:
            return False

        # Write the local Q&A json data to a file
        if config.get("webui", "show_card", "common_config", "local_qa"):
            try:
                ret = common.write_content_to_file(input_local_qa_text_json_file_path.value, textarea_local_qa_text_json_file_content.value, write_log=False)
                if not ret:
                    ui.notify(position="top", type="negative", message="Unable to write the local Q&A json data to a file!\nSee the log for detailed errors")
                    return False
            except Exception as e:
                logger.error(f"Unable to write the local Q&A json data to a file!\n{str(e)}")
                ui.notify(position="top", type="negative", message=f"Unable to write the local Q&A json data to a file!\n{str(e)}")
                return False   

        # Write the config to the config file
        try:
            with open(config_path, 'w', encoding="utf-8") as config_file:
                json.dump(config_data, config_file, indent=2, ensure_ascii=False)
                config_file.flush()  # Flush the buffer to make sure the write takes effect immediately

            logger.info("Config data was written to the file successfully!")
            ui.notify(position="top", type="positive", message="Config data was written to the file successfully!")

            return True
        except Exception as e:
            logger.error(f"Unable to write the config file!\n{str(e)}")
            ui.notify(position="top", type="negative", message=f"Unable to write the config file!\n{str(e)}")
            return False
        


    """

    ..............................................................................................................
    ..............................................................................................................
    ..........................,]].................................................................................
    .........................O@@@@^...............................................................................
    .....=@@@@@`.....O@@@....,\@@[.....................................,@@@@@@@@@@]....O@@@^......=@@@@....O@@@^..
    .....=@@@@@@.....O@@@............................................=@@@@/`..,[@@/....O@@@^......=@@@@....O@@@^..
    .....=@@@@@@@....O@@@....,]]]].......]@@@@@]`.....,/@@@@\`....../@@@@..............O@@@^......=@@@@....O@@@^..
    .....=@@@/@@@\...O@@@....=@@@@....,@@@@@@@@@@^..,@@@@@@@@@@\...=@@@@...............O@@@^......=@@@@....O@@@^..
    .....=@@@^,@@@\..O@@@....=@@@@...,@@@@`........=@@@/....=@@@\..=@@@@....]]]]]]]]...O@@@^......=@@@@....O@@@^..
    .....=@@@^.=@@@^.O@@@....=@@@@...O@@@^.........@@@@......@@@@..=@@@@....=@@@@@@@...O@@@^......=@@@@....O@@@^..
    .....=@@@^..\@@@^=@@@....=@@@@...@@@@^........,@@@@@@@@@@@@@@..=@@@@.......=@@@@...O@@@^......=@@@@....O@@@^..
    .....=@@@^...\@@@/@@@....=@@@@...O@@@^.........@@@@`...........,@@@@`......=@@@@...O@@@^......=@@@@....O@@@^..
    .....=@@@^....@@@@@@@....=@@@@...,@@@@`........=@@@@......,.....=@@@@`.....=@@@@...=@@@@`.....@@@@^....O@@@^..
    .....=@@@^....,@@@@@@....=@@@@....,@@@@@@@@@@`..=@@@@@@@@@@@`....,@@@@@@@@@@@@@@....,@@@@@@@@@@@@`.....O@@@^..
    .....,[[[`.....,[[[[[....,[[[[.......[@@@@@[`.....,[@@@@@[`.........,\@@@@@@[`.........[@@@@@@[........[[[[`..
    ..............................................................................................................
    ..............................................................................................................

    """

    # All speech synthesis options
    audio_synthesis_type_options = {
        'none': 'Disabled', 
        'edge-tts': 'Edge-TTS', 
        'vieneu': 'VieNeu-TTS (free, local, Vietnamese)',
        'vits': 'VITS', 
        'bert_vits2': 'bert_vits2',
        'vits_fast': 'VITS-Fast', 
        'elevenlabs': 'elevenlabs',
        'openai_tts': 'OpenAI TTS',
        'gradio_tts': 'Gradio',
        'gpt_sovits': 'GPT_SoVITS',
        'azure_tts': 'azure_tts',
        'cosyvoice': 'CosyVoice',
        'f5_tts': 'F5-TTS',
        'multitts': 'MultiTTS',
        'melotts': 'MeloTTS',
        'index_tts': 'Index-TTS',
    }

    # All chat type options
    chat_type_options = {
        'none': 'Disabled', 
        'reread': 'Repeater', 
        'chatgpt': 'ChatGPT/Wenda', 
        'chat_with_file': 'chat_with_file',
        'chatterbot': 'Chatterbot',
        'text_generation_webui': 'text_generation_webui',
        'sparkdesk': 'iFlytek Spark',
        'langchain_chatchat': 'langchain_chatchat',
        'zhipu': 'Zhipu AI',
        'bard': 'Bard',
        'tongyixingchen': 'Tongyi Xingchen',
        'my_wenxinworkshop': 'Qianfan',
        'gemini': 'Gemini',
        'koboldcpp': 'koboldcpp',
        'anythingllm': 'AnythingLLM',
        'tongyi': 'Tongyi Qianwen / Alibaba Cloud Bailian',
        'gpt4free': 'GPT4Free',
        'dify': 'Dify',
        'volcengine': 'Volcengine',
        'llm_tpu': 'LLM_TPU',
        'custom_llm': 'Custom LLM',
    }

    platform_options = {
        'talk': 'Chat Mode',
        'tiktok': 'TikTok LIVE',
        'youtube': 'YouTube',
        'twitch': 'Twitch',
    }

    visual_body_options = {
        'Other': 'Other (external)',
        'metahuman_stream': 'metahuman_stream', 
        'EasyAIVtuber': 'EasyAIVtuber', 
        'digital_human_video_player': 'Digital Human Video Player', 
        'live2d_TTS_LLM_GPT_SoVITS_Vtuber': 'live2d-TTS-LLM-GPT-SoVITS-Vtuber',
        'xuniren': 'xuniren', 
    }

    with ui.tabs().classes('lv-hidden-tabs') as tabs:
        home_page = ui.tab('Home')
        setup_page = ui.tab('Setup')
        common_config_page = ui.tab('Common Config')
        llm_page = ui.tab('Large Language Model')
        tts_page = ui.tab('Text-to-Speech')
        svc_page = ui.tab('Voice Changer')
        visual_body_page = ui.tab('Virtual Body')
        copywriting_page = ui.tab('Copywriting')
        products_page = ui.tab('Products')
        voice_page = ui.tab('Voice')
        dashboard_page = ui.tab('Dashboard')
        tools_page = ui.tab('Live tools')
        teach_page = ui.tab('Teach')
        schedule_page = ui.tab('Schedule')
        novel_page = ui.tab('Novel reader')
        writer_page = ui.tab('Novel writer')
        avatar_page = ui.tab('Avatar studio')
        story_page = ui.tab('Story studio')
        talk_page = ui.tab('Chat')
        image_recognition_page = ui.tab('Image Recognition')
        integral_page = ui.tab('Points')
        assistant_anchor_page = ui.tab('Assistant Streamer')
        translate_page = ui.tab('Translation')
        serial_page = ui.tab('Serial port')
        data_analysis_page = ui.tab('Data Analysis')
        web_page = ui.tab('Page Config')
        docs_page = ui.tab('Docs & Tutorials')
        about_page = ui.tab('About')

    def studio_status():
        from utils.webui_setup import PM as _PM
        api_ok = port_open(config.get("api_port"))
        bridge = _PM.running("bridge")
        engine = config.get("audio_synthesis_type") or "edge-tts"
        voice_txt = {"edge-tts": "Voice: Edge", "vieneu": "Voice: VieNeu"}.get(engine, f"Voice: {engine}")
        return {"app": ("Streamer online" if api_ok else "Streamer offline", api_ok),
                "bridge": ("LIVE" if bridge else "Not live", bridge),
                "voice": (voice_txt, True)}

    select_page = build_shell(tabs, [
        ("Studio", [("Home", "home", home_page), ("Setup", "rocket_launch", setup_page), ("Dashboard", "insights", dashboard_page),
                    ("Teach", "school", teach_page), ("Schedule", "event", schedule_page), ("Live tools", "bolt", tools_page), ("Novel reader", "menu_book", novel_page), ("Novel writer", "edit", writer_page), ("Avatar studio", "face_retouching_natural", avatar_page), ("Story studio", "auto_stories", story_page), ("Products", "shopping_bag", products_page)]),
        ("Host", [("Voice", "record_voice_over", voice_page), ("AI model", "psychology", llm_page),
                  ("Text-to-Speech", "graphic_eq", tts_page), ("Virtual body", "face", visual_body_page),
                  ("Copywriting", "edit_note", copywriting_page), ("Chat", "forum", talk_page),
                  ("Assistant streamer", "support_agent", assistant_anchor_page),
                  ("Image recognition", "image_search", image_recognition_page),
                  ("Translation", "translate", translate_page), ("Points", "stars", integral_page)]),
        ("System", [("Common config", "tune", common_config_page), ("Voice changer", "settings_voice", svc_page),
                    ("Serial port", "usb", serial_page), ("Data analysis", "analytics", data_analysis_page),
                    ("Page config", "web", web_page), ("Docs & tutorials", "menu_book", docs_page),
                    ("About", "info", about_page)]),
    ], dark, status_fn=studio_status, go_live=lambda: select_page(setup_page))
    select_page(home_page)

    with ui.tab_panels(tabs, value=home_page).classes('w-full'):
        with ui.tab_panel(common_config_page).style(tab_panel_css):
            with ui.row():
                
                select_platform = ui.select(
                    label='Platform', 
                    options=platform_options, 
                    value=config.get("platform")
                ).style("width:200px;")

                input_room_display_id = ui.input(label='Live room ID', placeholder='Usually the letters or digits after the last “/” of the live room URL', value=config.get("room_display_id")).style("width:200px;").tooltip('Usually the letters or digits after the last “/” of the live room URL')

                select_chat_type = ui.select(
                    label='Large Language Model', 
                    options=chat_type_options, 
                    value=config.get("chat_type")
                ).style("width:200px;").tooltip('The selected LLM type. Related danmaku messages etc. are passed to this LLM for inference to get an answer')

                select_visual_body = ui.select(
                    label='Virtual Body', 
                    options=visual_body_options, 
                    value=config.get("visual_body")
                ).style("width:200px;").tooltip('The selected virtual body type. If you connect via VTS, choose Other; choose whatever you use to display the body. Most integration options require starting the corresponding server program separately, so do not choose casually.')

                select_audio_synthesis_type = ui.select(
                    label='Speech synthesis', 
                    options=audio_synthesis_type_options, 
                    value=config.get("audio_synthesis_type")
                ).style("width:200px;").tooltip('The selected TTS type; all text content will ultimately be synthesized into speech by this TTS')

            with ui.row():
                select_need_lang = ui.select(
                    label='Reply language', 
                    options={'none': 'All', 'zh': 'Chinese', 'en': 'English', 'jp': 'Japanese'}, 
                    value=config.get("need_lang")
                ).style("width:200px;").tooltip('Restrict the reply language, e.g. if Chinese is selected, only Chinese questions will be replied to and other languages are skipped')

                input_before_prompt = ui.input(label='Prompt prefix', placeholder='This is prepended to the danmaku before sending it to the LLM', value=config.get("before_prompt")).style("width:200px;").tooltip('This is prepended to the danmaku before sending it to the LLM')
                input_after_prompt = ui.input(label='Prompt suffix', placeholder='This is appended to the danmaku before sending it to the LLM', value=config.get("after_prompt")).style("width:200px;").tooltip('This is appended to the danmaku before sending it to the LLM')
                switch_comment_template_enable = ui.switch('Enable danmaku template', value=config.get("comment_template", "enable")).style(switch_internal_css).tooltip('This is appended to the danmaku before sending it to the LLM')
                input_comment_template_copywriting = ui.input(label='Danmaku template', value=config.get("comment_template", "copywriting"), placeholder='This modifies the danmaku content; {} contains variables that are replaced with specified content; do not delete variables arbitrarily').style("width:200px;").tooltip('This modifies the danmaku content; {} contains variables that are replaced with specified content; do not delete variables arbitrarily')
                switch_reply_template_enable = ui.switch('Enable reply template', value=config.get("reply_template", "enable")).style(switch_internal_css).tooltip('This rebuilds the reply content within the answer output by the LLM')
                input_reply_template_username_max_len = ui.input(label='Max length of the replied username', value=config.get("reply_template", "username_max_len"), placeholder='Max length of the replied username').style("width:200px;").tooltip('Max length of the replied username')
                textarea_reply_template_copywriting = ui.textarea(
                    label='Reply template', 
                    placeholder='This modifies the LLM reply content; {} contains variables that are replaced with specified content; do not delete variables arbitrarily', 
                    value=textarea_data_change(config.get("reply_template", "copywriting"))
                ).style("width:500px;").tooltip('This modifies the LLM reply content; {} contains variables that are replaced with specified content; do not delete variables arbitrarily')

            with ui.expansion('Feature Management', icon="settings", value=True).classes('w-full'):

                with ui.card().style(card_css):
                    ui.label('Platform-related')
                    with ui.card().style(card_css):
                        ui.label('Bilibili')
                        with ui.row():
                            select_bilibili_login_type = ui.select(
                                label='Login method',
                                options={'cookie': 'cookie', 'Scan QR with phone': 'Scan QR with phone', 'Scan QR with phone - terminal': 'Scan QR with phone - terminal', 'Account & password login': 'Account & password login', 'open_live': 'Open platform', 'No login': 'No login'},
                                value=config.get("bilibili", "login_type")
                            ).style("width:100px")
                            input_bilibili_cookie = ui.input(label='cookie', placeholder='After logging in to Bilibili, press F12 and capture network packets to get the cookie. Using an alt account is strongly recommended! There is a risk of being banned, although I have not actually heard of anyone being banned', value=config.get("bilibili", "cookie")).style("width:500px;").tooltip('After logging in to Bilibili, press F12 and capture network packets to get the cookie. Using an alt account is strongly recommended! There is a risk of being banned, although I have not actually heard of anyone being banned')
                            input_bilibili_ac_time_value = ui.input(label='ac_time_value', placeholder='After logging in to Bilibili, open the F12 console and enter window.localStorage.ac_time_value to get it (if there is none, log in again)', value=config.get("bilibili", "ac_time_value")).style("width:500px;").tooltip('Optional, only when Platform is Bilibili. After logging in to Bilibili, open the F12 console and enter window.localStorage.ac_time_value to get it (if there is none, log in again)')
                        with ui.row():
                            input_bilibili_username = ui.input(label='Account', value=config.get("bilibili", "username"), placeholder='Bilibili account (an alt account is recommended)').style("width:300px;").tooltip('Only fill in when Platform is Bilibili and Login method is Account & password login. Bilibili account (an alt account is recommended)')
                            input_bilibili_password = ui.input(label='Password', value=config.get("bilibili", "password"), placeholder='Bilibili password (an alt account is recommended)').style("width:300px;").tooltip('Only fill in when Platform is Bilibili and Login method is Account & password login. Bilibili password (an alt account is recommended)')
                        with ui.row():
                            with ui.card().style(card_css):
                                ui.label('Open platform')
                                with ui.row():
                                    input_bilibili_open_live_ACCESS_KEY_ID = ui.input(label='ACCESS_KEY_ID', value=config.get("bilibili", "open_live", "ACCESS_KEY_ID"), placeholder='Open platform ACCESS_KEY_ID').style("width:160px;").tooltip('Only fill in when Platform is Bilibili 2 and Login method is Open platform.Open platform ACCESS_KEY_ID')
                                    input_bilibili_open_live_ACCESS_KEY_SECRET = ui.input(label='ACCESS_KEY_SECRET', value=config.get("bilibili", "open_live", "ACCESS_KEY_SECRET"), placeholder='Open platform ACCESS_KEY_SECRET').style("width:200px;").tooltip('Only fill in when Platform is Bilibili 2 and Login method is Open platform.Open platform ACCESS_KEY_SECRET')
                                    input_bilibili_open_live_APP_ID = ui.input(label='Project ID', value=config.get("bilibili", "open_live", "APP_ID"), placeholder='Open platform Creator Service Center project ID').style("width:100px;").tooltip('Only fill in when Platform is Bilibili 2 and Login method is Open platform.Open platform Creator Service Center project ID')
                                    input_bilibili_open_live_ROOM_OWNER_AUTH_CODE = ui.input(label='Identity code', value=config.get("bilibili", "open_live", "ROOM_OWNER_AUTH_CODE"), placeholder='Live Center user identity code').style("width:100px;").tooltip('Only fill in when Platform is Bilibili 2 and Login method is Open platform.Live Center user identity code')
                    with ui.card().style(card_css):
                        ui.label('Danmaku Fly (ordinaryroad)')
                        with ui.row():
                            input_ordinaryroad_barrage_fly_ws_ip_port = ui.input(label='WebSocket address', value=config.get("ordinaryroad_barrage_fly", "ws_ip_port"), placeholder='Default: ws://127.0.0.1:9898').style("width:300px;").tooltip('Fill in the WebSocket address according to your actual service config')
                            textarea_ordinaryroad_barrage_fly_taskIds = ui.textarea(
                                label='Task ID', 
                                placeholder='For successfully listening tasks, the corresponding task ID can be copied from the page; you can edit multiple ones (separated by line breaks)', 
                                value=textarea_data_change(config.get("ordinaryroad_barrage_fly", "taskIds"))
                            ).style("width:500px;").tooltip('For successfully listening tasks, the corresponding task ID can be copied from the page; you can edit multiple ones (separated by line breaks)')
                    with ui.card().style(card_css):
                        ui.label('twitch')
                        with ui.row():
                            input_twitch_token = ui.input(label='token', value=config.get("twitch", "token"), placeholder='Get it by visiting https://twitchapps.com/tmi/, format: oauth:xxx').style("width:300px;")
                            input_twitch_user = ui.input(label='Username', value=config.get("twitch", "user"), placeholder='Your twitch account username').style("width:300px;")
                            input_twitch_proxy_server = ui.input(label='HTTP proxy IP address', value=config.get("twitch", "proxy_server"), placeholder='The IP address the proxy software listens on for the http protocol, usually 127.0.0.1').style("width:200px;")
                            input_twitch_proxy_port = ui.input(label='HTTP proxy port', value=config.get("twitch", "proxy_port"), placeholder='The port the proxy software listens on for the http protocol, usually 1080').style("width:200px;")
                            
                if config.get("webui", "show_card", "common_config", "play_audio"):
                    with ui.card().style(card_css):
                        ui.label('Audio playback')
                        with ui.row():
                            switch_play_audio_enable = ui.switch('Enable', value=config.get("play_audio", "enable")).style(switch_internal_css)
                            switch_play_audio_text_split_enable = ui.switch('Enable text splitting', value=config.get("play_audio", "text_split_enable")).style(switch_internal_css).tooltip('When enabled, messages from the LLM awaiting audio synthesis are split into multiple short sentences by an internal algorithm so the TTS can synthesize quickly')
                            switch_play_audio_info_to_callback = ui.switch('Send audio info back to the internal endpoint', value=config.get("play_audio", "info_to_callback")).style(switch_internal_css).tooltip('When enabled, after the current audio finishes playing, info about audio waiting to be played is passed to the internal endpoint, used for the idle-time reset function of idle-time tasks.\nHowever, this slows the program down to some extent; if you don’t need idle-time reset, turn it off to improve responsiveness')
                            
                        with ui.row():
                            input_play_audio_interval_num_min = ui.input(label='Min repeat count of the interval', value=config.get("play_audio", "interval_num_min"), placeholder='Interval for normal audio playback, minimum number of sleep repeats. A repeat count is randomly generated between min and max; i.e. count x time = final interval').tooltip('Interval for normal audio playback, minimum number of sleep repeats. A repeat count is randomly generated between min and max; i.e. count x time = final interval')
                            input_play_audio_interval_num_max = ui.input(label='Max repeat count of the interval', value=config.get("play_audio", "interval_num_max"), placeholder='Interval for normal audio playback, maximum number of sleep repeats. A repeat count is randomly generated between min and max; i.e. count x time = final interval').tooltip('Interval for normal audio playback, maximum number of sleep repeats. A repeat count is randomly generated between min and max; i.e. count x time = final interval')
                            input_play_audio_normal_interval_min = ui.input(label='Min interval between normal audio playback', value=config.get("play_audio", "normal_interval_min"), placeholder='The interval between the end of audio playback (danmaku replies, singing, etc.) and the start of the next audio, in seconds').tooltip('The interval between the end of audio playback (danmaku replies, singing, etc.) and the start of the next audio, in seconds. count x time = final interval')
                            input_play_audio_normal_interval_max = ui.input(label='Max interval between normal audio playback', value=config.get("play_audio", "normal_interval_max"), placeholder='The interval between the end of audio playback (danmaku replies, singing, etc.) and the start of the next audio, in seconds').tooltip('The interval between the end of audio playback (danmaku replies, singing, etc.) and the start of the next audio, in seconds. count x time = final interval')
                            
                            input_play_audio_out_path = ui.input(label='Audio output path', placeholder='Path where synthesized audio files are stored; relative or absolute paths are supported', value=config.get("play_audio", "out_path")).tooltip('Path where synthesized audio files are stored; relative or absolute paths are supported')
                            select_play_audio_player = ui.select(
                                label='Audio player',
                                options={'pygame': 'pygame', 'audio_player_v2': 'audio_player_v2', 'audio_player': 'audio_player'},
                                value=config.get("play_audio", "player")
                            ).style("width:200px").tooltip('The selected audio player; the default pygame does not require installing other programs. audio player must be installed and connected separately; see the video tutorial for details')
                    
                        with ui.card().style(card_css):
                            ui.label('audio_player')
                            with ui.row():
                                input_audio_player_api_ip_port = ui.input(
                                    label='API address', 
                                    value=config.get("audio_player", "api_ip_port"), 
                                    placeholder='API address of audio_player; just http://ip:port is enough',
                                    validation={
                                        'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                                    }
                                ).style("width:200px;").tooltip('Only fill in when Audio player is audio_player etc. API address of audio_player; just http://ip:port is enough')

                        with ui.card().style(card_css):
                            ui.label('Audio random speed change')     
                            with ui.grid(columns=3):
                                switch_audio_random_speed_normal_enable = ui.switch('Normal audio speed change', value=config.get("audio_random_speed", "normal", "enable")).style(switch_internal_css).tooltip('Whether to enable the speed change feature for normal audio. This feature requires ffmpeg to be installed and configured')
                                input_audio_random_speed_normal_speed_min = ui.input(label='Speed lower limit', value=config.get("audio_random_speed", "normal", "speed_min")).style("width:200px;").tooltip('Lower limit of audio speed change; the final speed is randomly picked between the lower and upper limits')
                                input_audio_random_speed_normal_speed_max = ui.input(label='Speed upper limit', value=config.get("audio_random_speed", "normal", "speed_max")).style("width:200px;").tooltip('Upper limit of audio speed change; the final speed is randomly picked between the lower and upper limits')
                            with ui.grid(columns=3):
                                switch_audio_random_speed_copywriting_enable = ui.switch('Copywriting audio speed change', value=config.get("audio_random_speed", "copywriting", "enable")).style(switch_internal_css).tooltip('Whether to enable the speed change feature for Copywriting page audio. This feature requires ffmpeg to be installed and configured')
                                input_audio_random_speed_copywriting_speed_min = ui.input(label='Speed lower limit', value=config.get("audio_random_speed", "copywriting", "speed_min")).style("width:200px;").tooltip('Lower limit of audio speed change; the final speed is randomly picked between the lower and upper limits')
                                input_audio_random_speed_copywriting_speed_max = ui.input(label='Speed upper limit', value=config.get("audio_random_speed", "copywriting", "speed_max")).style("width:200px;").tooltip('Upper limit of audio speed change; the final speed is randomly picked between the lower and upper limits')

                if config.get("webui", "show_card", "common_config", "filter"):
                    with ui.card().style(card_css):
                        ui.label('Filter')    
                        with ui.grid(columns=6):
                            textarea_filter_before_must_str = ui.textarea(label='Danmaku trigger prefix', placeholder='The prefix must carry any one of these strings to trigger\nFor example: configure #, then this will trigger: #Hello', value=textarea_data_change(config.get("filter", "before_must_str"))).style("width:200px;").tooltip("The prefix must carry any one of these strings to trigger\nFor example: configure #, then this will trigger: #Hello")
                            textarea_filter_after_must_str = ui.textarea(label='Danmaku trigger suffix', placeholder='The suffix must carry any one of these strings to trigger\nFor example: configure “.”, then this will trigger: Hello.', value=textarea_data_change(config.get("filter", "before_must_str"))).style("width:200px;").tooltip("The suffix must carry any one of these strings to trigger\nFor example: configure “.”, then this will trigger: Hello.")
                            textarea_filter_before_filter_str = ui.textarea(label='Danmaku filter prefix', placeholder='When the prefix is any one of these strings, the danmaku is filtered\nFor example: configure #, then this will be filtered: #Hello', value=textarea_data_change(config.get("filter", "before_filter_str"))).style("width:200px;").tooltip("When the prefix is any one of these strings, the danmaku is filtered\nFor example: configure #, then this will be filtered: #Hello")
                            textarea_filter_after_filter_str = ui.textarea(label='Danmaku filter suffix', placeholder='When the suffix is any one of these strings, the danmaku is filtered\nFor example: configure #, then this will be filtered: Hello#', value=textarea_data_change(config.get("filter", "before_filter_str"))).style("width:200px;").tooltip("When the suffix is any one of these strings, the danmaku is filtered\nFor example: configure #, then this will be filtered: Hello#")
                            textarea_filter_before_must_str_for_llm = ui.textarea(label='LLM trigger prefix', placeholder='The prefix must carry any one of these strings to trigger the LLM\nFor example: configure #, then this will trigger: #Hello', value=textarea_data_change(config.get("filter", "before_must_str_for_llm"))).style("width:200px;").tooltip("The prefix must carry any one of these strings to trigger the LLM\nFor example: configure #, then this will trigger: #Hello")
                            textarea_filter_after_must_str_for_llm = ui.textarea(label='LLM trigger suffix', placeholder='The suffix must carry any one of these strings to trigger the LLM\nFor example: configure “.”, then this will trigger: Hello.', value=textarea_data_change(config.get("filter", "before_must_str_for_llm"))).style("width:200px;").tooltip('The suffix must carry any one of these strings to trigger the LLM\nFor example: configure “.”, then this will trigger: Hello.')
                            
                        with ui.row():
                            input_filter_max_len = ui.input(label='Max words', placeholder='Maximum number of English words to read (space-separated)', value=config.get("filter", "max_len")).style("width:150px;").tooltip('Maximum number of English words to read (space-separated)')
                            input_filter_max_char_len = ui.input(label='Max characters', placeholder='Maximum number of characters to read; double filtering to avoid overflow', value=config.get("filter", "max_char_len")).style("width:150px;").tooltip('Maximum number of characters to read; double filtering to avoid overflow')
                            switch_filter_username_convert_digits_to_chinese = ui.switch('Convert digits in usernames to Chinese', value=config.get("filter", "username_convert_digits_to_chinese")).style(switch_internal_css).tooltip('Convert digits in usernames to Chinese')
                            switch_filter_emoji = ui.switch('Danmaku emoji filter', value=config.get("filter", "emoji")).style(switch_internal_css)
                        with ui.grid(columns=5):
                            switch_filter_badwords_enable = ui.switch('Banned word filter', value=config.get("filter", "badwords", "enable")).style(switch_internal_css)
                            switch_filter_badwords_discard = ui.switch('Discard banned sentences', value=config.get("filter", "badwords", "discard")).style(switch_internal_css)
                            input_filter_badwords_path = ui.input(label='Banned words path', value=config.get("filter", "badwords", "path"), placeholder='Local banned word data path (if you don’t need it, you can clear the file content)').style("width:200px;").tooltip('Local banned word data path (if you don’t need it, you can clear the file content)')
                            input_filter_badwords_bad_pinyin_path = ui.input(label='Banned pinyin path', value=config.get("filter", "badwords", "bad_pinyin_path"), placeholder='Local banned pinyin data path (if you don’t need it, you can clear the file content)').style("width:200px;").tooltip('Local banned pinyin data path (if you don’t need it, you can clear the file content)')
                            input_filter_badwords_replace = ui.input(label='Banned word replacement', value=config.get("filter", "badwords", "replace"), placeholder='Without discarding banned sentences, replace banned words with this text').style("width:200px;").tooltip('Without discarding banned sentences, replace banned words with this text')
                        
                        with ui.expansion('Message forgetting & retention settings', icon="settings", value=True).classes('w-full'):
                            with ui.element('div').classes('p-2 bg-blue-100'):
                                ui.label("Forget interval means that every such interval (seconds), the data received during that interval is discarded, but the latest n items are kept; Retention count is the number of latest received items to keep")
                            with ui.grid(columns=4):
                                input_filter_comment_forget_duration = ui.input(
                                    label='Danmaku forget interval', 
                                    placeholder='e.g. 1', 
                                    value=config.get("filter", "comment_forget_duration")
                                ).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_comment_forget_reserve_num = ui.input(label='Danmaku retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "comment_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                                input_filter_gift_forget_duration = ui.input(label='Gift forget interval', placeholder='This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config', value=config.get("filter", "gift_forget_duration")).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_gift_forget_reserve_num = ui.input(label='Gift retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "gift_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                            with ui.grid(columns=4):
                                input_filter_entrance_forget_duration = ui.input(label='Entrance forget interval', placeholder='This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config', value=config.get("filter", "entrance_forget_duration")).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_entrance_forget_reserve_num = ui.input(label='Entrance retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "entrance_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                                input_filter_follow_forget_duration = ui.input(label='Follow forget interval', placeholder='This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config', value=config.get("filter", "follow_forget_duration")).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_follow_forget_reserve_num = ui.input(label='Follow retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "follow_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                            with ui.grid(columns=4):
                                input_filter_talk_forget_duration = ui.input(label='Chat forget interval', placeholder='This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config', value=config.get("filter", "talk_forget_duration")).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_talk_forget_reserve_num = ui.input(label='Chat retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "talk_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                                input_filter_schedule_forget_duration = ui.input(label='Scheduled forget interval', placeholder='This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config', value=config.get("filter", "schedule_forget_duration")).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_schedule_forget_reserve_num = ui.input(label='Scheduled retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "schedule_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                            with ui.grid(columns=4):
                                input_filter_idle_time_task_forget_duration = ui.input(label='Idle-time task forget interval', placeholder='This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config', value=config.get("filter", "idle_time_task_forget_duration")).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_idle_time_task_forget_reserve_num = ui.input(label='Idle-time task retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "idle_time_task_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                                input_filter_image_recognition_schedule_forget_duration = ui.input(label='Image recognition forget interval', placeholder='This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config', value=config.get("filter", "image_recognition_schedule_forget_duration")).style("width:200px;").tooltip('This means that every such interval (seconds), the data received during that interval is discarded,\nand the retained data can be customized in the following config')
                                input_filter_image_recognition_schedule_forget_reserve_num = ui.input(label='Image recognition retention count', placeholder='Number of latest received items to keep', value=config.get("filter", "image_recognition_schedule_forget_reserve_num")).style("width:200px;").tooltip('Number of latest received items to keep')
                        with ui.expansion('Discard duplicate data within a limited time period', icon="settings", value=True).classes('w-full'):
                            with ui.row():
                                switch_filter_limited_time_deduplication_enable = ui.switch('Enable', value=config.get("filter", "limited_time_deduplication", "enable")).style(switch_internal_css)
                                input_filter_limited_time_deduplication_comment = ui.input(label='Danmaku detection period', value=config.get("filter", "limited_time_deduplication", "comment"), placeholder='Duplicate data within this period (seconds) will be discarded').style("width:200px;").tooltip('Duplicate data within this period (seconds) will be discarded')
                                input_filter_limited_time_deduplication_gift = ui.input(label='Gift detection period', value=config.get("filter", "limited_time_deduplication", "gift"), placeholder='Duplicate data within this period (seconds) will be discarded').style("width:200px;").tooltip('Duplicate data within this period (seconds) will be discarded')
                                input_filter_limited_time_deduplication_entrance = ui.input(label='Entrance detection period', value=config.get("filter", "limited_time_deduplication", "entrance"), placeholder='Duplicate data within this period (seconds) will be discarded').style("width:200px;").tooltip('Duplicate data within this period (seconds) will be discarded')
                                    
                        with ui.expansion('Messages awaiting audio synthesis & audio queue awaiting playback', icon="settings", value=True).classes('w-full'):
                            with ui.row():
                                input_filter_message_queue_max_len = ui.input(label='Message queue max retained length', placeholder='Received messages and generated text content are put into the message queue by priority; when a new message has a lower priority than all messages in the queue and the queue exceeds this length, the message is discarded', value=config.get("filter", "message_queue_max_len")).style("width:160px;").tooltip('Received messages and generated text content are put into the message queue by priority; when a new message has a lower priority than all messages in the queue and the queue exceeds this length, the message is discarded')
                                input_filter_voice_tmp_path_queue_max_len = ui.input(label='Audio playback queue max retained length', placeholder='Synthesized audio is put into the playback queue by priority; when a new audio has a lower priority than all audio in the queue and the queue exceeds this length, the audio is discarded', value=config.get("filter", "voice_tmp_path_queue_max_len")).style("width:200px;").tooltip('Synthesized audio is put into the playback queue by priority; when a new audio has a lower priority than all audio in the queue and the queue exceeds this length, the audio is discarded')

                                input_filter_voice_tmp_path_queue_min_start_play = ui.input(
                                    label='Audio playback queue first-trigger playback threshold', 
                                    placeholder='Positive integer, e.g. 20; if you don’t want to buffer a certain amount of audio before going live, set 0', 
                                    value=config.get("filter", "voice_tmp_path_queue_min_start_play")
                                ).style("width:200px;").tooltip('This feature buffers a certain amount of audio before starting playback. If you don’t want to buffer audio before going live, set 0; if you want to prepare some audio in advance, e.g. because TTS synthesis is slow, set this value so the TTS pre-synthesizes content triggered by your other tasks')

                                with ui.element('div').classes('p-2 bg-blue-100'):
                                    ui.label("For the priority settings below, use positive integers. The larger the number, the higher the priority, and it will be synthesized and played first")
                                    ui.label("Also note that, due to legacy code issues, the length of this queue is currently calculated after text splitting, so if the reply is too long, data may be lost")
                            with ui.grid(columns=5):
                                input_filter_priority_mapping_idle_time_task = ui.input(label='Idle-time task priority', value=config.get("filter", "priority_mapping", "idle_time_task"), placeholder='The larger the number, the higher the priority; but this is not text, so it is of no use for now and is reserved').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_image_recognition_schedule = ui.input(label='Image recognition priority', value=config.get("filter", "priority_mapping", "image_recognition_schedule"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_local_qa_audio = ui.input(label='Local Q&A - audio priority', value=config.get("filter", "priority_mapping", "local_qa_audio"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_comment = ui.input(label='Danmaku reply priority', value=config.get("filter", "priority_mapping", "comment"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_copywriting = ui.input(label='Copywriting priority', value=config.get("filter", "priority_mapping", "copywriting"), placeholder='The larger the number, the higher the priority; Copywriting page copy, but this is not text, so it is of no use for now and is reserved').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                
                            with ui.grid(columns=5):
                                input_filter_priority_mapping_song = ui.input(label='Song request priority', value=config.get("filter", "priority_mapping", "song"), placeholder='The larger the number, the higher the priority; but this is not text, so it is of no use for now and is reserved').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_read_comment = ui.input(label='Read danmaku priority', value=config.get("filter", "priority_mapping", "read_comment"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_entrance = ui.input(label='Entrance welcome priority', value=config.get("filter", "priority_mapping", "entrance"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_gift = ui.input(label='Gift thanks priority', value=config.get("filter", "priority_mapping", "gift"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_follow = ui.input(label='Follow thanks priority', value=config.get("filter", "priority_mapping", "follow"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                            with ui.grid(columns=5):
                                input_filter_priority_mapping_talk = ui.input(label='Chat (voice input) priority', value=config.get("filter", "priority_mapping", "talk"), placeholder='The larger the number, the higher the priority; but this is not text, so it is of no use for now and is reserved').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_reread = ui.input(label='Repeat priority', value=config.get("filter", "priority_mapping", "reread"), placeholder='The larger the number, the higher the priority; but this is not text, so it is of no use for now and is reserved').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_key_mapping = ui.input(label='Key mapping priority', value=config.get("filter", "priority_mapping", "key_mapping"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_integral = ui.input(label='Points priority', value=config.get("filter", "priority_mapping", "integral"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_reread_top_priority = ui.input(label='Top-priority repeat priority', value=config.get("filter", "priority_mapping", "reread_top_priority"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                
                            with ui.grid(columns=5):
                                input_filter_priority_mapping_abnormal_alarm = ui.input(label='Abnormal alarm priority', value=config.get("filter", "priority_mapping", "abnormal_alarm"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_trends_copywriting = ui.input(label='Dynamic copywriting priority', value=config.get("filter", "priority_mapping", "trends_copywriting"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_schedule = ui.input(label='Scheduled task priority', value=config.get("filter", "priority_mapping", "schedule"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_assistant_anchor_text = ui.input(label='Assistant - text priority', value=config.get("filter", "priority_mapping", "assistant_anchor_text"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                input_filter_priority_mapping_assistant_anchor_audio = ui.input(label='Assistant - audio priority', value=config.get("filter", "priority_mapping", "assistant_anchor_audio"), placeholder='The larger the number, the higher the priority').style("width:200px;").tooltip('The larger the number, the higher the priority')
                                
                        
                        with ui.expansion('Danmaku blacklist', icon="settings", value=True).classes('w-full'):
                            with ui.row():
                                switch_filter_blacklist_enable = ui.switch('Enable', value=config.get("filter", "blacklist", "enable")).style(switch_internal_css)
                            
                            with ui.row():
                                textarea_filter_blacklist_username = ui.textarea(label='Username blacklist', value=textarea_data_change(config.get("filter", "blacklist", "username")), placeholder='Block danmaku from all users on this list; separate usernames with line breaks').style("width:500px;")
                            
            with ui.expansion('Interactive Features', icon="question_answer", value=True).classes('w-full'):

                if config.get("webui", "show_card", "common_config", "read_comment"):
                    with ui.card().style(card_css):
                        ui.label('Read danmaku')
                        with ui.grid(columns=4):
                            switch_read_comment_enable = ui.switch('Enable', value=config.get("read_comment", "enable")).style(switch_internal_css)
                            switch_read_comment_read_username_enable = ui.switch('Read username', value=config.get("read_comment", "read_username_enable")).style(switch_internal_css)
                            input_read_comment_username_max_len = ui.input(label='Max username length', value=config.get("read_comment", "username_max_len"), placeholder='Maximum length of the username to keep; the excess is discarded').style("width:100px;").tooltip('Maximum length of the username to keep; the excess is discarded')
                            switch_read_comment_voice_change = ui.switch('Voice Changer', value=config.get("read_comment", "voice_change")).style(switch_internal_css)
                        with ui.grid(columns=2):
                            textarea_read_comment_read_username_copywriting = ui.textarea(
                                label='Read-username copywriting', 
                                placeholder='Copywriting used when reading the username; you can edit multiple ones (separated by line breaks), and one is picked at random in practice', 
                                value=textarea_data_change(config.get("read_comment", "read_username_copywriting"))
                            ).style("width:500px;").tooltip('Copywriting used when reading the username; you can edit multiple ones (separated by line breaks), and one is picked at random in practice')
                        with ui.row():
                            switch_read_comment_periodic_trigger_enable = ui.switch('Enable periodic trigger', value=config.get("read_comment", "periodic_trigger", "enable")).style(switch_internal_css)
                            input_read_comment_periodic_trigger_periodic_time_min = ui.input(
                                label='Trigger period min', 
                                value=config.get("read_comment", "periodic_trigger", "periodic_time_min"), 
                                placeholder='e.g. 5'
                            ).style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                            input_read_comment_periodic_trigger_periodic_time_max = ui.input(
                                label='Trigger period max', 
                                value=config.get("read_comment", "periodic_trigger", "periodic_time_max"), 
                                placeholder='e.g. 10'
                            ).style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                            input_read_comment_periodic_trigger_trigger_num_min = ui.input(
                                label='Trigger count min', 
                                value=config.get("read_comment", "periodic_trigger", "trigger_num_min"), 
                                placeholder='e.g. 0'
                            ).style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values')
                            input_read_comment_periodic_trigger_trigger_num_max = ui.input(
                                label='Trigger count max', 
                                value=config.get("read_comment", "periodic_trigger", "trigger_num_max"), 
                                placeholder='e.g. 1'
                            ).style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values')
                
                if config.get("webui", "show_card", "common_config", "local_qa"):
                    with ui.card().style(card_css):
                        ui.label('Local Q&A')
                        with ui.row():
                            switch_local_qa_periodic_trigger_enable = ui.switch('Enable periodic trigger', value=config.get("local_qa", "periodic_trigger", "enable")).style(switch_internal_css)
                            input_local_qa_periodic_trigger_periodic_time_min = ui.input(label='Trigger period min', value=config.get("local_qa", "periodic_trigger", "periodic_time_min"), placeholder='This feature is triggered n times every such period').style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                            input_local_qa_periodic_trigger_periodic_time_max = ui.input(label='Trigger period max', value=config.get("local_qa", "periodic_trigger", "periodic_time_max"), placeholder='This feature is triggered n times every such period').style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                            input_local_qa_periodic_trigger_trigger_num_min = ui.input(label='Trigger count min', value=config.get("local_qa", "periodic_trigger", "trigger_num_min"), placeholder='When the period elapses, this feature is triggered n times').style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                            input_local_qa_periodic_trigger_trigger_num_max = ui.input(label='Trigger count max', value=config.get("local_qa", "periodic_trigger", "trigger_num_max"), placeholder='When the period elapses, this feature is triggered n times').style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                            
                        with ui.grid(columns=5):
                            switch_local_qa_text_enable = ui.switch('Enable text matching', value=config.get("local_qa", "text", "enable")).style(switch_internal_css)
                            select_local_qa_text_type = ui.select(
                                label='Danmaku log type',
                                options={'json': 'Custom json', 'text': 'One question, one answer'},
                                value=config.get("local_qa", "text", "type")
                            )
                            input_local_qa_text_file_path = ui.input(label='Text Q&A data path', placeholder='Local Q&A text data storage path', value=config.get("local_qa", "text", "file_path")).style("width:200px;")
                            input_local_qa_text_similarity = ui.input(label='Text min similarity', placeholder='Minimum text matching similarity, i.e. the minimum similarity between the content sent by the user and the content set in the local Q&A library.\nBelow it, the message is treated as a regular danmaku', value=config.get("local_qa", "text", "similarity")).style("width:200px;")
                            input_local_qa_text_username_max_len = ui.input(label='Max username length', value=config.get("local_qa", "text", "username_max_len"), placeholder='Maximum length of the username to keep; the excess is discarded').style("width:100px;")       
                        with ui.grid(columns=4):
                            switch_local_qa_audio_enable = ui.switch('Enable audio matching', value=config.get("local_qa", "audio", "enable")).style(switch_internal_css)
                            input_local_qa_audio_file_path = ui.input(label='Audio storage path', placeholder='Local Q&A audio file storage path', value=config.get("local_qa", "audio", "file_path")).style("width:200px;")
                            input_local_qa_audio_similarity = ui.input(label='Audio min similarity', placeholder='Minimum audio matching similarity, i.e. the minimum similarity between the content sent by the user and the audio file names in the local audio library.\nBelow it, the message is treated as a regular danmaku', value=config.get("local_qa", "audio", "similarity")).style("width:200px;")
                        with ui.row():
                            input_local_qa_text_json_file_path = ui.input(label='json file path', placeholder='Fill in the json file path; the default is the local Q&A text data storage path', value=config.get("local_qa", "text", "file_path")).style("width:200px;").tooltip("Fill in the json file path; the default is the local Q&A text data storage path")

                            def local_qa_text_json_file_reload():
                                try:
                                    # Only an empty check is done, so don’t fill in randomly
                                    if input_local_qa_text_json_file_path.value != "":
                                        textarea_local_qa_text_json_file_content.value = json.dumps(common.read_file(input_local_qa_text_json_file_path.value, "dict"), ensure_ascii=False, indent=3)
                                except Exception as e:
                                    logger.error(traceback.format_exc())
                                    ui.notify(f"The file path is wrong or there is another problem. Error:{str(e)}", position="top", type="negative")

                            button_local_qa_text_json_file_reload = ui.button('Load file', on_click=lambda: local_qa_text_json_file_reload(), color=button_internal_color).style(button_internal_css)

                            textarea_local_qa_text_json_file_content = ui.textarea(label='JSON file content', placeholder='Mind the format!').style("width:700px;")

                            local_qa_text_json_file_reload()
                
                if config.get("webui", "show_card", "common_config", "thanks"):
                    with ui.card().style(card_css):
                        ui.label('Thanks')  
                        with ui.row():
                            input_thanks_username_max_len = ui.input(label='Max username length', value=config.get("thanks", "username_max_len"), placeholder='Maximum length of the username to keep; the excess is discarded').style("width:100px;")       
                        with ui.expansion('Entrance settings', icon="settings", value=True).classes('w-full'):
                            with ui.row():
                                switch_thanks_entrance_enable = ui.switch('Enable entrance welcome', value=config.get("thanks", "entrance_enable")).style(switch_internal_css)
                                switch_thanks_entrance_random = ui.switch('Random pick', value=config.get("thanks", "entrance_random")).style(switch_internal_css)
                                textarea_thanks_entrance_copy = ui.textarea(label='Entrance copywriting', value=textarea_data_change(config.get("thanks", "entrance_copy")), placeholder='Copywriting for users entering the live room; do not touch {username}, this string is used to replace the username').style("width:500px;")

                            with ui.row():
                                switch_thanks_entrance_periodic_trigger_enable = ui.switch('Enable periodic trigger', value=config.get("thanks", "entrance", "periodic_trigger", "enable")).style(switch_internal_css)
                                input_thanks_entrance_periodic_trigger_periodic_time_min = ui.input(label='Trigger period min', value=config.get("thanks", "entrance", "periodic_trigger", "periodic_time_min"), placeholder='This feature is triggered n times every such period').style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                                input_thanks_entrance_periodic_trigger_periodic_time_max = ui.input(label='Trigger period max', value=config.get("thanks", "entrance", "periodic_trigger", "periodic_time_max"), placeholder='This feature is triggered n times every such period').style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                                input_thanks_entrance_periodic_trigger_trigger_num_min = ui.input(label='Trigger count min', value=config.get("thanks", "entrance", "periodic_trigger", "trigger_num_min"), placeholder='When the period elapses, this feature is triggered n times').style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                                input_thanks_entrance_periodic_trigger_trigger_num_max = ui.input(label='Trigger count max', value=config.get("thanks", "entrance", "periodic_trigger", "trigger_num_max"), placeholder='When the period elapses, this feature is triggered n times').style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                        with ui.expansion('Gift settings', icon="settings", value=True).classes('w-full'):
                            with ui.row():
                                switch_thanks_gift_enable = ui.switch('Enable gift thanks', value=config.get("thanks", "gift_enable")).style(switch_internal_css)
                                switch_thanks_gift_random = ui.switch('Random pick', value=config.get("thanks", "gift_random")).style(switch_internal_css)
                                textarea_thanks_gift_copy = ui.textarea(label='Gift copywriting', value=textarea_data_change(config.get("thanks", "gift_copy")), placeholder='Copywriting for users sending gifts; do not touch {username} and {gift_name}, these strings are used to replace the username and gift name').style("width:500px;")
                                input_thanks_lowest_price = ui.input(label='Minimum thanked gift price', value=config.get("thanks", "lowest_price"), placeholder='Set the minimum price (CNY) of gifts to thank; gifts below this will not trigger thanks').style("width:100px;")
                            with ui.row():
                                switch_thanks_gift_periodic_trigger_enable = ui.switch('Enable periodic trigger', value=config.get("thanks", "gift", "periodic_trigger", "enable")).style(switch_internal_css)
                                input_thanks_gift_periodic_trigger_periodic_time_min = ui.input(label='Trigger period min', value=config.get("thanks", "gift", "periodic_trigger", "periodic_time_min"), placeholder='This feature is triggered n times every such period').style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                                input_thanks_gift_periodic_trigger_periodic_time_max = ui.input(label='Trigger period max', value=config.get("thanks", "gift", "periodic_trigger", "periodic_time_max"), placeholder='This feature is triggered n times every such period').style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                                input_thanks_gift_periodic_trigger_trigger_num_min = ui.input(label='Trigger count min', value=config.get("thanks", "gift", "periodic_trigger", "trigger_num_min"), placeholder='When the period elapses, this feature is triggered n times').style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                                input_thanks_gift_periodic_trigger_trigger_num_max = ui.input(label='Trigger count max', value=config.get("thanks", "gift", "periodic_trigger", "trigger_num_max"), placeholder='When the period elapses, this feature is triggered n times').style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                        with ui.expansion('Follow settings', icon="settings", value=True).classes('w-full'):
                            with ui.row():
                                switch_thanks_follow_enable = ui.switch('Enable follow thanks', value=config.get("thanks", "follow_enable")).style(switch_internal_css)
                                switch_thanks_follow_random = ui.switch('Random pick', value=config.get("thanks", "follow_random")).style(switch_internal_css)
                                textarea_thanks_follow_copy = ui.textarea(label='Follow copywriting', value=textarea_data_change(config.get("thanks", "follow_copy")), placeholder='Copywriting for when a user follows; do not touch {username}, this string is used to replace the username').style("width:500px;")
                            with ui.row():
                                switch_thanks_follow_periodic_trigger_enable = ui.switch(
                                    'Enable periodic trigger', 
                                    value=config.get("thanks", "follow", "periodic_trigger", "enable")
                                ).style(switch_internal_css)
                                input_thanks_follow_periodic_trigger_periodic_time_min = ui.input(
                                    label='Trigger period min', 
                                    value=config.get("thanks", "follow", "periodic_trigger", "periodic_time_min"), 
                                    placeholder='This feature is triggered n times every such period'
                                ).style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                                input_thanks_follow_periodic_trigger_periodic_time_max = ui.input(
                                    label='Trigger period max', 
                                    value=config.get("thanks", "follow", "periodic_trigger", "periodic_time_max"), 
                                    placeholder='This feature is triggered n times every such period'
                                ).style("width:100px;").tooltip('This feature is triggered n times every such period; the period is randomly generated between the min and max values')
                                input_thanks_follow_periodic_trigger_trigger_num_min = ui.input(
                                    label='Trigger count min', 
                                    value=config.get("thanks", "follow", "periodic_trigger", "trigger_num_min"), 
                                    placeholder='When the period elapses, this feature is triggered n times'
                                ).style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                                input_thanks_follow_periodic_trigger_trigger_num_max = ui.input(
                                    label='Trigger count max', 
                                    value=config.get("thanks", "follow", "periodic_trigger", "trigger_num_max"), 
                                    placeholder='When the period elapses, this feature is triggered n times'
                                ).style("width:100px;").tooltip('When the period elapses, this feature is triggered n times; n is randomly generated between the min and max values') 
                        
                if config.get("webui", "show_card", "common_config", "choose_song"): 
                    with ui.card().style(card_css):
                        ui.label('Song request mode') 
                        with ui.row():
                            switch_choose_song_enable = ui.switch('Enable', value=config.get("choose_song", "enable")).style(switch_internal_css)
                            textarea_choose_song_start_cmd = ui.textarea(
                                label='Song request trigger command', 
                                value=textarea_data_change(config.get("choose_song", "start_cmd")), 
                                placeholder='Song request trigger commands, separated by line breaks, multiple commands supported; triggered by sending danmaku (must match exactly)'
                            ).style("width:200px;").tooltip('Song request trigger commands, separated by line breaks, multiple commands supported; triggered by sending danmaku (must match exactly)')
                            textarea_choose_song_stop_cmd = ui.textarea(
                                label='Cancel song request command', 
                                value=textarea_data_change(config.get("choose_song", "stop_cmd")), 
                                placeholder='Stop song request commands, separated by line breaks, multiple commands supported; triggered by sending danmaku (must match exactly)'
                            ).style("width:200px;").tooltip('Stop song request commands, separated by line breaks, multiple commands supported; triggered by sending danmaku (must match exactly)')
                            textarea_choose_song_random_cmd = ui.textarea(
                                label='Random song request command', 
                                value=textarea_data_change(config.get("choose_song", "random_cmd")), 
                                placeholder='Random song request commands, separated by line breaks, multiple commands supported; triggered by sending danmaku (must match exactly)'
                            ).style("width:200px;").tooltip('Random song request commands, separated by line breaks, multiple commands supported; triggered by sending danmaku (must match exactly)')
                        with ui.row():
                            input_choose_song_song_path = ui.input(
                                label='Song path', 
                                value=config.get("choose_song", "song_path"), 
                                placeholder='Path where song audio is stored; audio files are read automatically'
                            ).style("width:200px;").tooltip('Path where song audio is stored; audio files are read automatically')
                            input_choose_song_match_fail_copy = ui.input(
                                label='Match-failure copywriting', 
                                value=config.get("choose_song", "match_fail_copy"), 
                                placeholder='Audio copywriting returned on match failure. Note: {content} is used to replace the song name sent by the user, do not delete it carelessly! It affects usage!'
                            ).style("width:300px;").tooltip('Audio copywriting returned on match failure. Note: {content} is used to replace the song name sent by the user, do not delete it carelessly! It affects usage!')
                            input_choose_song_similarity = ui.input(
                                label='Match min similarity', 
                                value=config.get("choose_song", "similarity"), 
                                placeholder='Minimum audio matching similarity, i.e. the minimum similarity between the content sent by the user and the audio file names in the local audio library.\nBelow it, the message is treated as a regular danmaku'
                            ).style("width:200px;").tooltip('Minimum audio matching similarity, i.e. the minimum similarity between the content sent by the user and the audio file names in the local audio library.\nBelow it, the message is treated as a regular danmaku')
                
                if config.get("webui", "show_card", "common_config", "schedule"): 
                    with ui.card().style(card_css):
                        ui.label('Scheduled tasks')
                        with ui.row():
                            input_schedule_index = ui.input(label='Task index', value="", placeholder='Order number of the task group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                            button_schedule_add = ui.button('Add task group', on_click=schedule_add, color=button_internal_color).style(button_internal_css)
                            button_schedule_del = ui.button('Delete task group', on_click=lambda: schedule_del(input_schedule_index.value), color=button_internal_color).style(button_internal_css)
                        
                        schedule_var = {}
                        schedule_config_card = ui.card()
                        for index, schedule in enumerate(config.get("schedule")):
                            with schedule_config_card.style(card_css):
                                with ui.row():
                                    schedule_var[str(4 * index)] = ui.switch(text=f"Enable task#{index}", value=schedule["enable"]).style(switch_internal_css)
                                    schedule_var[str(4 * index + 1)] = ui.input(label=f"Min loop period#{index}", value=schedule["time_min"], placeholder='Minimum duration (seconds) of the scheduled task loop; the task runs once every such period').style("width:100px;").tooltip('Minimum duration (seconds) of the scheduled task loop; the final period is randomly generated between min and max, and the task runs once every such period')
                                    schedule_var[str(4 * index + 2)] = ui.input(label=f"Max loop period#{index}", value=schedule["time_max"], placeholder='Maximum duration (seconds) of the scheduled task loop; the task runs once every such period').style("width:100px;").tooltip('Minimum duration (seconds) of the scheduled task loop; the final period is randomly generated between min and max, and the task runs once every such period')
                                    schedule_var[str(4 * index + 3)] = ui.textarea(label=f"Copywriting list#{index}", value=textarea_data_change(schedule["copy"]), placeholder='List of copywriting, separated by spaces or line breaks; use {variable} to replace key data; you can modify the source code to customize the function').style("width:500px;").tooltip('List of copywriting, separated by spaces or line breaks; use {variable} to replace key data; you can modify the source code to customize the function')
                    
                if config.get("webui", "show_card", "common_config", "idle_time_task"): 
                    with ui.card().style(card_css):
                        ui.label('Idle-time task')
                        with ui.row():
                            switch_idle_time_task_enable = ui.switch('Enable', value=config.get("idle_time_task", "enable")).style(switch_internal_css)
                            select_idle_time_task_type = ui.select(
                                label='Mechanism type',
                                options={
                                    'Idle: message queue': 'Idle: message queue', 
                                    'Idle: audio queue': 'Idle: audio queue', 
                                    'Idle: no room messages': 'Idle: no room messages',
                                },
                                value=config.get("idle_time_task", "type")
                            ).tooltip('The logic by which idle-time tasks are executed; different logics give different trigger effects.\nFor selling products, you can choose “Idle time updated by the pending-playback audio queue” and set the trigger value to 1, so idle-time tasks only trigger when there are fewer than 1 audio items, effectively suppressing a flood of tasks.\nFor scenarios that don’t require talking all the time, we recommend “Idle time updated when the live room has no messages” with a larger interval, triggering once in a while.')
                        with ui.row():
                            input_idle_time_task_idle_min_msg_queue_len_to_trigger = ui.input(
                                label='Trigger when the pending-synthesis message queue count is less than this value', 
                                value=config.get("idle_time_task", "min_msg_queue_len_to_trigger"), 
                                placeholder='Idle-time tasks only trigger when the pending-synthesis message queue count is less than this value'
                            ).style("width:250px;").tooltip('Idle-time tasks only trigger when the pending-synthesis message queue count is less than this value')
                            input_idle_time_task_idle_min_audio_queue_len_to_trigger = ui.input(
                                label='Trigger when the pending-playback audio queue count is less than this value', 
                                value=config.get("idle_time_task", "min_audio_queue_len_to_trigger"), 
                                placeholder='Idle-time tasks only trigger when the pending-playback audio queue count is less than this value'
                            ).style("width:250px;").tooltip('Idle-time tasks only trigger when the pending-playback audio queue count is less than this value')
                            
                        with ui.row():
                            input_idle_time_task_idle_time_min = ui.input(
                                label='Min idle time', 
                                value=config.get("idle_time_task", "idle_time_min"), 
                                placeholder='Minimum idle interval (positive integer, in seconds), i.e. the time elapsed when there is no danmaku'
                            ).style("width:150px;").tooltip('Minimum idle interval (positive integer, in seconds), i.e. the time elapsed when there is no danmaku')
                            input_idle_time_task_idle_time_max = ui.input(
                                label='Max idle time', 
                                value=config.get("idle_time_task", "idle_time_max"), 
                                placeholder='Maximum idle interval (positive integer, in seconds), i.e. the time elapsed when there is no danmaku'
                            ).style("width:150px;").tooltip('Maximum idle interval (positive integer, in seconds), i.e. the time elapsed when there is no danmaku')
                            input_idle_time_task_wait_play_audio_num_threshold = ui.input(
                                label='Pending-playback audio count threshold', 
                                value=config.get("idle_time_task", "wait_play_audio_num_threshold"), 
                                placeholder='When the number of audio items waiting to play exceeds this threshold, after the audio finishes playing the idle time is reduced to the configured reduction value, aiming to control the total number of idle-time tasks triggered'
                            ).style("width:150px;").tooltip('When the number of audio items waiting to play exceeds this threshold, after the audio finishes playing the idle time is reduced to the configured reduction value, aiming to control the total number of idle-time tasks triggered')
                            input_idle_time_task_idle_time_reduce_to = ui.input(label='Idle timer reduced to', value=config.get("idle_time_task", "idle_time_reduce_to"), placeholder='The value the idle timer is reduced to when the threshold is reached').style("width:150px;").tooltip('The value the idle timer is reduced to when the threshold is reached')
                            
                        with ui.row():
                            ui.label('Message types that refresh the idle timer')
                            # TypeList
                            idle_time_task_trigger_type_list = ["comment", "gift", "entrance", "follow"]
                            idle_time_task_trigger_type_mapping = {
                                "comment": "Comment",
                                "gift": "Gift",
                                "entrance": "Entrance",
                                "follow": "Follow",
                            }
                            idle_time_task_trigger_type_var = {}
                            
                            for index, idle_time_task_trigger_type in enumerate(idle_time_task_trigger_type_list):
                                if idle_time_task_trigger_type in config.get("idle_time_task", "trigger_type"):
                                    idle_time_task_trigger_type_var[str(index)] = ui.checkbox(text=idle_time_task_trigger_type_mapping[idle_time_task_trigger_type], value=True)
                                else:
                                    idle_time_task_trigger_type_var[str(index)] = ui.checkbox(text=idle_time_task_trigger_type_mapping[idle_time_task_trigger_type], value=False)
                    

                        with ui.row():
                            switch_idle_time_task_copywriting_enable = ui.switch('Copywriting mode', value=config.get("idle_time_task", "copywriting", "enable")).style(switch_internal_css)
                            switch_idle_time_task_copywriting_random = ui.switch('Random copywriting', value=config.get("idle_time_task", "copywriting", "random")).style(switch_internal_css)
                            textarea_idle_time_task_copywriting_copy = ui.textarea(
                                label='Copywriting list', 
                                value=textarea_data_change(config.get("idle_time_task", "copywriting", "copy")), 
                                placeholder='Copywriting list, separated by line breaks; the copywriting is sent to the LLM for processing and the returned result is synthesized directly'
                            ).style("width:800px;").tooltip('Copywriting list, separated by line breaks; the copywriting is sent to the LLM for processing and the returned result is synthesized directly')
                        
                        with ui.row():
                            switch_idle_time_task_comment_enable = ui.switch('Danmaku-triggered LLM mode', value=config.get("idle_time_task", "comment", "enable")).style(switch_internal_css)
                            switch_idle_time_task_comment_random = ui.switch('Random danmaku', value=config.get("idle_time_task", "comment", "random")).style(switch_internal_css)
                            textarea_idle_time_task_comment_copy = ui.textarea(
                                label='Danmaku list', 
                                value=textarea_data_change(config.get("idle_time_task", "comment", "copy")), 
                                placeholder='Danmaku list, separated by line breaks; the content is sent to the LLM for processing and the returned result is synthesized directly'
                            ).style("width:800px;").tooltip('Danmaku list, separated by line breaks; the content is sent to the LLM for processing and the returned result is synthesized directly')
                        with ui.row():
                            switch_idle_time_task_local_audio_enable = ui.switch('Local audio mode', value=config.get("idle_time_task", "local_audio", "enable")).style(switch_internal_css)
                            switch_idle_time_task_local_audio_random = ui.switch('Random local audio', value=config.get("idle_time_task", "local_audio", "random")).style(switch_internal_css)
                            textarea_idle_time_task_local_audio_path = ui.textarea(
                                label='Local audio path list', 
                                value=textarea_data_change(config.get("idle_time_task", "local_audio", "path")), 
                                placeholder='Local audio path list; relative/absolute paths separated by line breaks; the audio files are put directly into the audio playback queue'
                            ).style("width:800px;").tooltip('Local audio path list; relative/absolute paths separated by line breaks; the audio files are put directly into the audio playback queue')

                if config.get("webui", "show_card", "common_config", "search_online"):      
                    with ui.card().style(card_css):
                        ui.label('Online search')
                        with ui.row():
                            switch_search_online_enable = ui.switch('Enable', value=config.get("search_online", "enable")).style(switch_internal_css) 
                            switch_search_online_keyword_enable = ui.switch('Keyword trigger', value=config.get("search_online", "keyword_enable")).style(switch_internal_css) 
                            textarea_search_online_before_keyword = ui.textarea(
                                label='Keyword prefix', 
                                placeholder='The prefix must carry any one of these strings to trigger online search\nFor example: configure [Web search:] then this will trigger: Web search:Hangzhou weather', 
                                value=textarea_data_change(config.get("search_online", "before_keyword"))
                            ).style("width:200px;").tooltip('The prefix must carry any one of these strings to trigger online search\nFor example: configure [Web search:] then this will trigger: Web search:Hangzhou weather')
                            
                            select_search_online_engine = ui.select(
                                label='Search engine',
                                options={'baidu': 'Baidu Search', 'google': 'Google Search'},
                                value=config.get("search_online", "engine")
                            ).style("width:100px;").tooltip('The search engine used')
                            input_search_online_engine_id = ui.input(label='Engine ID', value=config.get("search_online", "engine_id"), placeholder='Default: 1, modification not recommended').style("width:100px;").tooltip('A single engine may have multiple search methods; currently only Google has 2; modifying the default is not recommended')
                            input_search_online_count = ui.input(label='Number of articles to retrieve', value=config.get("search_online", "count"), placeholder='Default is 1, but sometimes the parsed article content may be empty; you can increase the number appropriately').style("width:100px;").tooltip('Default is 1, but sometimes the parsed article content may be empty; you can increase the number appropriately')
                            input_search_online_resp_template = ui.input(label='Result template', value=config.get("search_online", "resp_template"), placeholder='After retrieval, the data generates a question in this template format; do not delete the two {} variables, otherwise it will fail to run').style("width:500px;").tooltip('After retrieval, the data generates a question in this template format; do not delete the two {} variables, otherwise it will fail to run')
                            input_search_online_http_proxy = ui.input(
                                label='HTTP proxy address', 
                                value=config.get("search_online", "http_proxy"), 
                                placeholder='HTTP proxy address; configure this when a proxy is needed.',
                                validation={
                                    'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                                }
                            ).style("width:200px;").tooltip('HTTP proxy address; configure this when a proxy is needed.')
                            input_search_online_https_proxy = ui.input(
                                label='HTTPS proxy address', 
                                value=config.get("search_online", "https_proxy"), 
                                placeholder='HTTPS proxy address; configure this when a proxy is needed.',
                                validation={
                                    'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                                }
                            ).style("width:200px;").tooltip('HTTPS proxy address; configure this when a proxy is needed.')
                        
                if config.get("webui", "show_card", "common_config", "trends_copywriting"):        
                    with ui.card().style(card_css):
                        ui.label('Dynamic copywriting')
                        with ui.row():
                            switch_trends_copywriting_enable = ui.switch('Enable', value=config.get("trends_copywriting", "enable")).style(switch_internal_css)
                            select_trends_copywriting_llm_type = ui.select(
                                label='LLM type',
                                options=chat_type_options,
                                value=config.get("trends_copywriting", "llm_type")
                            ).style("width:200px;")
                            switch_trends_copywriting_random_play = ui.switch('Random play', value=config.get("trends_copywriting", "random_play")).style(switch_internal_css)
                            input_trends_copywriting_play_interval = ui.input(label='Copywriting play interval', value=config.get("trends_copywriting", "play_interval"), placeholder='Play interval between copywriting items (seconds)').style("width:200px;").tooltip('Play interval between copywriting items (seconds)')
                        
                        with ui.row():
                            input_trends_copywriting_index = ui.input(label='Copywriting index', value="", placeholder='Order number of the copywriting group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer').tooltip('Order number of the copywriting group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                            button_trends_copywriting_add = ui.button('Add copywriting group', on_click=trends_copywriting_add, color=button_internal_color).style(button_internal_css)
                            button_trends_copywriting_del = ui.button('Delete copywriting group', on_click=lambda: trends_copywriting_del(input_trends_copywriting_index.value), color=button_internal_color).style(button_internal_css)
                        
                        trends_copywriting_copywriting_var = {}
                        trends_copywriting_config_card = ui.card()
                        for index, trends_copywriting_copywriting in enumerate(config.get("trends_copywriting", "copywriting")):
                            with trends_copywriting_config_card.style(card_css):
                                with ui.row():
                                    trends_copywriting_copywriting_var[str(3 * index)] = ui.input(label=f"Copywriting path#{index + 1}", value=trends_copywriting_copywriting["folder_path"], placeholder='Folder path where copywriting files are stored').style("width:200px;").tooltip('Folder path where copywriting files are stored')
                                    trends_copywriting_copywriting_var[str(3 * index + 1)] = ui.switch(text=f"Prompt conversion#{index + 1}", value=trends_copywriting_copywriting["prompt_change_enable"])
                                    trends_copywriting_copywriting_var[str(3 * index + 2)] = ui.input(label=f"Prompt conversion content#{index + 1}", value=trends_copywriting_copywriting["prompt_change_content"], placeholder='Use this prompt to convert the copywriting content before synthesis; the LLM used is the one configured as the chat type').style("width:500px;").tooltip('Use this prompt to convert the copywriting content before synthesis; the LLM used is the one configured as the chat type')
                
                if config.get("webui", "show_card", "common_config", "key_mapping"):  
                    with ui.card().style(card_css):
                        ui.label('Key/Copywriting/Audio/Serial/Image mapping')
                        with ui.row():
                            switch_key_mapping_enable = ui.switch('Enable', value=config.get("key_mapping", "enable")).style(switch_internal_css)
                            input_key_mapping_start_cmd = ui.input(
                                label='Command prefix', 
                                value=config.get("key_mapping", "start_cmd"), 
                                placeholder='To trigger this feature, the command must start with this string, otherwise it will not be parsed as a key mapping command'
                            ).style("width:200px;").tooltip('To trigger this feature, the command must start with this string, otherwise it will not be parsed as a key mapping command')
                            select_key_mapping_type = ui.select(
                                label='Capture type',
                                options={'Comment': 'Comment', 'Reply': 'Reply', 'Comment + Reply': 'Comment + Reply'},
                                value=config.get("key_mapping", "type")
                            ).style("width:200px").tooltip('What type of data triggers the function of this section')
                        with ui.row():
                            
                            select_key_mapping_key_trigger_type = ui.select(
                                label='Key trigger type',
                                options={'Disabled': 'Disabled', 'Keywords': 'Keywords', 'Gift': 'Gift', 'Keywords + Gift': 'Keywords + Gift'},
                                value=config.get("key_mapping", "key_trigger_type")
                            ).style("width:120px").tooltip('What type of data triggers key mapping')
                            switch_key_mapping_key_single_sentence_trigger_once_enable = ui.switch('Trigger once per sentence (key)', value=config.get("key_mapping", "key_single_sentence_trigger_once")).style(switch_internal_css).tooltip('Whether a single sentence triggers key mapping only once, since a sentence may contain multiple keywords and trigger multiple times')
                            select_key_mapping_copywriting_trigger_type = ui.select(
                                label='Copywriting trigger type',
                                options={'Disabled': 'Disabled', 'Keywords': 'Keywords', 'Gift': 'Gift', 'Keywords + Gift': 'Keywords + Gift'},
                                value=config.get("key_mapping", "copywriting_trigger_type")
                            ).style("width:120px").tooltip('What type of data triggers copywriting mapping')
                            switch_key_mapping_copywriting_single_sentence_trigger_once_enable = ui.switch('Trigger once per sentence (copywriting)', value=config.get("key_mapping", "copywriting_single_sentence_trigger_once")).style(switch_internal_css).tooltip('Whether a single sentence triggers copywriting mapping only once, since a sentence may contain multiple keywords and trigger multiple times')
                            select_key_mapping_local_audio_trigger_type = ui.select(
                                label='Local audio trigger type',
                                options={'Disabled': 'Disabled', 'Keywords': 'Keywords', 'Gift': 'Gift', 'Keywords + Gift': 'Keywords + Gift'},
                                value=config.get("key_mapping", "local_audio_trigger_type")
                            ).style("width:120px").tooltip('What type of data triggers local audio mapping')
                            switch_key_mapping_local_audio_single_sentence_trigger_once_enable = ui.switch('Trigger once per sentence (copywriting)', value=config.get("key_mapping", "local_audio_single_sentence_trigger_once")).style(switch_internal_css).tooltip('Whether a single sentence triggers local audio mapping only once, since a sentence may contain multiple keywords and trigger multiple times')
                            select_key_mapping_serial_trigger_type = ui.select(
                                label='Serial trigger type',
                                options={'Disabled': 'Disabled', 'Keywords': 'Keywords', 'Gift': 'Gift', 'Keywords + Gift': 'Keywords + Gift'},
                                value=config.get("key_mapping", "serial_trigger_type")
                            ).style("width:120px").tooltip('What type of data triggers copywriting mapping')
                            switch_key_mapping_serial_single_sentence_trigger_once_enable = ui.switch('Trigger once per sentence (serial)', value=config.get("key_mapping", "serial_single_sentence_trigger_once")).style(switch_internal_css).tooltip('Whether a single sentence triggers copywriting mapping only once, since a sentence may contain multiple keywords and trigger multiple times')
                            select_key_mapping_img_path_trigger_type = ui.select(
                                label='Image trigger type',
                                options={'Disabled': 'Disabled', 'Keywords': 'Keywords', 'Gift': 'Gift', 'Keywords + Gift': 'Keywords + Gift'},
                                value=config.get("key_mapping", "img_path_trigger_type")
                            ).style("width:120px").tooltip('What type of data triggers copywriting mapping')
                            switch_key_mapping_img_path_single_sentence_trigger_once_enable = ui.switch('Trigger once per sentence (image display)', value=config.get("key_mapping", "img_path_single_sentence_trigger_once")).style(switch_internal_css).tooltip('Whether a single sentence triggers copywriting mapping only once, since a sentence may contain multiple keywords and trigger multiple times')
                            
                        with ui.row():
                            input_key_mapping_index = ui.input(label='Config index', value="", placeholder='Order number of the config group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer').tooltip('Order number of the config group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                            button_key_mapping_add = ui.button('Add config group', on_click=key_mapping_add, color=button_internal_color).style(button_internal_css)
                            button_key_mapping_del = ui.button('Delete config group', on_click=lambda: key_mapping_del(input_key_mapping_index.value), color=button_internal_color).style(button_internal_css)
                        
                        
                        key_mapping_config_var = {}
                        key_mapping_config_card = ui.card()
                        for index, key_mapping_config in enumerate(config.get("key_mapping", "config")):
                            with key_mapping_config_card.style(card_css):
                                with ui.row():
                                    num = 9
                                    key_mapping_config_var[str(num * index)] = ui.textarea(label=f"Keywords#{index + 1}", value=textarea_data_change(key_mapping_config["keywords"]), placeholder='Enter the trigger keywords here; separate multiple ones with line breaks').style("width:100px;").tooltip('Enter the trigger keywords here; separate multiple ones with line breaks')
                                    key_mapping_config_var[str(num * index + 1)] = ui.textarea(label=f"Gift#{index + 1}", value=textarea_data_change(key_mapping_config["gift"]), placeholder='Enter the trigger gift names here; separate multiple ones with line breaks').style("width:100px;").tooltip('Enter the trigger gift names here; separate multiple ones with line breaks')
                                    key_mapping_config_var[str(num * index + 2)] = ui.textarea(label=f"Key#{index + 1}", value=textarea_data_change(key_mapping_config["keys"]), placeholder='Enter the keys you want to map here; separate multiple keys with line breaks (key names follow pyautogui rules)').style("width:100px;").tooltip('Enter the keys you want to map here; separate multiple keys with line breaks (key names follow pyautogui rules)')
                                    key_mapping_config_var[str(num * index + 3)] = ui.input(label=f"Similarity#{index + 1}", value=key_mapping_config["similarity"], placeholder='Similarity between the keywords and the user input; default 1 means 100%').style("width:50px;").tooltip('Similarity between the keywords and the user input; default 1 means 100%')
                                    key_mapping_config_var[str(num * index + 4)] = ui.textarea(label=f"Copywriting#{index + 1}", value=textarea_data_change(key_mapping_config["copywriting"]), placeholder='Enter the copywriting content to synthesize after triggering; separate multiple ones with line breaks').style("width:300px;").tooltip('Enter the copywriting content to synthesize after triggering; separate multiple ones with line breaks')
                                    key_mapping_config_var[str(num * index + 5)] = ui.textarea(label=f"Local audio#{index + 1}", value=textarea_data_change(key_mapping_config["local_audio"]), placeholder='Enter the local audio paths to play after triggering; separate multiple ones with line breaks').style("width:300px;").tooltip('Enter the local audio paths to play after triggering; separate multiple ones with line breaks')
                                    key_mapping_config_var[str(num * index + 6)] = ui.input(label=f"Serial port name#{index + 1}", value=key_mapping_config["serial_name"], placeholder='e.g. COM1').style("width:100px;").tooltip('Serial port name configured on the serial page, e.g. COM1')
                                    key_mapping_config_var[str(num * index + 7)] = ui.textarea(label=f"Serial send content#{index + 1}", value=textarea_data_change(key_mapping_config["serial_send_data"]), placeholder='Separate multiple ones with line breaks. ASCII example: open led\nHEX example (2-character hexadecimal): 313233').style("width:300px;").tooltip('Enter the data to send to the serial port here; the data type is determined by the serial page settings; separate multiple ones with line breaks')
                                    key_mapping_config_var[str(num * index + 8)] = ui.textarea(label=f"Image path#{index + 1}", value=textarea_data_change(key_mapping_config["img_path"]), placeholder='Separate multiple ones with line breaks; absolute or relative paths are supported; pay attention to the path slashes').style("width:300px;").tooltip('Enter image paths here; separate multiple ones with line breaks. Displayed randomly by default')
                                    
                                    # with ui.card().style(card_css):
                                    #     key_mapping_config_var[str(6 * index + 5)] = ui.textarea(label=f"Serial port number#{index + 1}", value=textarea_data_change(key_mapping_config["serial_name"]), placeholder='e.g. COM1').style("width:100px;").tooltip('Name of the serial port to send to')
                                    #     key_mapping_config_var[str(6 * index + 5)] = ui.textarea(label=f"Send data#{index + 1}", value=key_mapping_config["serial_data"], placeholder='Fill in according to the type; separate multiple ones with line breaks').style("width:300px;").tooltip('Fill in according to the type; separate multiple ones with line breaks')
                
            with ui.expansion('Auxiliary Software Integration', icon="extension", value=True).classes('w-full'):

                with ui.card().style(card_css):
                    ui.label("Luoxi Live Danmaku Assistant")
                    with ui.row():
                        switch_luoxi_project_Live_Comment_Assistant_enable = ui.switch('Enable', value=config.get("luoxi_project", "Live_Comment_Assistant", "enable")).style(switch_internal_css)
                        select_luoxi_project_Live_Comment_Assistant_version = ui.select(
                            label='Integration version',
                            options={'V0.1.x': 'V0.1.x'},
                            value=config.get("luoxi_project", "Live_Comment_Assistant", "version")
                        ).style("width:100px;").tooltip('Version, since different versions may have interface changes')
                        input_luoxi_project_Live_Comment_Assistant_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("luoxi_project", "Live_Comment_Assistant", "api_ip_port"), 
                            placeholder='Luoxi Live Danmaku Assistant API address'
                        ).style("width:200px;").tooltip('Luoxi Live Danmaku Assistant API address')
                
                    with ui.card().style(card_css):
                        ui.label("Trigger type")
                        with ui.row():    
                            # The type list comes from the type values supported by audio synthesis
                            luoxi_project_Live_Comment_Assistant_type_list = [
                                "comment",
                                "comment_reply", 
                                "idle_time_task", 
                                "entrance_reply", 
                                "follow_reply", 
                                "gift_reply", 
                                "reread", 
                                "schedule",
                                "integral",
                                "key_mapping_copywriting"
                            ]
                            luoxi_project_Live_Comment_Assistant_type_mapping = {
                                "comment": "Danmaku message",
                                "comment_reply": "Danmaku reply",
                                "idle_time_task": "Idle-time task",
                                "entrance_reply": "Entrance reply",
                                "follow_reply": "Follow reply",
                                "gift_reply": "Gift reply",
                                "reread": "Repeat",
                                "schedule": "Scheduled tasks",
                                "integral": "Points message",
                                "key_mapping_copywriting": "Key mapping - copywriting"
                            }
                            luoxi_project_Live_Comment_Assistant_type_var = {}
                            
                            for index, luoxi_project_Live_Comment_Assistant_type in enumerate(luoxi_project_Live_Comment_Assistant_type_list):
                                if luoxi_project_Live_Comment_Assistant_type in config.get("luoxi_project", "Live_Comment_Assistant", "type"):
                                    luoxi_project_Live_Comment_Assistant_type_var[str(index)] = ui.checkbox(
                                        text=luoxi_project_Live_Comment_Assistant_type_mapping[luoxi_project_Live_Comment_Assistant_type], 
                                        value=True
                                    )
                                else:
                                    luoxi_project_Live_Comment_Assistant_type_var[str(index)] = ui.checkbox(
                                        text=luoxi_project_Live_Comment_Assistant_type_mapping[luoxi_project_Live_Comment_Assistant_type], 
                                        value=False
                                    )
                    with ui.card().style(card_css):
                        ui.label("Trigger position")
                        with ui.row(): 
                            luoxi_project_Live_Comment_Assistant_trigger_position_list = [
                                "On message created", 
                                "When the audio is played",
                            ]
                            luoxi_project_Live_Comment_Assistant_trigger_position_mapping = {
                                "On message created": "On message created",
                                "When the audio is played": "When the audio is played",
                            }
                            luoxi_project_Live_Comment_Assistant_trigger_position_var = {}
                            
                            for index, luoxi_project_Live_Comment_Assistant_trigger_position in enumerate(luoxi_project_Live_Comment_Assistant_trigger_position_list):
                                if luoxi_project_Live_Comment_Assistant_trigger_position in config.get("luoxi_project", "Live_Comment_Assistant", "trigger_position"):
                                    luoxi_project_Live_Comment_Assistant_trigger_position_var[str(index)] = ui.checkbox(
                                        text=luoxi_project_Live_Comment_Assistant_trigger_position_mapping[luoxi_project_Live_Comment_Assistant_trigger_position], 
                                        value=True
                                    )
                                else:
                                    luoxi_project_Live_Comment_Assistant_trigger_position_var[str(index)] = ui.checkbox(
                                        text=luoxi_project_Live_Comment_Assistant_trigger_position_mapping[luoxi_project_Live_Comment_Assistant_trigger_position], 
                                        value=False
                                    )        
                

                if config.get("webui", "show_card", "common_config", "sd"):      
                    with ui.card().style(card_css):
                        ui.label('Stable Diffusion')
                        with ui.row():
                            switch_sd_enable = ui.switch('Enable', value=config.get("sd", "enable")).style(switch_internal_css) 
                            select_sd_translate_type = ui.select(
                                label='Translation type',
                                options={'none': 'Disabled', 'baidu': 'Baidu Translate', 'google': 'Google Translate'},
                                value=config.get("sd", "translate_type")
                            ).style("width:100px;").tooltip('For the triggered drawing command, use the Translate page config to translate it before passing it to SD for drawing')
                            select_sd_prompt_llm_type = ui.select(
                                label='LLM type',
                                options=chat_type_options,
                                value=config.get("sd", "prompt_llm", "type")
                            ).style("width:100px;")
                            input_sd_prompt_llm_before_prompt = ui.input(label='Prompt prefix', value=config.get("sd", "prompt_llm", "before_prompt"), placeholder='LLM prompt prefix').style("width:300px;")
                            input_sd_prompt_llm_after_prompt = ui.input(label='Prompt suffix', value=config.get("sd", "prompt_llm", "after_prompt"), placeholder='LLM prompt suffix').style("width:300px;")
                        with ui.row(): 
                            input_sd_trigger = ui.input(label='Danmaku trigger prefix', value=config.get("sd", "trigger"), placeholder='Trigger keyword (triggered at the start of the danmaku)').style("width:200px;")
                            input_sd_ip = ui.input(label='IP address', value=config.get("sd", "ip"), placeholder='IP address the service runs on').style("width:200px;")
                            input_sd_port = ui.input(label='Port', value=config.get("sd", "port"), placeholder='Port the service runs on').style("width:100px;")
                            input_sd_negative_prompt = ui.input(label='Negative prompt', value=config.get("sd", "negative_prompt"), placeholder='Negative text prompt, used to specify content that contradicts or is opposite to the generated image').style("width:200px;")
                            input_sd_seed = ui.input(label='Random seed', value=config.get("sd", "seed"), placeholder='Random seed, used to control the randomness of the generation process. You can set an integer value to get reproducible results.').style("width:100px;")
                            textarea_sd_styles = ui.textarea(label='Image style', placeholder='Style list, used to specify the style of the generated image. It can contain multiple styles, e.g. [“anime”, “portrait”]', value=textarea_data_change(config.get("sd", "styles"))).style("width:200px;")
                        with ui.row():
                            input_sd_cfg_scale = ui.input(label='Prompt relevance (CFG scale)', value=config.get("sd", "cfg_scale"), placeholder='Prompt relevance, Classifier Free Guidance Scale - how closely the image should follow the prompt - lower values produce more creative results.').style("width:100px;")
                            input_sd_steps = ui.input(label='Generation steps', value=config.get("sd", "steps"), placeholder='Number of steps for image generation, used to control the precision of generation.').style("width:100px;") 
                            input_sd_hr_resize_x = ui.input(label='Image horizontal pixels', value=config.get("sd", "hr_resize_x"), placeholder='Horizontal size of the generated image.').style("width:100px;")
                            input_sd_hr_resize_y = ui.input(label='Image vertical pixels', value=config.get("sd", "hr_resize_y"), placeholder='Vertical size of the generated image.').style("width:100px;")
                            input_sd_denoising_strength = ui.input(label='Denoising strength', value=config.get("sd", "denoising_strength"), placeholder='Denoising strength, used to control the noise in the generated image.').style("width:100px;")
                        with ui.row():
                            switch_sd_enable_hr = ui.switch('High-resolution generation', value=config.get("sd", "enable_hr")).style(switch_internal_css)
                            input_sd_hr_scale = ui.input(label='High-res scale factor', value=config.get("sd", "hr_scale"), placeholder='High-res scale factor, used to specify the high-resolution scaling level of the generated image.').style("width:200px;")
                            input_sd_hr_second_pass_steps = ui.input(label='High-res second pass steps', value=config.get("sd", "hr_second_pass_steps"), placeholder='Number of second-pass steps for high-resolution generation.').style("width:200px;")
                            switch_sd_save_enable = ui.switch('Save images locally', value=config.get("sd", "save_enable")).style(switch_internal_css)
                            switch_sd_loop_cover = ui.switch('Loop-overwrite local images', value=config.get("sd", "loop_cover")).style(switch_internal_css)
                            input_sd_save_path = ui.input(label='Image save path', value=config.get("sd", "save_path"), placeholder='Path where generated images are stored; modification is not recommended').style("width:200px;")
                
                if config.get("webui", "show_card", "common_config", "web_captions_printer"):
                    with ui.card().style(card_css):
                        ui.label('Web captions printer')
                        with ui.grid(columns=2):
                            switch_web_captions_printer_enable = ui.switch('Enable', value=config.get("web_captions_printer", "enable")).style(switch_internal_css).tooltip("If you use audio player for audio playback and have enabled its web captions printer feature,\nplease do not enable this one, since that would be redundant")
                            input_web_captions_printer_api_ip_port = ui.input(
                                label='API address', 
                                value=config.get("web_captions_printer", "api_ip_port"), 
                                placeholder='API address of the web captions printer; just http://ip:port is enough',
                                validation={
                                    'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                                }
                            ).style("width:200px;").tooltip('API address of the web captions printer; just http://ip:port is enough')


            with ui.expansion('Advanced Features', icon="view_in_ar", value=True).classes('w-full'):
                if config.get("webui", "show_card", "common_config", "log"):
                    with ui.card().style(card_css):
                        ui.label('Log')
                        with ui.grid(columns=4):
                            switch_captions_enable = ui.switch('Enable', value=config.get("captions", "enable")).style(switch_internal_css)

                            select_comment_log_type = ui.select(
                                label='Danmaku log type',
                                options={'Q&A': 'Q&A', 'Question': 'Question', 'Answer': 'Answer', 'No logging': 'No logging'},
                                value=config.get("comment_log_type")
                            )

                            input_captions_file_path = ui.input(label='Caption log path', value=config.get("captions", "file_path"), placeholder='Caption log storage path').style("width:200px;")
                            input_captions_raw_file_path = ui.input(label='Original caption log path', placeholder='Original caption log storage path',
                                                                value=config.get("captions", "raw_file_path")).style("width:200px;")

                if config.get("webui", "show_card", "common_config", "database"):  
                    with ui.card().style(card_css):
                        ui.label('Database')
                        with ui.grid(columns=4):
                            switch_database_comment_enable = ui.switch('Danmaku log', value=config.get("database", "comment_enable")).style(switch_internal_css)
                            switch_database_entrance_enable = ui.switch('Entrance log', value=config.get("database", "entrance_enable")).style(switch_internal_css)
                            switch_database_gift_enable = ui.switch('Gift log', value=config.get("database", "gift_enable")).style(switch_internal_css)
                            input_database_path = ui.input(label='Database path', value=config.get("database", "path"), placeholder='Database file storage path').style("width:200px;")
                            
                              
                if config.get("webui", "show_card", "common_config", "custom_cmd"):  
                    with ui.card().style(card_css):
                        ui.label('Custom commands')
                        with ui.row():
                            switch_custom_cmd_enable = ui.switch('Enable', value=config.get("custom_cmd", "enable")).style(switch_internal_css)
                            select_custom_cmd_type = ui.select(
                                label='Type',
                                options={'Comment': 'Comment'},
                                value=config.get("custom_cmd", "type")
                            ).style("width:200px")
                        with ui.row():
                            input_custom_cmd_index = ui.input(label='Config index', value="", placeholder='Order number of the config group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                            button_custom_cmd_add = ui.button('Add config group', on_click=custom_cmd_add, color=button_internal_color).style(button_internal_css)
                            button_custom_cmd_del = ui.button('Delete config group', on_click=lambda: custom_cmd_del(input_custom_cmd_index.value), color=button_internal_color).style(button_internal_css)
                        
                        custom_cmd_config_var = {}
                        custom_cmd_config_card = ui.card()
                        for index, custom_cmd_config in enumerate(config.get("custom_cmd", "config")):
                            with custom_cmd_config_card.style(card_css):
                                with ui.row():
                                    custom_cmd_config_var[str(7 * index)] = ui.textarea(label=f"Keywords#{index + 1}", value=textarea_data_change(custom_cmd_config["keywords"]), placeholder='Enter the trigger keywords here; separate multiple ones with line breaks').style("width:200px;")
                                    custom_cmd_config_var[str(7 * index + 1)] = ui.input(label=f"Similarity#{index + 1}", value=custom_cmd_config["similarity"], placeholder='Similarity between the keywords and the user input; default 1 means 100%').style("width:100px;")
                                    custom_cmd_config_var[str(7 * index + 2)] = ui.textarea(
                                        label=f"API URL#{index + 1}", 
                                        value=custom_cmd_config["api_url"], 
                                        placeholder='API link for sending HTTP requests', 
                                        validation={
                                            'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                                        }
                                    ).style("width:300px;").tooltip('API link for sending HTTP requests')
                                    custom_cmd_config_var[str(7 * index + 3)] = ui.select(label=f"API type#{index + 1}", value=custom_cmd_config["api_type"], options={"GET": "GET"}).style("width:100px;")
                                    custom_cmd_config_var[str(7 * index + 4)] = ui.select(label=f"Response data type#{index + 1}", value=custom_cmd_config["resp_data_type"], options={"json": "json", "content": "content"}).style("width:150px;")
                                    custom_cmd_config_var[str(7 * index + 5)] = ui.textarea(label=f"Data parsing (executed with eval)#{index + 1}", value=custom_cmd_config["data_analysis"], placeholder='Data parsing; do not modify the resp variable arbitrarily, it is used to parse the final returned data').style("width:200px;").tooltip('Data parsing; do not modify the resp variable arbitrarily, it is used to parse the final returned data')
                                    custom_cmd_config_var[str(7 * index + 6)] = ui.textarea(label=f"Response content template#{index + 1}", value=custom_cmd_config["resp_template"], placeholder='Do not delete the data variable arbitrarily; dynamic variables are supported; it will finally be merged into the complete content for audio synthesis').style("width:300px;").tooltip("Do not delete the data variable arbitrarily; dynamic variables are supported; it will finally be merged into the complete content for audio synthesis")


                if config.get("webui", "show_card", "common_config", "trends_config"):  
                    with ui.card().style(card_css):
                        ui.label('Dynamic config')
                        with ui.row():
                            switch_trends_config_enable = ui.switch('Enable', value=config.get("trends_config", "enable")).style(switch_internal_css)
                        trends_config_path_var = {}
                        for index, trends_config_path in enumerate(config.get("trends_config", "path")):
                            with ui.grid(columns=2):
                                trends_config_path_var[str(2 * index)] = ui.input(label="Online count range", value=trends_config_path["online_num"], placeholder='Online count range, separated by a hyphen, e.g. 0-10').style("width:200px;").tooltip("Online count range, separated by a hyphen, e.g. 0-10")
                                trends_config_path_var[str(2 * index + 1)] = ui.input(label="Config path", value=trends_config_path["path"], placeholder='Enter the path of the config file to load here').style("width:200px;").tooltip("Enter the path of the config file to load here")
                
                if config.get("webui", "show_card", "common_config", "abnormal_alarm"): 
                    with ui.card().style(card_css):
                        ui.label('Abnormal alarm')
                        with ui.row():
                            switch_abnormal_alarm_platform_enable = ui.switch('Enable platform alarm', value=config.get("abnormal_alarm", "platform", "enable")).style(switch_internal_css)
                            select_abnormal_alarm_platform_type = ui.select(
                                label='Type',
                                options={'local_audio': 'Local audio'},
                                value=config.get("abnormal_alarm", "platform", "type")
                            )
                            input_abnormal_alarm_platform_start_alarm_error_num = ui.input(label='Error count to start alarm', value=config.get("abnormal_alarm", "platform", "start_alarm_error_num"), placeholder='Error count at which abnormal alarms start; the alarm triggers once it is exceeded').style("width:100px;")
                            input_abnormal_alarm_platform_auto_restart_error_num = ui.input(label='Error count for auto restart', value=config.get("abnormal_alarm", "platform", "auto_restart_error_num"), placeholder='Remember to enable the “Auto run” feature first. Error count for auto restart; once exceeded, the webui is restarted automatically.').style("width:100px;")
                            input_abnormal_alarm_platform_local_audio_path = ui.input(label='Local audio path', value=config.get("abnormal_alarm", "platform", "local_audio_path"), placeholder='File path of the locally stored audio (can be multiple audio files, one picked at random)').style("width:300px;")
                        with ui.row():
                            switch_abnormal_alarm_llm_enable = ui.switch('Enable LLM alarm', value=config.get("abnormal_alarm", "llm", "enable")).style(switch_internal_css)
                            select_abnormal_alarm_llm_type = ui.select(
                                label='Type',
                                options={'local_audio': 'Local audio'},
                                value=config.get("abnormal_alarm", "llm", "type")
                            )
                            input_abnormal_alarm_llm_start_alarm_error_num = ui.input(label='Error count to start alarm', value=config.get("abnormal_alarm", "llm", "start_alarm_error_num"), placeholder='Error count at which abnormal alarms start; the alarm triggers once it is exceeded').style("width:100px;")
                            input_abnormal_alarm_llm_auto_restart_error_num = ui.input(label='Error count for auto restart', value=config.get("abnormal_alarm", "llm", "auto_restart_error_num"), placeholder='Remember to enable the “Auto run” feature first. Error count for auto restart; once exceeded, the webui is restarted automatically.').style("width:100px;")
                            input_abnormal_alarm_llm_local_audio_path = ui.input(label='Local audio path', value=config.get("abnormal_alarm", "llm", "local_audio_path"), placeholder='File path of the locally stored audio (can be multiple audio files, one picked at random)').style("width:300px;")
                        with ui.row():
                            switch_abnormal_alarm_tts_enable = ui.switch('Enable TTS alarm', value=config.get("abnormal_alarm", "tts", "enable")).style(switch_internal_css)
                            select_abnormal_alarm_tts_type = ui.select(
                                label='Type',
                                options={'local_audio': 'Local audio'},
                                value=config.get("abnormal_alarm", "tts", "type")
                            )
                            input_abnormal_alarm_tts_start_alarm_error_num = ui.input(label='Error count to start alarm', value=config.get("abnormal_alarm", "tts", "start_alarm_error_num"), placeholder='Error count at which abnormal alarms start; the alarm triggers once it is exceeded').style("width:100px;")
                            input_abnormal_alarm_tts_auto_restart_error_num = ui.input(label='Error count for auto restart', value=config.get("abnormal_alarm", "tts", "auto_restart_error_num"), placeholder='Remember to enable the “Auto run” feature first. Error count for auto restart; once exceeded, the webui is restarted automatically.').style("width:100px;")
                            input_abnormal_alarm_tts_local_audio_path = ui.input(label='Local audio path', value=config.get("abnormal_alarm", "tts", "local_audio_path"), placeholder='File path of the locally stored audio (can be multiple audio files, one picked at random)').style("width:300px;")
                        with ui.row():
                            switch_abnormal_alarm_svc_enable = ui.switch('Enable SVC alarm', value=config.get("abnormal_alarm", "svc", "enable")).style(switch_internal_css)
                            select_abnormal_alarm_svc_type = ui.select(
                                label='Type',
                                options={'local_audio': 'Local audio'},
                                value=config.get("abnormal_alarm", "svc", "type")
                            )
                            input_abnormal_alarm_svc_start_alarm_error_num = ui.input(label='Error count to start alarm', value=config.get("abnormal_alarm", "svc", "start_alarm_error_num"), placeholder='Error count at which abnormal alarms start; the alarm triggers once it is exceeded').style("width:100px;")
                            input_abnormal_alarm_svc_auto_restart_error_num = ui.input(label='Error count for auto restart', value=config.get("abnormal_alarm", "svc", "auto_restart_error_num"), placeholder='Remember to enable the “Auto run” feature first. Error count for auto restart; once exceeded, the webui is restarted automatically.').style("width:100px;")
                            input_abnormal_alarm_svc_local_audio_path = ui.input(label='Local audio path', value=config.get("abnormal_alarm", "svc", "local_audio_path"), placeholder='File path of the locally stored audio (can be multiple audio files, one picked at random)').style("width:300px;")
                        with ui.row():
                            switch_abnormal_alarm_visual_body_enable = ui.switch('Enable virtual body alarm', value=config.get("abnormal_alarm", "visual_body", "enable")).style(switch_internal_css)
                            select_abnormal_alarm_visual_body_type = ui.select(
                                label='Type',
                                options={'local_audio': 'Local audio'},
                                value=config.get("abnormal_alarm", "visual_body", "type")
                            )
                            input_abnormal_alarm_visual_body_start_alarm_error_num = ui.input(label='Error count to start alarm', value=config.get("abnormal_alarm", "visual_body", "start_alarm_error_num"), placeholder='Error count at which abnormal alarms start; the alarm triggers once it is exceeded').style("width:100px;")
                            input_abnormal_alarm_visual_body_auto_restart_error_num = ui.input(label='Error count for auto restart', value=config.get("abnormal_alarm", "visual_body", "auto_restart_error_num"), placeholder='Remember to enable the “Auto run” feature first. Error count for auto restart; once exceeded, the webui is restarted automatically.').style("width:100px;")
                            input_abnormal_alarm_visual_body_local_audio_path = ui.input(label='Local audio path', value=config.get("abnormal_alarm", "visual_body", "local_audio_path"), placeholder='File path of the locally stored audio (can be multiple audio files, one picked at random)').style("width:300px;")
                        with ui.row():
                            switch_abnormal_alarm_other_enable = ui.switch('Enable other alarms', value=config.get("abnormal_alarm", "other", "enable")).style(switch_internal_css)
                            select_abnormal_alarm_other_type = ui.select(
                                label='Type',
                                options={'local_audio': 'Local audio'},
                                value=config.get("abnormal_alarm", "other", "type")
                            )
                            input_abnormal_alarm_other_start_alarm_error_num = ui.input(label='Error count to start alarm', value=config.get("abnormal_alarm", "other", "start_alarm_error_num"), placeholder='Error count at which abnormal alarms start; the alarm triggers once it is exceeded').style("width:100px;")
                            input_abnormal_alarm_other_auto_restart_error_num = ui.input(label='Error count for auto restart', value=config.get("abnormal_alarm", "other", "auto_restart_error_num"), placeholder='Remember to enable the “Auto run” feature first. Error count for auto restart; once exceeded, the webui is restarted automatically.').style("width:100px;")
                            input_abnormal_alarm_other_local_audio_path = ui.input(label='Local audio path', value=config.get("abnormal_alarm", "other", "local_audio_path"), placeholder='File path of the locally stored audio (can be multiple audio files, one picked at random)').style("width:300px;")
                        
                if config.get("webui", "show_card", "common_config", "coordination_program"):
                    with ui.expansion('Linked programs', icon="settings", value=True).classes('w-full'):
                        with ui.row():
                            input_coordination_program_index = ui.input(label='Config index', value="", placeholder='Order number of the config group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                            button_coordination_program_add = ui.button('Add config group', on_click=coordination_program_add, color=button_internal_color).style(button_internal_css)
                            button_coordination_program_del = ui.button('Delete config group', on_click=lambda: coordination_program_del(input_coordination_program_index.value), color=button_internal_color).style(button_internal_css)
                        
                        coordination_program_var = {}
                        coordination_program_config_card = ui.card()
                        for index, coordination_program in enumerate(config.get("coordination_program")):
                            with coordination_program_config_card.style(card_css):
                                with ui.row():
                                    coordination_program_var[str(4 * index)] = ui.switch(f'Enable#{index + 1}', value=coordination_program["enable"]).style(switch_internal_css)
                                    coordination_program_var[str(4 * index + 1)] = ui.input(label=f"Program name#{index + 1}", value=coordination_program["name"], placeholder='Give your program a name, and do not use special characters!').style("width:200px;")
                                    coordination_program_var[str(4 * index + 2)] = ui.input(label=f"Executable#{index + 1}", value=coordination_program["executable"], placeholder='Path to the executable, preferably an absolute path, e.g. for a python program').style("width:400px;")
                                    coordination_program_var[str(4 * index + 3)] = ui.textarea(label=f'Parameters#{index + 1}', value=textarea_data_change(coordination_program["parameters"]), placeholder='Parameters; multiple parameters can be passed, separated by line breaks, e.g. the path of the program to launch, arguments carried by the command, etc.').style("width:500px;")
                

        with ui.tab_panel(llm_page).style(tab_panel_css):
            if config.get("webui", "show_card", "llm", "chatgpt"):
                with ui.card().style(card_css):
                    ui.label("ChatGPT | Wenda | ChatGLM3 | Kimi Chat | Ollama | One-API and other OpenAI-compatible API models ")
                    with ui.row():
                        input_openai_api = ui.input(
                            label='API address', 
                            placeholder='API Endpoint (Proxy Supported)', 
                            value=config.get("openai", "api"),
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;")
                        textarea_openai_api_key = ui.textarea(label='API Key', placeholder='API Key, Proxy Supported', value=textarea_data_change(config.get("openai", "api_key"))).style("width:400px;")
                        button_openai_test = ui.button('Test', on_click=lambda: test_openai_key(), color=button_bottom_color).style(button_bottom_css)
                    with ui.row():
                        chatgpt_models = [
                            "gpt-3.5-turbo",
                            "gpt-3.5-turbo-instruct",
                            "gpt-3.5-turbo-0125",
                            "gpt-4",
                            "gpt-4-turbo-preview",
                            "gpt-4-0125-preview",
                            "gpt-4o",
                            "gpt-4o-mini",
                            "text-embedding-3-large",
                            "text-embedding-3-small",
                            "text-davinci-003",
                            "rwkv",
                            "chatglm3-6b",
                            "moonshot-v1-8k",
                            "gemma:2b",
                            "qwen",
                            "qwen:1.8b-chat"
                        ]
                        # Insert the value configured by the user into the list (if it does not exist)
                        if config.get("chatgpt", "model") not in chatgpt_models:
                            chatgpt_models.append(config.get("chatgpt", "model"))
                        data_json = {}
                        for line in chatgpt_models:
                            data_json[line] = line
                        select_chatgpt_model = ui.select(
                            label='Model', 
                            options=data_json, 
                            value=config.get("chatgpt", "model"),
                            with_input=True,
                            new_value_mode='add-unique',
                            clearable=True
                        ).tooltip("If you can't find the model you are using here, you can clear this field and enter the model name manually. Be sure to press Enter to confirm!")
                        input_chatgpt_temperature = ui.input(label='Temperature', placeholder='Controls the randomness of generated text. Higher temperature values produce more random and diverse responses, while lower values produce more deterministic and consistent responses.', value=config.get("chatgpt", "temperature")).style("width:100px;")
                        input_chatgpt_max_tokens = ui.input(label='Max Tokens', placeholder='Limits the maximum length of the generated answer.', value=config.get("chatgpt", "max_tokens")).style("width:100px;")
                        input_chatgpt_top_p = ui.input(label='top_p', placeholder='Nucleus sampling. This parameter controls sampling from tokens whose cumulative probability exceeds a certain threshold. Higher values produce more diverse responses, while lower values produce fewer but more deterministic responses.', value=config.get("chatgpt", "top_p")).style("width:100px;")
                        switch_chatgpt_stream = ui.switch('Stream Output', value=config.get("chatgpt", "stream")).tooltip("Whether to enable streaming output. When enabled, the answer is displayed sentence by sentence; when disabled, the answer is displayed all at once.")
                    with ui.row():
                        input_chatgpt_presence_penalty = ui.input(label='Presence Penalty', placeholder='Controls how much the model avoids repeating tokens from the given prompt when generating a response. Higher values reduce repetition and encourage the model to generate more original responses.', value=config.get("chatgpt", "presence_penalty")).style("width:100px;")
                        input_chatgpt_frequency_penalty = ui.input(label='Frequency Penalty', placeholder='Controls how much the model penalizes tokens that have already appeared in the generated response. Higher values reduce the repetition of frequently used tokens and help avoid repetitive wording.', value=config.get("chatgpt", "frequency_penalty")).style("width:100px;")

                        input_chatgpt_preset = ui.input(label='Preset', placeholder='Specifies a set of predefined settings to help the model better adapt to specific conversation scenarios.', value=config.get("chatgpt", "preset")).style("width:500px") 

            
            
            if config.get("webui", "show_card", "llm", "chat_with_file"):
                with ui.card().style(card_css):
                    ui.label("chat_with_file")
                    with ui.row():
                        lines = [ "openai_gpt", "openai_vector_search"]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_chat_with_file_chat_mode = ui.select(
                            label='Chat Mode', 
                            options=data_json, 
                            value=config.get("chat_with_file", "chat_mode")
                        )
                        input_chat_with_file_data_path = ui.input(label='Data File Path', placeholder='Path to the local ZIP data file to load (up to x.zip), e.g., ./data/伊卡洛斯百度百科.zip', value=config.get("chat_with_file", "data_path"))
                        input_chat_with_file_data_path.style("width:400px")
                    with ui.row():
                        input_chat_with_file_separator = ui.input(label='Separator', placeholder='The delimiter used to split the text. A line break is used as the separator.', value=config.get("chat_with_file", "separator"))
                        input_chat_with_file_separator.style("width:300px")
                        input_chat_with_file_chunk_size = ui.input(label='Chunk Size', placeholder='Maximum number of characters per text chunk. More characters per chunk consume more tokens and produce more detailed responses.', value=config.get("chat_with_file", "chunk_size"))
                        input_chat_with_file_chunk_size.style("width:300px")
                        input_chat_with_file_chunk_overlap = ui.input(label='Chunk Overlap', placeholder='Number of overlapping characters between two adjacent text chunks. This overlap helps maintain text coherence, especially when the text is used for language model training or other machine learning tasks that require contextual information.', value=config.get("chat_with_file", "chunk_overlap"))
                        input_chat_with_file_chunk_overlap.style("width:300px")
                        lines = ["sebastian-hofstaetter/distilbert-dot-tas_b-b256-msmarco", "GanymedeNil/text2vec-large-chinese"]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_chat_with_file_local_vector_embedding_model = ui.select(
                            label='Model', 
                            options=data_json, 
                            value=config.get("chat_with_file", "local_vector_embedding_model")
                        )
                    with ui.row():
                        input_chat_with_file_chain_type = ui.input(label='Chain Type', placeholder='Specify the type of language chain to generate, e.g. stuff', value=config.get("chat_with_file", "chain_type"))
                        input_chat_with_file_chain_type.style("width:300px")
                        input_chat_with_file_question_prompt = ui.input(label='Question summary prompt', placeholder='Summarize the local vector database output via LLM; enter the summarization prompt here', value=config.get("chat_with_file", "question_prompt"))
                        input_chat_with_file_question_prompt.style("width:300px")
                        input_chat_with_file_local_max_query = ui.input(label='Max database queries', placeholder='Maximum number of database queries. Limiting this helps save tokens', value=config.get("chat_with_file", "local_max_query"))
                        input_chat_with_file_local_max_query.style("width:300px")
                        switch_chat_with_file_show_token_cost = ui.switch('Show cost', value=config.get("chat_with_file", "show_token_cost")).style(switch_internal_css)
            
            if config.get("webui", "show_card", "llm", "chatterbot"):
                with ui.card().style(card_css):
                    ui.label("Chatterbot")
                    with ui.grid(columns=2):
                        input_chatterbot_name = ui.input(label='Bot name', placeholder='Bot name', value=config.get("chatterbot", "name"))
                        input_chatterbot_name.style("width:400px")
                        input_chatterbot_db_path = ui.input(label='Database path', placeholder='Database path (absolute or relative)', value=config.get("chatterbot", "db_path"))
                        input_chatterbot_db_path.style("width:400px")
            
            if config.get("webui", "show_card", "llm", "text_generation_webui"):
                with ui.card().style(card_css):
                    ui.label("text_generation_webui")
                    with ui.row():
                        select_text_generation_webui_type = ui.select(
                            label='Type', 
                            options={"官方API": "官方API", "coyude": "coyude"}, 
                            value=config.get("text_generation_webui", "type")
                        )
                        input_text_generation_webui_api_ip_port = ui.input(
                            label='API address', 
                            placeholder='IP and port that text-generation-webui listens on after API mode is enabled', 
                            value=config.get("text_generation_webui", "api_ip_port"),
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        input_text_generation_webui_api_ip_port.style("width:300px")
                        input_text_generation_webui_max_new_tokens = ui.input(label='max_new_tokens', placeholder='Please refer to the docs', value=config.get("text_generation_webui", "max_new_tokens"))
                        input_text_generation_webui_max_new_tokens.style("width:200px")
                        switch_text_generation_webui_history_enable = ui.switch('Context memory', value=config.get("text_generation_webui", "history_enable")).style(switch_internal_css)
                        input_text_generation_webui_history_max_len = ui.input(label='Max memory length', placeholder='Maximum number of context characters to remember. Not recommended to set too high, as it may run out of VRAM; configure according to your situation', value=config.get("text_generation_webui", "history_max_len"))
                        input_text_generation_webui_history_max_len.style("width:200px")
                    with ui.row():
                        select_text_generation_webui_mode = ui.select(
                            label='Type', 
                            options={"chat": "chat", "chat-instruct": "chat-instruct", "instruct": "instruct"}, 
                            value=config.get("text_generation_webui", "mode")
                        ).style("width:150px")
                        input_text_generation_webui_character = ui.input(label='character', placeholder='Please refer to the docs', value=config.get("text_generation_webui", "character"))
                        input_text_generation_webui_character.style("width:100px")
                        input_text_generation_webui_instruction_template = ui.input(label='instruction_template', placeholder='Please refer to the docs', value=config.get("text_generation_webui", "instruction_template"))
                        input_text_generation_webui_instruction_template.style("width:150px")
                        input_text_generation_webui_your_name = ui.input(label='your_name', placeholder='Please refer to the docs', value=config.get("text_generation_webui", "your_name"))
                        input_text_generation_webui_your_name.style("width:100px")
                    with ui.row():
                        input_text_generation_webui_top_p = ui.input(label='top_p', value=config.get("text_generation_webui", "top_p"), placeholder='Probability threshold for nucleus sampling during generation. For example, at 0.8, only tokens in the probability distribution whose cumulative probability is >= 0.8 are kept as the candidate set for random sampling. Range is (0, 1.0); higher values increase randomness, lower values decrease it. Default 0.95. Note: the value must not be >= 1')
                        input_text_generation_webui_top_k = ui.input(label='top_k', value=config.get("text_generation_webui", "top_k"), placeholder='Number of matching search results')
                        input_text_generation_webui_temperature = ui.input(label='temperature', value=config.get("text_generation_webui", "temperature"), placeholder='Higher values make the output more random, lower values make it more focused and deterministic. Optional, default 0.92')
                        input_text_generation_webui_seed = ui.input(label='seed', value=config.get("text_generation_webui", "seed"), placeholder='Seed for the random number generator during generation, used to control randomness. With the same seed, each run produces the same result; use the same seed to reproduce generations. Supports unsigned 64-bit integers. Default 1683806810')

            if config.get("webui", "show_card", "llm", "sparkdesk"):    
                with ui.card().style(card_css):
                    ui.label("iFlytek Spark")
                    with ui.grid(columns=1):
                        lines = ["web", "api"]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_sparkdesk_type = ui.select(
                            label='Type', 
                            options=data_json, 
                            value=config.get("sparkdesk", "type")
                        ).style("width:100px") 
                    
                    with ui.card().style(card_css):
                        ui.label("WEB")
                        with ui.row():
                            input_sparkdesk_cookie = ui.input(label='cookie', placeholder='webCookie in the captured request headers, see the documentation tutorial', value=config.get("sparkdesk", "cookie"))
                            input_sparkdesk_cookie.style("width:300px")
                            input_sparkdesk_fd = ui.input(label='fd', placeholder='webfd in the captured payload, see the documentation tutorial', value=config.get("sparkdesk", "fd"))
                            input_sparkdesk_fd.style("width:200px")      
                            input_sparkdesk_GtToken = ui.input(label='GtToken', placeholder='webGtToken in the captured payload, see the documentation tutorial', value=config.get("sparkdesk", "GtToken"))
                            input_sparkdesk_GtToken.style("width:200px")

                    with ui.card().style(card_css):
                        ui.label("API")
                        with ui.row():
                            input_sparkdesk_app_id = ui.input(label='app_id', value=config.get("sparkdesk", "app_id"), placeholder='After applying for the official API, the one provided in the cloud PlatformAPPID').style("width:100px")   
                            input_sparkdesk_api_secret = ui.input(label='api_secret', value=config.get("sparkdesk", "api_secret"), placeholder='After applying for the official API, the one provided in the cloud PlatformAPISecret').style("width:200px") 
                            input_sparkdesk_api_key = ui.input(label='api_key', value=config.get("sparkdesk", "api_key"), placeholder='After applying for the official API, the one provided in the cloud PlatformAPIKey').style("width:200px") 
                            
                            select_sparkdesk_version = ui.select(
                                label='Version', 
                                options={
                                    "4.0": "Ultra",
                                    "3.5": "Max",
                                    "3.2": "pro-128k",
                                    "3.1": "Pro",
                                    "2.1": "V2.1",
                                    "1.1": "Lite",
                                }, 
                                value=str(config.get("sparkdesk", "version"))
                            ).style("width:100px") 
                            input_sparkdesk_assistant_id = ui.input(label='Assistant ID', value=config.get("sparkdesk", "assistant_id"), placeholder='Assistant creation center; after creating an assistant, the last part of the assistant API endpoint address is the assistantID').style("width:100px") 
                 
            if config.get("webui", "show_card", "llm", "langchain_chatchat"):  
                with ui.card().style(card_css):
                    ui.label("Langchain_ChatChat")
                    with ui.row():
                        input_langchain_chatchat_api_ip_port = ui.input(
                            label='API address', 
                            placeholder='Service URL after running the API version of Langchain-Chatchat (full URL required）', 
                            value=config.get("langchain_chatchat", "api_ip_port"),
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        input_langchain_chatchat_api_ip_port.style("width:400px")
                        lines = ["Model", "Knowledge base", "Search engine"]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_langchain_chatchat_chat_type = ui.select(
                            label='Type', 
                            options=data_json, 
                            value=config.get("langchain_chatchat", "chat_type")
                        )
                        switch_langchain_chatchat_history_enable = ui.switch('Context memory', value=config.get("langchain_chatchat", "history_enable")).style(switch_internal_css)
                        input_langchain_chatchat_history_max_len = ui.input(label='Max memory length', placeholder='Maximum number of context characters to remember. Not recommended to set too high, as it may run out of VRAM; configure according to your situation', value=config.get("langchain_chatchat", "history_max_len"))
                        input_langchain_chatchat_history_max_len.style("width:400px")
                    with ui.row():
                        with ui.card().style(card_css):
                            ui.label("Model")
                            with ui.row():
                                input_langchain_chatchat_llm_model_name = ui.input(label='LLM model', value=config.get("langchain_chatchat", "llm", "model_name"), placeholder='Name of the locally loaded LLM model')
                                input_langchain_chatchat_llm_temperature = ui.input(label='Temperature', value=config.get("langchain_chatchat", "llm", "temperature"), placeholder='Sampling temperature, controls output randomness, must be positive\nRange: (0.0, 1.0], cannot be 0, default 0.95\nHigher values make the output more random and creative; lower values make it more stable or deterministic\nIt is recommended to adjust either top_p or temperature for your use case, but not both at the same time')
                                input_langchain_chatchat_llm_max_tokens = ui.input(label='max_tokens', value=config.get("langchain_chatchat", "llm", "max_tokens"), placeholder='Positive integer greater than 0. Not recommended to set too high, you may run out of VRAM')
                                input_langchain_chatchat_llm_prompt_name = ui.input(label='Prompt template', value=config.get("langchain_chatchat", "llm", "prompt_name"), placeholder='File name of a locally available prompt template')
                    with ui.row():
                        with ui.card().style(card_css):
                            ui.label("Knowledge base")
                            with ui.row():
                                input_langchain_chatchat_knowledge_base_knowledge_base_name = ui.input(label='Knowledge base name', value=config.get("langchain_chatchat", "knowledge_base", "knowledge_base_name"), placeholder='Name of a locally added knowledge base. On run, the list of existing knowledge bases is retrieved and printed to the cmd, please check it there')
                                input_langchain_chatchat_knowledge_base_top_k = ui.input(label='Number of matched results', value=config.get("langchain_chatchat", "knowledge_base", "top_k"), placeholder='Number of matched search results')
                                input_langchain_chatchat_knowledge_base_score_threshold = ui.input(label='Knowledge match score threshold', value=config.get("langchain_chatchat", "knowledge_base", "score_threshold"), placeholder='Between 0.00 and 2.00')
                                input_langchain_chatchat_knowledge_base_model_name = ui.input(label='LLM model', value=config.get("langchain_chatchat", "knowledge_base", "model_name"), placeholder='Name of the locally loaded LLM model')
                                input_langchain_chatchat_knowledge_base_temperature = ui.input(label='Temperature', value=config.get("langchain_chatchat", "knowledge_base", "temperature"), placeholder='Sampling temperature, controls output randomness, must be positive\nRange: (0.0, 1.0], cannot be 0, default 0.95\nHigher values make the output more random and creative; lower values make it more stable or deterministic\nIt is recommended to adjust either top_p or temperature for your use case, but not both at the same time')
                                input_langchain_chatchat_knowledge_base_max_tokens = ui.input(label='max_tokens', value=config.get("langchain_chatchat", "knowledge_base", "max_tokens"), placeholder='Positive integer greater than 0. Not recommended to set too high, you may run out of VRAM')
                                input_langchain_chatchat_knowledge_base_prompt_name = ui.input(label='Prompt template', value=config.get("langchain_chatchat", "knowledge_base", "prompt_name"), placeholder='File name of a locally available prompt template')
                    with ui.row():
                        with ui.card().style(card_css):
                            ui.label("Search engine")
                            with ui.row():
                                lines = ['bing', 'duckduckgo', 'metaphor']
                                data_json = {}
                                for line in lines:
                                    data_json[line] = line
                                select_langchain_chatchat_search_engine_search_engine_name = ui.select(
                                    label='Search engine', 
                                    options=data_json, 
                                    value=config.get("langchain_chatchat", "search_engine", "search_engine_name")
                                )
                                input_langchain_chatchat_search_engine_top_k = ui.input(label='Number of matched results', value=config.get("langchain_chatchat", "search_engine", "top_k"), placeholder='Number of matched search results')
                                input_langchain_chatchat_search_engine_model_name = ui.input(label='LLM model', value=config.get("langchain_chatchat", "search_engine", "model_name"), placeholder='Name of the locally loaded LLM model')
                                input_langchain_chatchat_search_engine_temperature = ui.input(label='Temperature', value=config.get("langchain_chatchat", "search_engine", "temperature"), placeholder='Sampling temperature, controls output randomness, must be positive\nRange: (0.0, 1.0], cannot be 0, default 0.95\nHigher values make the output more random and creative; lower values make it more stable or deterministic\nIt is recommended to adjust either top_p or temperature for your use case, but not both at the same time')
                                input_langchain_chatchat_search_engine_max_tokens = ui.input(label='max_tokens', value=config.get("langchain_chatchat", "search_engine", "max_tokens"), placeholder='Positive integer greater than 0. Not recommended to set too high, you may run out of VRAM')
                                input_langchain_chatchat_search_engine_prompt_name = ui.input(label='Prompt template', value=config.get("langchain_chatchat", "search_engine", "prompt_name"), placeholder='File name of a locally available prompt template')
            if config.get("webui", "show_card", "llm", "zhipu"):  
                with ui.card().style(card_css):
                    ui.label("Zhipu AI")
                    with ui.row():
                        input_zhipu_api_key = ui.input(label='api key', placeholder='See the official documentation for details, application address:https://open.bigmodel.cn/usercenter/apikeys', value=config.get("zhipu", "api_key"))
                        input_zhipu_api_key.style("width:200px")
                        lines = [
                            'App',
                            'Agent',
                            'glm-3-turbo', 
                            'glm-4', 
                            'glm-4-flash',
                            'charglm-3',
                            'characterglm', 
                            'chatglm_turbo', 
                            'chatglm_pro', 
                            'chatglm_std', 
                            'chatglm_lite', 
                            'chatglm_lite_32k'
                        ]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_zhipu_model = ui.select(
                            label='Model', 
                            options=data_json, 
                            value=config.get("zhipu", "model"),
                            with_input=True,
                            new_value_mode='add-unique',
                            clearable=True
                        )
                        input_zhipu_app_id = ui.input(label='App ID', value=config.get("zhipu", "app_id"), placeholder='When the model is: Application, all application information added on your Platform is retrieved automatically, then just copy the application ID you need from the Log').style("width:200px")
                        
                    with ui.row():
                        input_zhipu_top_p = ui.input(label='top_p', placeholder='Another alternative to temperature sampling, called nucleus sampling\nValue range: (0.0,1.0); an open interval, cannot equal 0 or 1, default 0.7\nThe model considers the results of tokens with top_p probability mass. So 0.1 means the model decoder only takes tokens from the candidate set with the top 10% probability\nIt is recommended to adjust either the top_p or temperature parameter according to your application scenario, but not both at the same time', value=config.get("zhipu", "top_p"))
                        input_zhipu_top_p.style("width:200px")
                        input_zhipu_temperature = ui.input(label='temperature', placeholder='Sampling temperature, controls the randomness of the output, must be a positive number\nValue range: (0.0,1.0], cannot equal 0, default 0.95\nThe larger the value, the more random and creative the output; the smaller the value, the more stable or deterministic the output\nIt is recommended to adjust either the top_p or temperature parameter according to your application scenario, but not both at the same time', value=config.get("zhipu", "temperature"))
                        input_zhipu_temperature.style("width:200px")
                        switch_zhipu_history_enable = ui.switch('Context memory', value=config.get("zhipu", "history_enable")).style(switch_internal_css)
                        input_zhipu_history_max_len = ui.input(label='Max memory length', placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data', value=config.get("zhipu", "history_max_len"))
                        input_zhipu_history_max_len.style("width:200px")
                    with ui.row():
                        input_zhipu_user_info = ui.input(label='User info', placeholder='User info, needs to be configured when using characterglm', value=config.get("zhipu", "user_info"))
                        input_zhipu_user_info.style("width:400px")
                        input_zhipu_bot_info = ui.input(label='Character info', placeholder='Character info, needs to be configured when using characterglm', value=config.get("zhipu", "bot_info"))
                        input_zhipu_bot_info.style("width:400px")
                        input_zhipu_bot_name = ui.input(label='Character name', placeholder='Character name, needs to be configured when using characterglm', value=config.get("zhipu", "bot_name"))
                        input_zhipu_bot_name.style("width:200px")
                        input_zhipu_username = ui.input(label='UsernameName', placeholder='UsernameName, the default value is user, needs to be configured when using characterglm', value=config.get("zhipu", "username"))
                        input_zhipu_username.style("width:200px")
                    with ui.row():
                        switch_zhipu_remove_useless = ui.switch('Delete useless characters', value=config.get("zhipu", "remove_useless")).style(switch_internal_css)
                        switch_zhipu_stream = ui.switch('Streaming output', value=config.get("zhipu", "stream")).tooltip("Whether to enable streaming output. When enabled, the Answer is output sentence by sentence; when disabled, the Answer is output all at once.")
                    with ui.card().style(card_css):
                        ui.label("Agent")
                        with ui.row():
                            input_zhipu_assistant_api_api_key = ui.input(
                                label='Agent API Key', 
                                placeholder='Agent Creator Center, apply for the API:https://chatglm.cn/developersPanel/apiSet', 
                                value=config.get("zhipu", "assistant_api", "api_key")
                            ).style("width:150px").tooltip('Agent Creator Center, apply for the API:https://chatglm.cn/developersPanel/apiSet')
                            input_zhipu_assistant_api_api_secret = ui.input(
                                label='Agent API Secret', 
                                placeholder='Agent Creator Center, apply for the API:https://chatglm.cn/developersPanel/apiSet', 
                                value=config.get("zhipu", "assistant_api", "api_secret")
                            ).style("width:150px").tooltip('Agent Creator Center, apply for the API:https://chatglm.cn/developersPanel/apiSet')
                            input_zhipu_assistant_api_assistant_id = ui.input(
                                label='Agent ID', 
                                placeholder='Agent ID; after opening the agent conversation page in the browser, it can be seen in the URL address bar, that string of English letters and digits', 
                                value=config.get("zhipu", "assistant_api", "assistant_id")
                            ).style("width:200px").tooltip('Agent ID; after opening the agent conversation page in the browser, it can be seen in the URL address bar, that string of English letters and digits')

            if config.get("webui", "show_card", "llm", "bard"):  
                with ui.card().style(card_css):
                    ui.label("Bard")
                    with ui.grid(columns=2):
                        input_bard_token = ui.input(label='token', placeholder='Log in to bard, open F12, and get the value corresponding to __Secure-1PSID in the cookie', value=config.get("bard", "token"))
                        input_bard_token.style("width:400px")
            
            
            if config.get("webui", "show_card", "llm", "tongyixingchen"): 
                with ui.card().style(card_css):
                    ui.label("Tongyi Xingchen")
                    with ui.row():
                        input_tongyixingchen_access_token = ui.input(label='Key', value=config.get("tongyixingchen", "access_token"), placeholder='Apply on the official website to activate the API-KEY, then ask the official side for call permission')
                        lines = ['Fixed role']
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_tongyixingchen_type = ui.select(
                            label='Type', 
                            options=data_json, 
                            value=config.get("tongyixingchen", "type")
                        ).style("width:100px")
                        switch_tongyixingchen_history_enable = ui.switch('Context memory', value=config.get("tongyixingchen", "history_enable")).style(switch_internal_css)
                        input_tongyixingchen_history_max_len = ui.input(label='Max memory length', value=config.get("tongyixingchen", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')
                        switch_tongyixingchen_stream = ui.switch('Streaming output', value=config.get("tongyixingchen", "stream")).tooltip("Whether to enable streaming output. When enabled, the Answer is output sentence by sentence; when disabled, the Answer is output all at once.")
                    
                    with ui.card().style(card_css):
                        ui.label("Fixed role")
                        with ui.row():
                            input_tongyixingchen_GDJS_character_id = ui.input(label='CharacterID', value=config.get("tongyixingchen", "Fixed role", "character_id"), placeholder='On the official website Chat page, create a character, then open the character info and you can seeID')
                            input_tongyixingchen_GDJS_top_p = ui.input(label='top_p', value=config.get("tongyixingchen", "Fixed role", "top_p"), placeholder='topPProbability threshold of the nucleus sampling method during generation. For example, when set to 0.8, only the tokens in the probability distribution whose cumulative probability sum is greater than or equal to 0.8 are kept as the candidate set for random sampling. The value range is (0,1.0); the larger the value, the higher the randomness of generation; the lower the value, the lower the randomness. Default 0.95. Note, the value must not be greater than or equal to1')
                            input_tongyixingchen_GDJS_temperature = ui.input(label='temperature', value=config.get("tongyixingchen", "Fixed role", "temperature"), placeholder='A higher value makes the output more random, while a lower value makes the output more focused and deterministic. Optional, default value0.92')
                            input_tongyixingchen_GDJS_seed = ui.input(label='seed', value=config.get("tongyixingchen", "Fixed role", "seed"), placeholder='seedRandom number seed during generation, used to control the randomness of model generation. If the same seed is used, the results generated on each Run will be identical; when you need to reproduce the generation results of the model, you can use the same seed. The seed parameter supports the unsigned 64-bit integer Type. Default 1683806810')
                        with ui.row():
                            input_tongyixingchen_GDJS_user_id = ui.input(label='UserID', value=config.get("tongyixingchen", "Fixed role", "user_id"), placeholder='Unique user identifier of the business system; the same user cannot hold parallel conversations, and the next conversation can only start after the previous Reply has finished')
                            input_tongyixingchen_GDJS_username = ui.input(label='Chat Username', value=config.get("tongyixingchen", "Fixed role", "username"), placeholder='Chat Username, i.e. your name')
                            input_tongyixingchen_GDJS_role_name = ui.input(label='Fixed role name', value=config.get("tongyixingchen", "Fixed role", "role_name"), placeholder='Character name corresponding to the character ID; if you wrote it yourself, do not tell me you do not know!')

            if config.get("webui", "show_card", "llm", "my_wenxinworkshop"): 
                with ui.card().style(card_css):
                    ui.label("Qianfan")
                    with ui.row():
                        select_my_wenxinworkshop_type = ui.select(
                            label='Type', 
                            options={"Qianfan": "Qianfan", "AppBuilder": "AppBuilder"}, 
                            value=config.get("my_wenxinworkshop", "type")
                        ).style("width:150px")
                        switch_my_wenxinworkshop_history_enable = ui.switch('Context memory', value=config.get("my_wenxinworkshop", "history_enable")).style(switch_internal_css)
                        input_my_wenxinworkshop_history_max_len = ui.input(label='Max memory length', value=config.get("my_wenxinworkshop", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')
                        switch_my_wenxinworkshop_stream = ui.switch('Streaming output', value=config.get("my_wenxinworkshop", "stream")).tooltip("Whether to enable streaming output. When enabled, the Answer is output sentence by sentence; when disabled, the Answer is output all at once.")
                    
                    with ui.row():
                        input_my_wenxinworkshop_api_key = ui.input(label='api_key', value=config.get("my_wenxinworkshop", "api_key"), placeholder='Qianfan Large ModelPlatform, activate the corresponding service. Application access - create application, fill inapi key')
                        input_my_wenxinworkshop_secret_key = ui.input(label='secret_key', value=config.get("my_wenxinworkshop", "secret_key"), placeholder='Qianfan Large ModelPlatform, activate the corresponding service. Application access - create application, fill insecret key')
                        lines = [
                            "ERNIEBot",
                            "ERNIEBot_turbo",
                            "ERNIEBot_4_0",
                            "ERNIE_SPEED_128K",
                            "ERNIE_SPEED_8K",
                            "ERNIE_LITE_8K",
                            "ERNIE_LITE_8K_0922",
                            "ERNIE_TINY_8K",
                            "BLOOMZ_7B",
                            "LLAMA_2_7B",
                            "LLAMA_2_13B",
                            "LLAMA_2_70B",
                            "ERNIEBot_4_0",
                            "QIANFAN_BLOOMZ_7B_COMPRESSED",
                            "QIANFAN_CHINESE_LLAMA_2_7B",
                            "CHATGLM2_6B_32K",
                            "AQUILACHAT_7B",
                            "ERNIE_BOT_8K",
                            "CODELLAMA_7B_INSTRUCT",
                            "XUANYUAN_70B_CHAT",
                            "CHATLAW",
                            "QIANFAN_BLOOMZ_7B_COMPRESSED",
                        ]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_my_wenxinworkshop_model = ui.select(
                            label='Model', 
                            options=data_json, 
                            value=config.get("my_wenxinworkshop", "model")
                        ).style("width:150px")
                        
                        input_my_wenxinworkshop_temperature = ui.input(label='Temperature', value=config.get("my_wenxinworkshop", "temperature"), placeholder='(0, 1.0] Controls the randomness of the generated text. A higher temperature value makes the generated text more random and diverse, while a lower temperature value makes it more deterministic and consistent.').style("width:200px;")
                        input_my_wenxinworkshop_top_p = ui.input(label='Top p selection', value=config.get("my_wenxinworkshop", "top_p"), placeholder='[0, 1.0] NucleusSampling. This parameter controls the model to sample from tokens whose cumulative probability exceeds a certain threshold. A higher value produces more diversity, a lower value produces fewer but more deterministic Answers.').style("width:200px;")
                        input_my_wenxinworkshop_penalty_score = ui.input(label='Penalty score', value=config.get("my_wenxinworkshop", "penalty_score"), placeholder='[1.0, 2.0] Penalty applied to certain words or patterns when generating text. This is a mechanism for adjusting the generated content, used to reduce or avoid undesired content.').style("width:200px;")
                    with ui.row():
                        input_my_wenxinworkshop_app_id = ui.input(label='AppBuilder App ID', value=config.get("my_wenxinworkshop", "app_id"), placeholder='Qianfan AppBuilder Platform, Personal Space, Applications, ApplicationID').style("width:200px;")
                        input_my_wenxinworkshop_app_token = ui.input(label='AppBuilder app_token', value=config.get("my_wenxinworkshop", "app_token"), placeholder='Qianfan AppBuilder Platform, My Applications - Application Configuration - Publish Details - My Agent Applications - API Call, fill inapp_token').style("width:200px;")
                        


            
            if config.get("webui", "show_card", "llm", "gemini"):
                with ui.card().style(card_css):
                    ui.label("Gemini")
                    with ui.row():
                        input_gemini_api_key = ui.input(label='api_key', value=config.get("gemini", "api_key"), placeholder='Created in Google AI Studioapi key')
                        lines = [
                            "gemini-pro",
                        ]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_gemini_model = ui.select(
                            label='Model', 
                            options=data_json, 
                            value=config.get("gemini", "model")
                        ).style("width:150px")
                        switch_gemini_history_enable = ui.switch('Context memory', value=config.get("gemini", "history_enable")).style(switch_internal_css)
                        input_gemini_history_max_len = ui.input(label='Max memory length', value=config.get("gemini", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')
                    with ui.row():
                        input_gemini_http_proxy = ui.input(label='HTTP proxy address', value=config.get("gemini", "http_proxy"), placeholder='httpProxy address; a VPN is required to use it, so this must be configured.').style("width:200px;")
                        input_gemini_https_proxy = ui.input(label='HTTPS proxy address', value=config.get("gemini", "https_proxy"), placeholder='httpsProxy address; a VPN is required to use it, so this must be configured.').style("width:200px;")
                    with ui.row():
                        input_gemini_max_output_tokens = ui.input(label='Max output tokens', value=config.get("gemini", "max_output_tokens"), placeholder='Maximum number of tokens in the candidate output')
                        input_gemini_max_temperature = ui.input(label='temperature', value=config.get("gemini", "temperature"), placeholder='Controls the randomness of the output. The value range is [0.0,1.0], inclusive of 0.0 and 1.0. The closer the value is to 1.0, the more diverse and creative the generated response will be, while the closer to 0.0, the more straightforward the model response usually is.')
                        input_gemini_top_p = ui.input(label='top_p', value=config.get("gemini", "top_p"), placeholder='Maximum cumulative probability of tokens considered during sampling. Tokens are sorted by their assigned probability so that only the most likely tokens are considered. Top-k sampling directly limits the maximum number of tokens to consider, while Nucleus sampling limits the number of tokens based on cumulative probability.')
                        input_gemini_top_k = ui.input(label='top_k', value=config.get("gemini", "top_k"), placeholder='Maximum number of tokens considered during sampling. Top-k sampling considers the set of top_k most likely tokens. The default is 40.')

            
            if config.get("webui", "show_card", "llm", "koboldcpp"):
                with ui.card().style(card_css):
                    ui.label("koboldcpp")
                    with ui.row():
                        input_koboldcpp_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("koboldcpp", "api_ip_port"), 
                            placeholder='koboldcppThe ip and Port address the API listens on after starting',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        input_koboldcpp_max_context_length = ui.input(label='max_context_length', value=config.get("koboldcpp", "max_context_length"), placeholder='max_context_length')
                        input_koboldcpp_max_length = ui.input(label='max_length', value=config.get("koboldcpp", "max_length"), placeholder='max_length')
                        switch_koboldcpp_quiet = ui.switch('quiet', value=config.get("koboldcpp", "quiet")).style(switch_internal_css)
                        input_koboldcpp_rep_pen = ui.input(label='rep_pen', value=config.get("koboldcpp", "rep_pen"), placeholder='rep_pen')
                        input_koboldcpp_rep_pen_range = ui.input(label='rep_pen_range', value=config.get("koboldcpp", "rep_pen_range"), placeholder='rep_pen_range')
                        input_koboldcpp_rep_pen_slope = ui.input(label='rep_pen_slope', value=config.get("koboldcpp", "rep_pen_slope"), placeholder='rep_pen_slope')
                    with ui.row():
                        input_koboldcpp_temperature = ui.input(label='temperature', value=config.get("koboldcpp", "temperature"), placeholder='Controls the randomness of the output.')
                        input_koboldcpp_tfs = ui.input(label='tfs', value=config.get("koboldcpp", "tfs"), placeholder='tfs')
                        input_koboldcpp_top_a = ui.input(label='top_a', value=config.get("koboldcpp", "top_a"), placeholder='top_a')
                        input_koboldcpp_top_p = ui.input(label='top_p', value=config.get("koboldcpp", "top_p"), placeholder='Maximum cumulative probability of tokens considered during sampling. Tokens are sorted by their assigned probability so that only the most likely tokens are considered. Top-k sampling directly limits the maximum number of tokens to consider, while Nucleus sampling limits the number of tokens based on cumulative probability.')
                        input_koboldcpp_top_k = ui.input(label='top_k', value=config.get("koboldcpp", "top_k"), placeholder='Maximum number of tokens considered during sampling. Top-k sampling considers the set of top_k most likely tokens. The default is 40.')
                        input_koboldcpp_typical = ui.input(label='typical', value=config.get("koboldcpp", "typical"), placeholder='typical')
                        switch_koboldcpp_history_enable = ui.switch('Context memory', value=config.get("koboldcpp", "history_enable")).style(switch_internal_css)
                        input_koboldcpp_history_max_len = ui.input(label='Max memory length', value=config.get("koboldcpp", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')

            if config.get("webui", "show_card", "llm", "anythingllm"):
                with ui.card().style(card_css):
                    ui.label("AnythingLLM")
                    with ui.row():
                        input_anythingllm_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("anythingllm", "api_ip_port"), 
                            placeholder='anythingllmThe ip and Port address the API listens on after starting',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
            
                        input_anythingllm_api_key = ui.input(label='APIKey', value=config.get("anythingllm", "api_key"), placeholder='APIKey, obtained in the settings')
                        select_anythingllm_mode = ui.select(
                            label='Mode', 
                            options={'chat': 'Chat', 'query': 'Query the knowledge base only'}, 
                            value=config.get("anythingllm", "mode")
                        ).style("width:200px")
                        select_anythingllm_workspace_slug = ui.select(
                            label='Workspaceslug', 
                            options={config.get("anythingllm", "workspace_slug"): config.get("anythingllm", "workspace_slug")}, 
                            value=config.get("anythingllm", "workspace_slug")
                        ).style("width:200px")

                        def anythingllm_get_workspaces_list():
                            try:
                                from utils.gpt_model.anythingllm import AnythingLLM

                                tmp_config = config.get("anythingllm")
                                tmp_config["api_ip_port"] = input_anythingllm_api_ip_port.value
                                tmp_config["api_key"] = input_anythingllm_api_key.value

                                anythingllm = AnythingLLM(tmp_config)

                                workspaces_list = anythingllm.get_workspaces_list()
                                data_json = {}
                                for workspace_info in workspaces_list:
                                    data_json[workspace_info['slug']] = workspace_info['slug']

                                select_anythingllm_workspace_slug.set_options(data_json)
                                select_anythingllm_workspace_slug.set_value(config.get("anythingllm", "workspace_slug"))

                                logger.info("Read workspaceSuccess")
                                ui.notify(position="top", type="positive", message="Read workspaceSuccess")
                            except Exception as e:
                                logger.error(f"Read workspaceFailed!\n{e}")
                                ui.notify(position="top", type="negative", message=f"Read workspaceFailed!\n{e}")

                        button_anythingllm_get_workspaces_list = ui.button('Get All workspacesslug', on_click=lambda: anythingllm_get_workspaces_list(), color=button_internal_color).style(button_internal_css)
                

            if config.get("webui", "show_card", "llm", "tongyi"):           
                with ui.card().style(card_css):
                    ui.label("Tongyi Qianwen / Alibaba Cloud Bailian")
                    with ui.row():
                        lines = ['web', 'api']
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_tongyi_type = ui.select(
                            label='Type', 
                            options=data_json, 
                            value=config.get("tongyi", "type")
                        ).style("width:100px")
                        input_tongyi_cookie_path = ui.input(label='cookiePath', placeholder='webTypeUnder it, after logging in to Tongyi Qianwen, get the Cookie JSON string through the Cookie Editor browser plugin, then save the data in a file at this path', value=config.get("tongyi", "cookie_path"))
                        input_tongyi_cookie_path.style("width:400px")
                    with ui.row():
                        lines = [
                            'qwen-turbo', 
                            'qwen-plus', 
                            'qwen-long', 
                            'qwen-max-longcontext', 
                            'qwen-max', 
                            'qwen-max-0428', 
                            'baichuan2-turbo', 
                            'moonshot-v1-8k', 
                            'moonshot-v1-32k', 
                            'moonshot-v1-128k',
                            'yi-large',
                            'yi-large-turbo',
                            'yi-medium',
                        ]
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_tongyi_model = ui.select(
                            label='Type', 
                            options=data_json, 
                            value=config.get("tongyi", "model"),
                            with_input=True,
                            new_value_mode='add-unique',
                            clearable=True
                        ).style("width:150px")
                        input_tongyi_api_key = ui.input(label='Key', value=config.get("tongyi", "api_key"), placeholder='APITypeUnder it, the API key applied for on the DashScope Platform')
                        input_tongyi_preset = ui.input(label='Preset', placeholder='APITypeUnder it, used to specify a set of predefined settings so the model better fits specific conversation scenarios.', value=config.get("tongyi", "preset")).style("width:500px") 
                        input_tongyi_temperature = ui.input(label='temperature', value=config.get("tongyi", "temperature"), placeholder='Controls the randomness of the output.').style("width:100px")
                        input_tongyi_top_p = ui.input(label='top_p', value=config.get("tongyi", "top_p"), placeholder='Maximum cumulative probability of tokens considered during sampling. Tokens are sorted by their assigned probability so that only the most likely tokens are considered. Top-k sampling directly limits the maximum number of tokens to consider, while Nucleus sampling limits the number of tokens based on cumulative probability.').style("width:100px")
                        input_tongyi_top_k = ui.input(label='top_k', value=config.get("tongyi", "top_k"), placeholder='Maximum number of tokens considered during sampling. Top-k sampling considers the set of top_k most likely tokens. The default is 40.').style("width:100px")
                        switch_tongyi_enable_search = ui.switch('Online search', value=config.get("tongyi", "enable_search")).style(switch_internal_css)
                        
                    with ui.row():
                        switch_tongyi_history_enable = ui.switch('Context memory', value=config.get("tongyi", "history_enable")).style(switch_internal_css)
                        input_tongyi_history_max_len = ui.input(label='Max memory length', value=config.get("tongyi", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')
                        switch_tongyi_stream = ui.switch('Streaming output', value=config.get("tongyi", "stream")).tooltip("Whether to enable streaming output. When enabled, the Answer is output sentence by sentence; when disabled, the Answer is output all at once.")
                    
            if config.get("webui", "show_card", "llm", "gpt4free"):
                with ui.card().style(card_css):
                    ui.label("GPT4Free")
                    with ui.row():
                        providers = [
                            "none",
                            "g4f.Provider.Bing",
                            "g4f.Provider.ChatgptAi",
                            "g4f.Provider.Liaobots",
                            "g4f.Provider.OpenaiChat",
                            "g4f.Provider.Raycast",
                            "g4f.Provider.Theb",
                            "g4f.Provider.You",
                            "g4f.Provider.AItianhuSpace",
                            "g4f.Provider.ChatForAi",
                            "g4f.Provider.Chatgpt4Online",
                            "g4f.Provider.ChatgptNext",
                            "g4f.Provider.ChatgptX",
                            "g4f.Provider.FlowGpt",
                            "g4f.Provider.GptTalkRu",
                            "g4f.Provider.Koala",
                        ]
                        # Insert the value configured by the user into the list (if it does not exist)
                        if config.get("gpt4free", "provider") not in providers:
                            providers.append(config.get("gpt4free", "provider"))
                        data_json = {}
                        for line in providers:
                            data_json[line] = line
                        select_gpt4free_provider = ui.select(
                            label='Provider', 
                            options=data_json, 
                            value=config.get("gpt4free", "provider"),
                            with_input=True,
                            new_value_mode='add-unique',
                            clearable=True
                        )
                        input_gpt4free_api_key = ui.input(label='APIKey', placeholder='API KEY, supports proxy', value=config.get("gpt4free", "api_key")).style("width:300px;")
                        # button_gpt4free_test = ui.button('Test', on_click=lambda: test_openai_key(), color=button_bottom_color).style(button_bottom_css)

                        gpt4free_models = [
                            "gpt-3.5-turbo",
                            "gpt-4",
                            "gpt-4-turbo",
                        ]
                        # Insert the value configured by the user into the list (if it does not exist)
                        if config.get("gpt4free", "model") not in gpt4free_models:
                            gpt4free_models.append(config.get("gpt4free", "model"))
                        data_json = {}
                        for line in gpt4free_models:
                            data_json[line] = line
                        select_gpt4free_model = ui.select(
                            label='Model', 
                            options=data_json, 
                            value=config.get("gpt4free", "model"),
                            with_input=True,
                            new_value_mode='add-unique',
                            clearable=True
                        )
                        input_gpt4free_proxy = ui.input(label='HTTP proxy address', placeholder='HTTP proxy address', value=config.get("gpt4free", "proxy")).style("width:300px;")
                    with ui.row():
                        input_gpt4free_max_tokens = ui.input(label='Max tokens', value=config.get("gpt4free", "max_tokens"), placeholder='Limit the maximum length of the generated Answer.').style("width:200px;")
                    
                        input_gpt4free_preset = ui.input(label='Preset', value=config.get("gpt4free", "preset"), placeholder='Used to specify a set of predefined settings so the model better fits specific conversation scenarios.').style("width:500px") 
                        switch_gpt4free_history_enable = ui.switch('Context memory', value=config.get("gpt4free", "history_enable")).style(switch_internal_css)
                        input_gpt4free_history_max_len = ui.input(label='Max memory length', value=config.get("gpt4free", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')

            if config.get("webui", "show_card", "llm", "dify"):
                with ui.card().style(card_css):
                    ui.label("Dify")
                    with ui.row():
                        input_dify_api_ip_port = ui.input(
                            label="API address", 
                            value=config.get("dify", "api_ip_port"), 
                            placeholder='Dify API address, just copy it from the API documentation of the application', 
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip('Dify API address, just copy it from the API documentation of the application')
                        input_dify_api_key = ui.input(label='APIKey', value=config.get("dify", "api_key"), placeholder='APIKey, obtained from the API page').tooltip('APIKey, obtained from the API page')
                        select_dify_type = ui.select(
                            label='App type', 
                            options={'Chat assistant': 'Chat assistant', 'Workflow': 'Workflow'}, 
                            value=config.get("dify", "type")
                        ).style("width:200px")
                        switch_dify_stream = ui.switch('Streaming response', value=config.get("dify", "stream")).style(switch_internal_css)
                        
                        switch_dify_history_enable = ui.switch('Context memory', value=config.get("dify", "history_enable")).style(switch_internal_css)
                        textarea_dify_custom_params = ui.textarea(
                            label=f"Workflow custom parameters (JSON)", 
                            value=config.get("dify", "custom_params"), 
                            placeholder='inputsParameters to pass, note the JSON format',
                        ).style("width:200px;").tooltip('API link for sending HTTP requests')
            if config.get("webui", "show_card", "llm", "volcengine"):
                with ui.card().style(card_css):
                    ui.label("Volcengine")
                    with ui.row():
                        input_volcengine_model = ui.input(label='Model ID', value=config.get("volcengine", "model"), placeholder='Inference endpoint name').tooltip('Inference endpoint name')
                        
                        input_volcengine_api_key = ui.input(label='APIKey', value=config.get("volcengine", "api_key"), placeholder='APIKey, obtained from the API page').tooltip('APIKey, obtained from the API page')
                        input_volcengine_preset = ui.input(label='Preset', value=config.get("volcengine", "preset"), placeholder='Used to specify a set of predefined settings so the model better fits specific conversation scenarios.').style("width:500px") 
                        switch_volcengine_history_enable = ui.switch('Context memory', value=config.get("volcengine", "history_enable")).style(switch_internal_css)
                        input_volcengine_history_max_len = ui.input(label='Max memory length', value=config.get("volcengine", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')
                        switch_volcengine_stream = ui.switch('Streaming output', value=config.get("volcengine", "stream")).style(switch_internal_css)
                        

            if config.get("webui", "show_card", "llm", "custom_llm"):
                with ui.card().style(card_css):
                    ui.label("Custom LLM")
                    with ui.row():
                        textarea_custom_llm_url = ui.textarea(
                            label=f"API URL", 
                            value=config.get("custom_llm", "url"), 
                            placeholder='API link for sending HTTP requests', 
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip('API link for sending HTTP requests')
                        textarea_custom_llm_method = ui.select(label=f"APIType", value=config.get("custom_llm", "method"), options={"GET": "GET", "POST": "POST"}).style("width:100px;").tooltip('APIType')
                        textarea_custom_llm_headers = ui.textarea(label=f"Request headers", value=config.get("custom_llm", "headers"), placeholder='Separate with line breaks, e.g.:Content-Type:application/json\nAuthorization:Bearer sk').style("width:300px;").tooltip('Separate with line breaks, e.g.:Content-Type:application/json\nAuthorization:Bearer sk')
                        textarea_custom_llm_proxies = ui.textarea(label=f"Proxy", value=config.get("custom_llm", "proxies"), placeholder='requestsLibrary proxy configuration method, json data uses"Double quotes').style("width:200px;").tooltip('requestsLibrary proxy configuration method, json data uses"Double quotes')
                    with ui.row():
                        select_custom_llm_body_type = ui.select(label=f"Request bodyType", value=config.get("custom_llm", "body_type"), options={"json": "json", "raw": "raw"}).style("width:150px;").tooltip('Request bodyType')
                        textarea_custom_llm_body = ui.textarea(label=f"Request body", value=config.get("custom_llm", "body"), placeholder='Request body, write a string; note that variables must be wrapped in two curly braces {{}}; for json data use"Double quotes').style("width:300px;").tooltip('Request body, write a string; note that variables must be wrapped in two curly braces {{}}; for json data use"Double quotes')
                        select_custom_llm_resp_data_type = ui.select(label=f"Request responseData type", value=config.get("custom_llm", "resp_data_type"), options={"json": "json", "content": "content"}).style("width:150px;").tooltip('Request responseData type')
                        textarea_custom_llm_data_analysis = ui.textarea(label=f"Data parsing (executed with eval)", value=config.get("custom_llm", "data_analysis"), placeholder='Data parsing; do not modify the resp variable arbitrarily, it is used to parse the final returned data').style("width:300px;").tooltip('Data parsing; do not modify the resp variable arbitrarily, it is used to parse the final returned data')
                        textarea_custom_llm_resp_template = ui.textarea(label=f"Response content template", value=config.get("custom_llm", "resp_template"), placeholder='Do not delete the data variable arbitrarily; dynamic variables are supported; it will finally be merged into the complete content for audio synthesis').style("width:300px;").tooltip('Do not delete the data variable arbitrarily; dynamic variables are supported; it will finally be merged into the complete content for audio synthesis')

            if config.get("webui", "show_card", "llm", "llm_tpu"): 
                with ui.card().style(card_css):
                    ui.label("LLM_TPU")
                    with ui.row():
                        input_llm_tpu_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("llm_tpu", "api_ip_port"), 
                            placeholder='llm_tpuThe ip and Port address to listen on after starting the gradio web demo',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        switch_llm_tpu_history_enable = ui.switch('Context memory', value=config.get("llm_tpu", "history_enable")).style(switch_internal_css)
                        input_llm_tpu_history_max_len = ui.input(label='Max memory length', value=config.get("llm_tpu", "history_max_len"), placeholder='Maximum length of the Q&A string that can be remembered; when exceeded, the earliest remembered content is discarded, use with caution! Setting it too large may lose data')
                    
                    with ui.row():
                        input_llm_tpu_max_length = ui.input(label='max_length', value=config.get("llm_tpu", "max_length"), placeholder='max_length').style("width:200px;")
                        input_llm_tpu_temperature = ui.input(label='Temperature', value=config.get("llm_tpu", "temperature"), placeholder='(0, 1.0] Controls the randomness of the generated text. A higher temperature value makes the generated text more random and diverse, while a lower temperature value makes it more deterministic and consistent.').style("width:200px;")
                        input_llm_tpu_top_p = ui.input(label='Top p selection', value=config.get("llm_tpu", "top_p"), placeholder='[0, 1.0] NucleusSampling. This parameter controls the model to sample from tokens whose cumulative probability exceeds a certain threshold. A higher value produces more diversity, a lower value produces fewer but more deterministic Answers.').style("width:200px;")
                        
        with ui.tab_panel(tts_page).style(tab_panel_css):
            # General - synthesize preview audio
            async def tts_common_audio_synthesis():
                ui.notify(position="top", type="warning", message="Audio synthesis in progress, it will block other tasks from Running, please do not do anything else, check the Log and wait patiently")
                logger.warning("Audio synthesis in progress, it will block other tasks from Running, please do not do anything else, check the Log and wait patiently")
                
                content = input_tts_common_text.value
                audio_synthesis_type = select_tts_common_audio_synthesis_type.value

                # Synthesize audio using the local configuration, returns the audio path
                file_path = await audio.audio_synthesis_use_local_config(content, audio_synthesis_type)

                if file_path:
                    logger.info(f"Audio Synthesis succeeded, stored at:{file_path}")
                    ui.notify(position="top", type="positive", message=f"Audio Synthesis succeeded, stored at:{file_path}")
                else:
                    logger.error(f"Audio synthesis Failed! Please check the Log to troubleshootQuestion")
                    ui.notify(position="top", type="negative", message=f"Audio synthesis Failed! Please check the Log to troubleshootQuestion")
                    return

                def clear_tts_common_audio_card(file_path):
                    tts_common_audio_card.clear()
                    if common.del_file(file_path):
                        ui.notify(position="top", type="positive", message=f"File deleted successfully:{file_path}")
                    else:
                        ui.notify(position="top", type="negative", message=f"Failed to delete file:{file_path}")
                
                # Clear the card
                tts_common_audio_card.clear()
                tmp_label = ui.label(f"Audio Synthesis succeeded, stored at:{file_path}")
                tmp_label.move(tts_common_audio_card)
                audio_tmp = ui.audio(src=file_path)
                audio_tmp.move(tts_common_audio_card)
                button_audio_del = ui.button('Delete audio', on_click=lambda: clear_tts_common_audio_card(file_path), color=button_internal_color).style(button_internal_css)
                button_audio_del.move(tts_common_audio_card)
                
                
            with ui.card().style(card_css):
                ui.label("Synthesis test (for testing only; if you confirm using this TTS, go to Common Config to configure Speech synthesis)")
                with ui.row():
                    select_tts_common_audio_synthesis_type = ui.select(
                        label='Speech synthesis', 
                        options=audio_synthesis_type_options, 
                        value=config.get("audio_synthesis_type")
                    ).style("width:200px;")
                    input_tts_common_text = ui.input(label='Audio content to be synthesized', placeholder='Fill in the audio text content to be synthesized here', value="Fill in the audio text content to be synthesized here, for previewing the effect; Type changes take effect without saving.").style("width:350px;")
                    button_tts_common_audio_synthesis = ui.button('Preview', on_click=lambda: tts_common_audio_synthesis(), color=button_internal_color).style(button_internal_css)
                tts_common_audio_card = ui.card()
                with tts_common_audio_card.style(card_css):
                    with ui.row():
                        ui.label("The generated audio is shown here, only the most recently synthesized audio is shown, and you can delete the synthesized audio here")

            if config.get("webui", "show_card", "tts", "edge-tts"):
                with ui.card().style(card_css):
                    ui.label("Edge-TTS")
                    with ui.row():
                        with open('data/edge-tts-voice-list.txt', 'r') as file:
                            file_content = file.read()
                        # Split content by line and remove the line break at the end of each line
                        lines = file_content.strip().split('\n')
                        data_json = {}
                        for line in lines:
                            data_json[line] = line
                        select_edge_tts_voice = ui.select(
                            label='Speaker', 
                            options=data_json, 
                            value=config.get("edge-tts", "voice")
                        )

                        input_edge_tts_rate = ui.input(label='Speech rate gain', placeholder='Speech rate gain, default is +0%, can be increased or decreased; be careful not to lose the + - % symbols, otherwise it will affectSpeech synthesis', value=config.get("edge-tts", "rate")).style("width:150px;").tooltip("Speech rate gain, default is +0%, can be increased or decreased; be careful not to lose the + - % symbols, otherwise it will affectSpeech synthesis")

                        input_edge_tts_volume = ui.input(label='Volume gain', placeholder='Volume gain, default is +0%, can be increased or decreased; be careful not to lose the + - % symbols, otherwise it will affectSpeech synthesis', value=config.get("edge-tts", "volume")).style("width:150px;").tooltip("Volume gain, default is +0%, can be increased or decreased; be careful not to lose the + - % symbols, otherwise it will affectSpeech synthesis")
                        input_edge_tts_proxy = ui.input(label='HTTP proxy address', placeholder='Example:http://127.0.0.1:10809', value=config.get("edge-tts", "proxy")).style("width:300px;").tooltip("According to your actual proxy configuration, e.g.:http://127.0.0.1:10809")
                        
            if config.get("webui", "show_card", "tts", "vits"):
                with ui.card().style(card_css):
                    ui.label("VITS-Simple-API")
                    with ui.row():
                        select_vits_type = ui.select(
                            label='Type', 
                            options={'vits': 'vits', 'bert_vits2': 'bert_vits2', 'gpt_sovits': 'gpt_sovits'}, 
                            value=config.get("vits", "type")
                        ).style("width:200px;")
                        input_vits_config_path = ui.input(label='Config file path', placeholder='Model configuration file storage path', value=config.get("vits", "config_path")).style("width:200px;")

                        input_vits_api_ip_port = ui.input(
                            label='API address', 
                            placeholder='vits-simple-apiThe ip and Port address to listen on after starting', 
                            value=config.get("vits", "api_ip_port"),
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:300px;")
                    with ui.row():
                        # input_vits_id = ui.input(label='SpeakerID', placeholder='APIOn startup the configuration file ids are reassigned, generally in pinyin order, starting from 0', value=config.get("vits", "id")).style("width:200px;")
                        select_vits_id = ui.select(
                            label='SpeakerID', 
                            options={config.get("vits", "id"): config.get("vits", "id")}, 
                            value=config.get("vits", "id")
                        ).style("width:200px;")

                        async def vits_get_speaker_id():
                            try:
                                API_URL = urljoin(input_vits_api_ip_port.value, '/voice/speakers')

                                resp_data = await common.send_async_request(API_URL, "GET", resp_data_type="json")

                                if resp_data is None:
                                    content = "vits-simple-api speaker lookup failed, check both logs"
                                    logger.error(content)
                                    ui.notify(position="top", type="negative", message=content)
                                else:
                                    content = "vits-simple-api speaker lookup succeeded"
                                    logger.info(content)
                                    ui.notify(position="top", type="positive", message=content)

                                    data_json = {}
                                    if select_vits_type.value == "vits":
                                        for vits_info in resp_data["VITS"]:
                                            data_json[vits_info['id']] = vits_info['name']
                                        select_vits_id.set_options(data_json, value=int(config.get("vits", "id")))
                                    elif select_vits_type.value == "bert_vits2":
                                        for vits_info in resp_data["BERT-VITS2"]:
                                            data_json[vits_info['id']] = vits_info['name']
                                        select_vits_id.set_options(data_json, value=int(config.get("vits", "id")))
                                    elif select_vits_type.value == "gpt_sovits":
                                        for vits_info in resp_data["GPT-SOVITS"]:
                                            data_json[vits_info['id']] = vits_info['name']
                                        select_vits_gpt_sovits_id.set_options(data_json, value=int(config.get("vits", "gpt_sovits", "id")))
                                    
                            except Exception as e:
                                logger.error(traceback.format_exc())
                                logger.error(f'vits-simple-apiUnknown error: {e}')
                                ui.notify(position="top", type="negative", message=f'vits-simple-apiUnknown error: {e}')

                        
                        select_vits_lang = ui.select(
                            label='Language', 
                            options={'Auto': 'Auto', '中文': 'Chinese', '英文': 'English', '日文': 'Japanese'}, 
                            value=config.get("vits", "lang")
                        ).style("width:100px;")
                        input_vits_length = ui.input(label='Speech length', placeholder='Adjust speech length, equivalent to adjusting speech rate; the larger the value, the slower the speech', value=config.get("vits", "length")).style("width:200px;")

                        button_vits_get_speaker_id = ui.button('Retrieve speakers', on_click=lambda: vits_get_speaker_id(), color=button_internal_color).style(button_internal_css)
                
                    with ui.row():
                        input_vits_noise = ui.input(label='Noise', placeholder='Controls the degree of emotional variation', value=config.get("vits", "noise")).style("width:200px;")
                    
                        input_vits_noisew = ui.input(label='Noise deviation', placeholder='Controls the phoneme pronunciation length', value=config.get("vits", "noisew")).style("width:200px;")

                        input_vits_max = ui.input(label='Segment threshold', placeholder='Split into segments by punctuation; when the sum exceeds max it becomes one segment of text. max<=0 means no segmentation.', value=config.get("vits", "max")).style("width:200px;")
                        input_vits_format = ui.input(label='Audio format', placeholder='Supportswav,ogg,silk,mp3,flac', value=config.get("vits", "format")).style("width:200px;")

                        input_vits_sdp_radio = ui.input(label='SDP/DPMix ratio', placeholder='SDP/DPMix ratio: the proportion of SDP in synthesis; in theory the higher this ratio, the larger the variance of the synthesized speech intonation.', value=config.get("vits", "sdp_radio")).style("width:200px;")

                    with ui.expansion('GPT-SOVITS', icon="settings", value=True).classes('w-full'):
                        with ui.row():
                            select_vits_gpt_sovits_id = ui.select(
                                label='SpeakerID', 
                                options={config.get("vits", "gpt_sovits", "id"): config.get("vits", "gpt_sovits", "id")}, 
                                value=config.get("vits", "gpt_sovits", "id")
                            ).style("width:200px;")

                            select_vits_gpt_sovits_lang = ui.select(
                                label='Language', 
                                options={'auto': 'Auto', 'zh': 'Chinese', 'jp': 'Japanese', 'en': 'English'}, 
                                value=config.get("vits", "gpt_sovits", "lang")
                            ).style("width:100px;")
                            input_vits_gpt_sovits_format = ui.input(label='Audio format', value=config.get("vits", "gpt_sovits", "format"), placeholder='Supportswav,ogg,silk,mp3,flac').style("width:100px;")
                            input_vits_gpt_sovits_segment_size = ui.input(label='segment_size', value=config.get("vits", "gpt_sovits", "segment_size"), placeholder='segment_size').style("width:100px;")
                            input_vits_gpt_sovits_reference_audio = ui.input(label='Reference audio path', value=config.get("vits", "gpt_sovits", "reference_audio"), placeholder='Reference audio path').style("width:200px;")
                            input_vits_gpt_sovits_prompt_text = ui.input(label='Reference audio text content', value=config.get("vits", "gpt_sovits", "prompt_text"), placeholder='Reference audio text content').style("width:200px;")
                            select_vits_gpt_sovits_prompt_lang = ui.select(
                                label='Reference audio language', 
                                options={'auto': 'Auto', 'zh': 'Chinese', 'jp': 'Japanese', 'en': 'English'}, 
                                value=config.get("vits", "gpt_sovits", "prompt_lang")
                            ).style("width:150px;")
                        with ui.row():
                            input_vits_gpt_sovits_top_k = ui.input(label='top_k', value=config.get("vits", "gpt_sovits", "top_k"), placeholder='top_k').style("width:100px;")
                            input_vits_gpt_sovits_top_p = ui.input(label='top_p', value=config.get("vits", "gpt_sovits", "top_p"), placeholder='top_p').style("width:100px;")
                            input_vits_gpt_sovits_temperature = ui.input(label='temperature', value=config.get("vits", "gpt_sovits", "temperature"), placeholder='temperature').style("width:100px;")
                            input_vits_gpt_sovits_preset = ui.input(label='preset', value=config.get("vits", "gpt_sovits", "preset"), placeholder='preset').style("width:100px;")
                            

            if config.get("webui", "show_card", "tts", "bert_vits2"):
                with ui.card().style(card_css):
                    ui.label("bert_vits2")
                    with ui.row():
                        select_bert_vits2_type = ui.select(
                            label='Type', 
                            options={'hiyori': 'hiyori', '刘悦-中文特化API': '刘悦-中文特化API'}, 
                            value=config.get("bert_vits2", "type")
                        ).style("width:200px;")
                        
                    with ui.expansion('hiyori', icon="settings", value=True).classes('w-full'):
                        with ui.row():
                            input_bert_vits2_api_ip_port = ui.input(
                                label='API address', 
                                placeholder='bert_vits2The ip and Port address the Hiyori UI listens on after starting', 
                                value=config.get("bert_vits2", "api_ip_port"),
                                validation={
                                    'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                                }
                            ).style("width:300px;")
                            input_bert_vits2_model_id = ui.input(label='Model ID', placeholder='Reassign ids to the configuration file, generally in pinyin order, starting from 0', value=config.get("bert_vits2", "model_id")).style("width:200px;")
                            input_bert_vits2_speaker_name = ui.input(label='Speaker name', value=config.get("bert_vits2", "speaker_name"), placeholder='Name of the corresponding speaker in the configuration file').style("width:200px;")
                            input_bert_vits2_speaker_id = ui.input(label='SpeakerID', value=config.get("bert_vits2", "speaker_id"), placeholder='Reassign ids to the configuration file, generally in pinyin order, starting from 0').style("width:200px;")
                            
                            select_bert_vits2_language = ui.select(
                                label='Language', 
                                options={'auto': 'Auto', 'ZH': 'Chinese', 'JP': 'Japanese', 'EN': 'English'}, 
                                value=config.get("bert_vits2", "language")
                            ).style("width:100px;")
                            input_bert_vits2_length = ui.input(label='Speech length', placeholder='Adjust speech length, equivalent to adjusting speech rate; the larger the value, the slower the speech', value=config.get("bert_vits2", "length")).style("width:200px;")

                        with ui.row():
                            input_bert_vits2_noise = ui.input(label='Noise', value=config.get("bert_vits2", "noise"), placeholder='Controls the degree of emotional variation').style("width:200px;")
                            input_bert_vits2_noisew = ui.input(label='Noise deviation', value=config.get("bert_vits2", "noisew"), placeholder='Controls the phoneme pronunciation length').style("width:200px;")
                            input_bert_vits2_sdp_radio = ui.input(label='SDP/DPMix ratio', value=config.get("bert_vits2", "sdp_radio"), placeholder='SDP/DPMix ratio: the proportion of SDP in synthesis; in theory the higher this ratio, the larger the variance of the synthesized speech intonation.').style("width:200px;")
                        with ui.row():
                            input_bert_vits2_emotion = ui.input(label='emotion', value=config.get("bert_vits2", "emotion"), placeholder='emotion').style("width:200px;")
                            input_bert_vits2_style_text = ui.input(label='Style text', value=config.get("bert_vits2", "style_text"), placeholder='style_text').style("width:200px;")
                            input_bert_vits2_style_weight = ui.input(label='Style weight', value=config.get("bert_vits2", "style_weight"), placeholder='Bert mixing ratio of the main text and auxiliary text; 0 means main text only, 1 means auxiliary text only0.7').style("width:200px;")
                            switch_bert_vits2_auto_translate = ui.switch('Auto translation', value=config.get("bert_vits2", "auto_translate")).style(switch_internal_css)
                            switch_bert_vits2_auto_split = ui.switch('Auto split', value=config.get("bert_vits2", "auto_split")).style(switch_internal_css)
                    with ui.expansion('Liuyue Chinese-specialized API', icon="settings", value=True).classes('w-full'):
                        with ui.row():
                            input_bert_vits2_liuyue_zh_api_api_ip_port = ui.input(
                                label='API address', 
                                placeholder='The ip and Port address to listen on after the interface service starts', 
                                value=config.get("bert_vits2", "刘悦-中文特化API", "api_ip_port"),
                                validation={
                                    'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                                }
                            ).style("width:300px;")
                            input_bert_vits2_liuyue_zh_api_speaker = ui.input(label='Speaker name', value=config.get("bert_vits2", "刘悦-中文特化API", "speaker"), placeholder='Name of the corresponding speaker in the configuration file').style("width:200px;")
                            
                            select_bert_vits2_liuyue_zh_api_language = ui.select(
                                label='Language', 
                                options={'auto': 'Auto', 'ZH': 'Chinese', 'JP': 'Japanese', 'EN': 'English'}, 
                                value=config.get("bert_vits2", "刘悦-中文特化API", "language")
                            ).style("width:100px;")
                            input_bert_vits2_liuyue_zh_api_length_scale = ui.input(label='Speech length', placeholder='Adjust speech length, equivalent to adjusting speech rate; the larger the value, the slower the speech', value=config.get("bert_vits2", "刘悦-中文特化API", "length_scale")).style("width:200px;")
                            
                        with ui.row():
                            input_bert_vits2_liuyue_zh_api_interval_between_para = ui.input(label='interval_between_para', value=config.get("bert_vits2", "刘悦-中文特化API", "interval_between_para"), placeholder='interval_between_para').style("width:200px;")
                            input_bert_vits2_liuyue_zh_api_interval_between_sent = ui.input(label='interval_between_sent', value=config.get("bert_vits2", "刘悦-中文特化API", "interval_between_sent"), placeholder='interval_between_sent').style("width:200px;")
                           
                            input_bert_vits2_liuyue_zh_api_noise_scale = ui.input(label='Noise', value=config.get("bert_vits2", "刘悦-中文特化API", "noise_scale"), placeholder='Controls the degree of emotional variation').style("width:200px;")
                            input_bert_vits2_liuyue_zh_api_noise_scale_w = ui.input(label='Noise deviation', value=config.get("bert_vits2", "刘悦-中文特化API", "noise_scale_w"), placeholder='Controls the phoneme pronunciation length').style("width:200px;")
                            input_bert_vits2_liuyue_zh_api_sdp_radio = ui.input(label='SDP/DPMix ratio', value=config.get("bert_vits2", "刘悦-中文特化API", "sdp_radio"), placeholder='SDP/DPMix ratio: the proportion of SDP in synthesis; in theory the higher this ratio, the larger the variance of the synthesized speech intonation.').style("width:200px;")
                        with ui.row():
                            input_bert_vits2_liuyue_zh_api_emotion = ui.input(label='emotion', value=config.get("bert_vits2", "刘悦-中文特化API", "emotion"), placeholder='emotion').style("width:200px;")
                            input_bert_vits2_liuyue_zh_api_style_text = ui.input(label='Style text', value=config.get("bert_vits2", "刘悦-中文特化API", "style_text"), placeholder='style_text').style("width:200px;")
                            input_bert_vits2_liuyue_zh_api_style_weight = ui.input(label='Style weight', value=config.get("bert_vits2", "刘悦-中文特化API", "style_weight"), placeholder='Bert mixing ratio of the main text and auxiliary text; 0 means main text only, 1 means auxiliary text only0.7').style("width:200px;")
                            switch_bert_vits2_cut_by_sent = ui.switch('cut_by_sent', value=config.get("bert_vits2", "刘悦-中文特化API", "cut_by_sent")).style(switch_internal_css)
                            
            if config.get("webui", "show_card", "tts", "vits_fast"):
                with ui.card().style(card_css):
                    ui.label("VITS-Fast")
                    with ui.row():
                        input_vits_fast_config_path = ui.input(label='Config file path', placeholder='Path of the configuration file,For example:E:\\inference\\finetune_speaker.json', value=config.get("vits_fast", "config_path"))
        
                        input_vits_fast_api_ip_port = ui.input(
                            label='API address', 
                            placeholder='Link of the Running inference service (full URL required)', 
                            value=config.get("vits_fast", "api_ip_port"),
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        input_vits_fast_character = ui.input(label='Speaker', placeholder='Selected speaker, one of the speakers in the configuration file', value=config.get("vits_fast", "character"))

                        select_vits_fast_language = ui.select(
                            label='Language', 
                            options={'Auto detect': 'Auto detect', '日本語': 'Japanese', '简体中文': 'Simplified Chinese', 'English': 'English', 'Mix': 'Mix'}, 
                            value=config.get("vits_fast", "language")
                        )
                        input_vits_fast_speed = ui.input(label='Speech rate', placeholder='Speech rate, default:1', value=config.get("vits_fast", "speed"))
            
            if config.get("webui", "show_card", "tts", "elevenlabs"):
                with ui.card().style(card_css):
                    ui.label("elevenlabs")
                    with ui.row():
                        input_elevenlabs_api_key = ui.input(label='apiKey', placeholder='elevenlabsKey, can be left empty; by default there is also a certain free usage quota, exact amount unknown', value=config.get("elevenlabs", "api_key"))

                        input_elevenlabs_voice = ui.input(label='Speaker', placeholder='Selected speaker name', value=config.get("elevenlabs", "voice"))

                        input_elevenlabs_model = ui.input(label='Model', placeholder='Selected model', value=config.get("elevenlabs", "model"))
            
            
            if config.get("webui", "show_card", "tts", "openai_tts"): 
                with ui.card().style(card_css):
                    ui.label("OpenAI TTS")
                    with ui.row():
                        select_openai_tts_type = ui.select(
                            label='Type', 
                            options={'api': 'api', 'huggingface': 'huggingface'}, 
                            value=config.get("openai_tts", "type")
                        ).style("width:200px;")
                        input_openai_tts_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("openai_tts", "api_ip_port"), 
                            placeholder='huggingfaceCorresponding project onAPI address',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;")
                    with ui.row():
                        select_openai_tts_model = ui.select(
                            label='Model', 
                            options={'tts-1': 'tts-1', 'tts-1-hd': 'tts-1-hd'}, 
                            value=config.get("openai_tts", "model")
                        ).style("width:200px;")
                        select_openai_tts_voice = ui.select(
                            label='Speaker', 
                            options={'alloy': 'alloy', 'echo': 'echo', 'fable': 'fable', 'onyx': 'onyx', 'nova': 'nova', 'shimmer': 'shimmer'}, 
                            value=config.get("openai_tts", "voice")
                        ).style("width:200px;")
                        input_openai_tts_api_key = ui.input(label='api key', value=config.get("openai_tts", "api_key"), placeholder='OpenAI API KEY').style("width:200px;")
                  
            if config.get("webui", "show_card", "tts", "gradio_tts"): 
                with ui.card().style(card_css):
                    ui.label("Gradio")
                    with ui.row():
                        textarea_gradio_tts_request_parameters = ui.textarea(label='Request parameters', value=config.get("gradio_tts", "request_parameters"), placeholder='Be sure to pay attention to the format! {content} is used to replace the text to be synthesized.\nurl is the request address;\nfn_index is the index corresponding to the api;\ndata_analysis is the data parsing rule, currently only index lookup on tuple and list data is supported, please refer to the template for configuration\nThe keys do not affect the request; note that the parameter order must match the API request\nThe data can then be converted from dict to str with the json library, which makes configuration much more reliable').style("width:800px;")
           
            if config.get("webui", "show_card", "tts", "gpt_sovits"): 
                with ui.card().style(card_css):
                    ui.label("GPT-SoVITS")
                    with ui.row():
                        select_gpt_sovits_type = ui.select(
                            label='APIType', 
                            options={
                                'api':'api', 
                                'api_0322':'api_0322', 
                                'api_0706':'api_0706', 
                                'v2_api_0821': 'v2_api_0821', 
                                'webtts':'WebTTS', 
                                'gradio_0322':'gradio_0322',
                            }, 
                            value=config.get("gpt_sovits", "type")
                        ).style("width:100px;")
                        input_gpt_sovits_gradio_ip_port = ui.input(
                            label='Gradio API address', 
                            value=config.get("gpt_sovits", "gradio_ip_port"), 
                            placeholder='Address gradio listens on after the official webui program starts',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;")
                        input_gpt_sovits_api_ip_port = ui.input(
                            label='API address(http)', 
                            value=config.get("gpt_sovits", "api_ip_port"), 
                            placeholder='Address the official API program listens on after startup',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;")
                        
                    
                    with ui.row():
                        input_gpt_sovits_gpt_model_path = ui.input(
                            label='GPTModel path', 
                            value=config.get("gpt_sovits", "gpt_model_path"), 
                            placeholder='GPTModel path, fill in an absolute path'
                        ).style("width:300px;")
                        input_gpt_sovits_sovits_model_path = ui.input(label='SOVITSModel path', value=config.get("gpt_sovits", "sovits_model_path"), placeholder='SOVITSModel path, fill in an absolute path').style("width:300px;")
                        button_gpt_sovits_set_model = ui.button('Load model', on_click=lambda: gpt_sovits_set_model(), color=button_internal_color).style(button_internal_css)
                    
                    with ui.card().style(card_css):
                        ui.label("api")
                        with ui.row():
                            input_gpt_sovits_ref_audio_path = ui.input(label='Reference audio path', value=config.get("gpt_sovits", "ref_audio_path"), placeholder='Reference audio path, an absolute path is recommended').style("width:300px;")
                            input_gpt_sovits_prompt_text = ui.input(label='Text of the reference audio', value=config.get("gpt_sovits", "prompt_text"), placeholder='Text of the reference audio').style("width:200px;")
                            select_gpt_sovits_prompt_language = ui.select(
                                label='Language of the reference audio', 
                                options={'中文': 'Chinese', '日文': 'Japanese', '英文': 'English'}, 
                                value=config.get("gpt_sovits", "prompt_language")
                            ).style("width:150px;")
                            select_gpt_sovits_language = ui.select(
                                label='Language to synthesize', 
                                options={'Auto detect': 'Auto detect', '中文': 'Chinese', '日文': 'Japanese', '英文': 'English'}, 
                                value=config.get("gpt_sovits", "language")
                            ).style("width:150px;")
                            select_gpt_sovits_cut = ui.select(
                                label='Sentence splitting', 
                                options={'不切': 'No split', '凑四句一切': 'Split every 4 sentences', '凑50字一切': 'Split every 50 characters', '按中文句号。切': 'Split at Chinese periods', '按英文句号.切': 'Split at English periods', '按标点符号切': 'Split at punctuation'}, 
                                value=config.get("gpt_sovits", "cut")
                            ).style("width:200px;")
                    
                    with ui.card().style(card_css):
                        ui.label("api_0322 | gradio_0322")
                        with ui.row():
                            input_gpt_sovits_api_0322_ref_audio_path = ui.input(label='Reference audio path', value=config.get("gpt_sovits", "api_0322", "ref_audio_path"), placeholder='Reference audio path, an absolute path is recommended').style("width:300px;")
                            input_gpt_sovits_api_0322_prompt_text = ui.input(label='Text of the reference audio', value=config.get("gpt_sovits", "api_0322", "prompt_text"), placeholder='Text of the reference audio').style("width:200px;")
                            select_gpt_sovits_api_0322_prompt_lang = ui.select(
                                label='Language of the reference audio', 
                                options={'中文': 'Chinese', '日文': 'Japanese', '英文': 'English'}, 
                                value=config.get("gpt_sovits", "api_0322", "prompt_lang")
                            ).style("width:150px;")
                            select_gpt_sovits_api_0322_text_lang = ui.select(
                                label='Language to synthesize', 
                                options={'Auto detect': 'Auto detect', '中文': 'Chinese', '日文': 'Japanese', '英文': 'English', '中英混合': 'Chinese + English mixed', '日英混合': 'Japanese + English mixed', '多语种混合': 'Multilingual mixed'}, 
                                value=config.get("gpt_sovits", "api_0322", "text_lang")
                            ).style("width:150px;")
                            select_gpt_sovits_api_0322_text_split_method = ui.select(
                                label='Sentence splitting', 
                                options={'不切': 'No split', '凑四句一切': 'Split every 4 sentences', '凑50字一切': 'Split every 50 characters', '按中文句号。切': 'Split at Chinese periods', '按英文句号.切': 'Split at English periods', '按标点符号切': 'Split at punctuation'}, 
                                value=config.get("gpt_sovits", "api_0322", "text_split_method")
                            ).style("width:200px;")
                        with ui.row():
                            input_gpt_sovits_api_0322_top_k = ui.input(label='top_k', value=config.get("gpt_sovits", "api_0322", "top_k"), placeholder='top_k').style("width:100px;")
                            input_gpt_sovits_api_0322_top_p = ui.input(label='top_p', value=config.get("gpt_sovits", "api_0322", "top_p"), placeholder='top_p').style("width:100px;")
                            input_gpt_sovits_api_0322_temperature = ui.input(label='temperature', value=config.get("gpt_sovits", "api_0322", "temperature"), placeholder='temperature').style("width:100px;")
                            input_gpt_sovits_api_0322_batch_size = ui.input(label='batch_size', value=config.get("gpt_sovits", "api_0322", "batch_size"), placeholder='batch_size').style("width:100px;")
                            input_gpt_sovits_api_0322_speed_factor = ui.input(label='speed_factor', value=config.get("gpt_sovits", "api_0322", "speed_factor"), placeholder='speed_factor').style("width:100px;")
                            input_gpt_sovits_api_0322_fragment_interval = ui.input(label='Segment interval (seconds)', value=config.get("gpt_sovits", "api_0322", "fragment_interval"), placeholder='fragment_interval').style("width:100px;")
                            switch_gpt_sovits_api_0322_split_bucket = ui.switch('split_bucket', value=config.get("gpt_sovits", "api_0322", "split_bucket")).style(switch_internal_css)
                            switch_gpt_sovits_api_0322_return_fragment = ui.switch('return_fragment', value=config.get("gpt_sovits", "api_0322", "return_fragment")).style(switch_internal_css)
                    
                    with ui.card().style(card_css):
                        ui.label("api_0706")
                        with ui.row():
                            input_gpt_sovits_api_0706_refer_wav_path = ui.input(label='Reference audio path', value=config.get("gpt_sovits", "api_0706", "refer_wav_path"), placeholder='Reference audio path, an absolute path is recommended').style("width:300px;")
                            input_gpt_sovits_api_0706_prompt_text = ui.input(label='Text of the reference audio', value=config.get("gpt_sovits", "api_0706", "prompt_text"), placeholder='Text of the reference audio').style("width:200px;")
                            select_gpt_sovits_api_0706_prompt_language = ui.select(
                                label='Language of the reference audio', 
                                options={'中文': 'Chinese', '日文': 'Japanese', '英文': 'English'}, 
                                value=config.get("gpt_sovits", "api_0706", "prompt_language")
                            ).style("width:150px;")
                            select_gpt_sovits_api_0706_text_language = ui.select(
                                label='Language to synthesize', 
                                options={'Auto detect': 'Auto detect', '中文': 'Chinese', '日文': 'Japanese', '英文': 'English', '中英混合': 'Chinese + English mixed', '日英混合': 'Japanese + English mixed', '多语种混合': 'Multilingual mixed'}, 
                                value=config.get("gpt_sovits", "api_0706", "text_language")
                            ).style("width:150px;")
                            input_gpt_sovits_api_0706_cut_punc = ui.input(label='Text splitting', value=config.get("gpt_sovits", "api_0706", "cut_punc"), placeholder='Text split symbol setting, symbol range: ,.;?!…').style("width:200px;")
                    
                    with ui.card().style(card_css):
                        ui.label("v2_api_0821")
                        with ui.row():
                            input_gpt_sovits_v2_api_0821_ref_audio_path = ui.input(label='Reference audio path', value=config.get("gpt_sovits", "v2_api_0821", "ref_audio_path"), placeholder='Reference audio path, an absolute path is recommended').style("width:300px;")
                            input_gpt_sovits_v2_api_0821_prompt_text = ui.input(label='Text of the reference audio', value=config.get("gpt_sovits", "v2_api_0821", "prompt_text"), placeholder='Text of the reference audio').style("width:200px;")
                            select_gpt_sovits_v2_api_0821_prompt_lang = ui.select(
                                label='Language of the reference audio', 
                                options={'zh':'Chinese', 'ja':'Japanese', 'en':'English'}, 
                                value=config.get("gpt_sovits", "v2_api_0821", "prompt_lang")
                            ).style("width:150px;")
                            select_gpt_sovits_v2_api_0821_text_lang = ui.select(
                                label='Language to synthesize', 
                                options={
                                    "all_zh": "Chinese",
                                    "all_yue": "Cantonese",
                                    "en": "English",
                                    "all_ja": "Japanese",
                                    "all_ko": "Korean",
                                    "zh": "Chinese-English mix",
                                    "yue": "Cantonese-English mix",
                                    "ja": "Japanese-English mix",
                                    "ko": "Korean-English mix",
                                    "auto": "Multilingual mix",    #Multilingual startup split recognition language
                                    "auto_yue": "Multilingual mix (Cantonese)",
                                }, 
                                value=config.get("gpt_sovits", "v2_api_0821", "text_lang")
                            ).style("width:150px;")
                            select_gpt_sovits_v2_api_0821_text_split_method = ui.select(
                                label='Sentence splitting', 
                                options={
                                    'cut0':'No split', 
                                    'cut1':'Split every 4 sentences', 
                                    'cut2':'Split every 50 characters', 
                                    'cut3':'Split at Chinese periods', 
                                    'cut4':'Split at English periods',
                                    'cut5':'Split at punctuation'
                                }, 
                                value=config.get("gpt_sovits", "v2_api_0821", "text_split_method")
                            ).style("width:200px;")
                        with ui.row():
                            input_gpt_sovits_v2_api_0821_top_k = ui.input(label='top_k', value=config.get("gpt_sovits", "v2_api_0821", "top_k"), placeholder='top_k').style("width:100px;")
                            input_gpt_sovits_v2_api_0821_top_p = ui.input(label='top_p', value=config.get("gpt_sovits", "v2_api_0821", "top_p"), placeholder='top_p').style("width:100px;")
                            input_gpt_sovits_v2_api_0821_temperature = ui.input(label='temperature', value=config.get("gpt_sovits", "v2_api_0821", "temperature"), placeholder='temperature').style("width:100px;")
                            input_gpt_sovits_v2_api_0821_batch_size = ui.input(label='batch_size', value=config.get("gpt_sovits", "v2_api_0821", "batch_size"), placeholder='batch_size').style("width:100px;")
                            input_gpt_sovits_v2_api_0821_batch_threshold = ui.input(label='batch_threshold', value=config.get("gpt_sovits", "v2_api_0821", "batch_threshold"), placeholder='batch_threshold').style("width:100px;")
                            switch_gpt_sovits_v2_api_0821_split_bucket = ui.switch('split_bucket', value=config.get("gpt_sovits", "v2_api_0821", "split_bucket")).style(switch_internal_css)
                            input_gpt_sovits_v2_api_0821_speed_factor = ui.input(label='speed_factor', value=config.get("gpt_sovits", "v2_api_0821", "speed_factor"), placeholder='speed_factor').style("width:100px;")
                            input_gpt_sovits_v2_api_0821_fragment_interval = ui.input(label='Segment interval (seconds)', value=config.get("gpt_sovits", "v2_api_0821", "fragment_interval"), placeholder='fragment_interval').style("width:100px;")
                            input_gpt_sovits_v2_api_0821_seed = ui.input(label='seed', value=config.get("gpt_sovits", "v2_api_0821", "seed"), placeholder='seed').style("width:100px;")
                            input_gpt_sovits_v2_api_0821_media_type = ui.input(label='media_type', value=config.get("gpt_sovits", "v2_api_0821", "media_type"), placeholder='media_type').style("width:100px;")
                            switch_gpt_sovits_v2_api_0821_parallel_infer = ui.switch('parallel_infer', value=config.get("gpt_sovits", "v2_api_0821", "parallel_infer")).style(switch_internal_css)
                            input_gpt_sovits_v2_api_0821_repetition_penalty = ui.input(label='repetition_penalty', value=config.get("gpt_sovits", "v2_api_0821", "repetition_penalty"), placeholder='repetition_penalty').style("width:100px;")
                            

                    with ui.card().style(card_css):
                        ui.label("WebTTSRelated configuration")
                        with ui.row():
                            select_gpt_sovits_webtts_version = ui.select(
                                label='Version', 
                                options={
                                    '1':'1', 
                                    '1.4':'1.4', 
                                    '2':'2'
                                }, 
                                value=config.get("gpt_sovits", "webtts", "version")
                            ).style("width:80px;")
                            input_gpt_sovits_webtts_api_ip_port = ui.input(label='API address', value=config.get("gpt_sovits", "webtts", "api_ip_port"), placeholder='APIListen address').style("width:200px;")
                            input_gpt_sovits_webtts_spk = ui.input(label='Timbre', value=config.get("gpt_sovits", "webtts", "spk"), placeholder='Timbre').style("width:100px;")
                            select_gpt_sovits_webtts_lang = ui.select(
                                label='Language', 
                                options={
                                    'zh':'Chinese', 
                                    'en':'English', 
                                    'jp':'Japanese'
                                }, 
                                value=config.get("gpt_sovits", "webtts", "lang")
                            ).style("width:100px;")
                            input_gpt_sovits_webtts_speed = ui.input(label='Speech rate', value=config.get("gpt_sovits", "webtts", "speed"), placeholder='Speech rate').style("width:100px;")
                            input_gpt_sovits_webtts_emotion = ui.input(label='Emotion', value=config.get("gpt_sovits", "webtts", "emotion"), placeholder='Emotion').style("width:100px;")
        
            
            if config.get("webui", "show_card", "tts", "azure_tts"): 
                with ui.card().style(card_css):
                    ui.label("azure_tts")
                    with ui.row():
                        input_azure_tts_subscription_key = ui.input(label='Key', value=config.get("azure_tts", "subscription_key"), placeholder='After applying to activate the service, you will naturally see it').style("width:200px;")
                        input_azure_tts_region = ui.input(label='Region', value=config.get("azure_tts", "region"), placeholder='After applying to activate the service, you will naturally see it').style("width:200px;")
                        input_azure_tts_voice_name = ui.input(label='Speaker name', value=config.get("azure_tts", "voice_name"), placeholder='Speech StudioPlatformPreview and get the speaker names').style("width:200px;")
            
            
            if config.get("webui", "show_card", "tts", "cosyvoice"): 
                with ui.card().style(card_css):
                    ui.label("CosyVoice")
                    with ui.row():
                        select_cosyvoice_type = ui.select(
                            label='Type', 
                            options={"api_0819": "api_0819", "gradio_0707": "gradio_0707"}, 
                            value=config.get("cosyvoice", "type")
                        ).style("width:150px").tooltip("ConnectedAPIType")
                        input_cosyvoice_gradio_ip_port = ui.input(
                            label='Gradio API address', 
                            value=config.get("cosyvoice", "gradio_ip_port"), 
                            placeholder='Address gradio listens on after the official webui program starts',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip("To connect the webui gradio interface, fill in the webui address")
                        input_cosyvoice_api_ip_port = ui.input(
                            label='HTTP API address', 
                            value=config.get("cosyvoice", "api_ip_port"), 
                            placeholder='APIAPI request address after the program starts',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip("To connect the api interface, fill in the api endpoint address")
                    
                    with ui.row():
                        with ui.card().style(card_css):
                            ui.label("gradio_0707")
                            with ui.row():
                                select_cosyvoice_gradio_0707_mode_checkbox_group = ui.select(
                                    label='Inference mode', 
                                    options={'预训练音色': '预训练音色', '3s极速复刻': '3s极速复刻', '跨语种复刻': '跨语种复刻', '自然语言控制': '自然语言控制'}, 
                                    value=config.get("cosyvoice", "gradio_0707", "mode_checkbox_group")
                                ).style("width:200px;")
                                select_cosyvoice_gradio_0707_sft_dropdown = ui.select(
                                    label='Pretrained voice', 
                                    options={'中文女': 'Chinese female', '中文男': 'Chinese male', '日语男': 'Japanese male', '粤语女': 'Cantonese female', '英文女': 'English female', '英文男': 'English male', '韩语女': 'Korean female'}, 
                                    value=config.get("cosyvoice", "gradio_0707", "sft_dropdown")
                                ).style("width:100px;")
                                input_cosyvoice_gradio_0707_prompt_text = ui.input(label='promptText', value=config.get("cosyvoice", "gradio_0707", "prompt_text"), placeholder='').style("width:200px;").tooltip("Leave empty if unused")
                                input_cosyvoice_gradio_0707_prompt_wav_upload = ui.input(label='promptAudio path', value=config.get("cosyvoice", "gradio_0707", "prompt_wav_upload"), placeholder='For example:E:\\1.wav').style("width:200px;").tooltip("Leave empty if unused,For example:E:\\1.wav")
                                input_cosyvoice_gradio_0707_instruct_text = ui.input(label='instructText', value=config.get("cosyvoice", "gradio_0707", "instruct_text"), placeholder='').style("width:200px;").tooltip("Leave empty if unused")
                                input_cosyvoice_gradio_0707_seed = ui.input(label='Random inference seed', value=config.get("cosyvoice", "gradio_0707", "seed"), placeholder='Default:0').style("width:100px;").tooltip("Random inference seed")
                    with ui.row():
                        with ui.card().style(card_css):
                            ui.label("api_0819")
                            with ui.row():
                                input_cosyvoice_api_0819_speaker = ui.input(label='Speaker', value=config.get("cosyvoice", "api_0819", "speaker"), placeholder='').style("width:200px;").tooltip("Check it yourself")
                                input_cosyvoice_api_0819_new = ui.input(label='new', value=config.get("cosyvoice", "api_0819", "new"), placeholder='0').style("width:200px;").tooltip("Check it yourself")
                                input_cosyvoice_api_0819_speed = ui.input(label='Speech rate', value=config.get("cosyvoice", "api_0819", "speed"), placeholder='1').style("width:200px;").tooltip("Speech rate")
            
            if config.get("webui", "show_card", "tts", "f5_tts"): 
                with ui.card().style(card_css):
                    ui.label("F5-TTS")
                    with ui.row():
                        select_f5_tts_type = ui.select(
                            label='Type', 
                            options={"gradio_1023": "gradio_1023"}, 
                            value=config.get("f5_tts", "type")
                        ).style("width:150px").tooltip("ConnectedAPIType")
                        input_f5_tts_gradio_ip_port = ui.input(
                            label='Gradio API address', 
                            value=config.get("f5_tts", "gradio_ip_port"), 
                            placeholder='Address gradio listens on after the official webui program starts',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip("To connect the webui gradio interface, fill in the webui address")

                        select_f5_tts_model = ui.select(
                            label='Model', 
                            options={'F5-TTS': 'F5-TTS', 'E2-TTS': 'E2-TTS'}, 
                            value=config.get("f5_tts", "model")
                        ).style("width:100px;")
                        input_f5_tts_ref_audio_orig = ui.input(label='Reference audio path', value=config.get("f5_tts", "ref_audio_orig"), placeholder='For example:E:\\1.wav').style("width:200px;").tooltip("Reference audio path")
                        input_f5_tts_ref_text = ui.input(label='Reference text', value=config.get("f5_tts", "ref_text"), placeholder='Audio text').style("width:200px;").tooltip("Reference text,For example:E:\\1.wav")
                        switch_f5_tts_remove_silence = ui.switch('remove_silence', value=config.get("f5_tts", "remove_silence")).style(switch_internal_css)
                        input_f5_tts_cross_fade_duration = ui.input(label='cross_fade_duration', value=config.get("f5_tts", "cross_fade_duration"), placeholder='0.15').style("width:100px;").tooltip("cross_fade_duration")
                        input_f5_tts_speed = ui.input(label='Speech rate', value=config.get("f5_tts", "speed"), placeholder='Speech rate').style("width:100px;").tooltip("Speech rate, default:1")

            if config.get("webui", "show_card", "tts", "multitts"): 
                with ui.card().style(card_css):
                    ui.label("MultiTTS")
                    with ui.row():
                        input_multitts_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("multitts", "api_ip_port"), 
                            placeholder='MultiTTSIP address and Port number of the device it runs on',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip("MultiTTSIP address and Port number of the device it runs on")
                        input_multitts_speed = ui.input(label='Speech rate', value=config.get("multitts", "speed"), placeholder='0-100').style("width:100px;").tooltip("Speech rate, default:1")
                        input_multitts_volume = ui.input(label='Volume', value=config.get("multitts", "volume"), placeholder='0-100').style("width:100px;").tooltip("Volume: default50")
                        input_multitts_pitch = ui.input(label='Pitch', value=config.get("multitts", "pitch"), placeholder='0-100').style("width:100px;").tooltip("Pitch: default50")
                        input_multitts_voice = ui.input(label='VoiceID', value=config.get("multitts", "voice"), placeholder='Leave empty to use the default selected speaker').style("width:200px;").tooltip("Leave empty to use the default selected speaker")
            if config.get("webui", "show_card", "tts", "melotts"): 
                with ui.card().style(card_css):
                    ui.label("MeloTTS")
                    with ui.row():
                        input_melotts_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("melotts", "api_ip_port"), 
                            placeholder='MeloTTS APIIP address and Port number of the device the program runs on',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip("MeloTTS APIIP address and Port number of the device the program runs on")
                        input_melotts_language = ui.input(label='Language', value=config.get("melotts", "language"), placeholder='0-100').style("width:100px;").tooltip("Speech rate, default:1")
                        select_melotts_device = ui.select(
                            label='device', 
                            options={'auto': 'auto', 'cuda': 'cuda', 'cpu': 'cpu'}, 
                            value=config.get("melotts", "device")
                        ).style("width:100px;")
                        switch_melotts_use_hf = ui.switch('Use the HF default model', value=config.get("melotts", "use_hf")).style(switch_internal_css)
                        input_melotts_config_path = ui.input(label='Config file path', value=config.get("melotts", "config_path"), placeholder='config.jsonPath').style("width:200px;").tooltip("config.jsonPath")
                        input_melotts_ckpt_path = ui.input(label='Model path', value=config.get("melotts", "ckpt_path"), placeholder='G_*.pthModel path').style("width:200px;").tooltip("G_*.pthModel path")
                        
                        async def melotts_load_model(data):
                            import aiohttp

                            ui.notify(position="top", type="info", message='MeloTTS Preparing to load the model')

                            API_URL = urljoin(data["api_ip_port"], '/init')

                            if "use_hf" in data and data["use_hf"]:
                                del data["config_path"]
                                del data["ckpt_path"]

                            try:
                                async with aiohttp.ClientSession() as session:
                                    async with session.post(API_URL, json=data) as response:
                                        if response.status == 200:
                                            ret = await response.json()
                                            logger.debug(ret)

                                            logger.info('MeloTTSModelloaded successfully')
                                            ui.notify(position="top", type="positive", message='MeloTTS model loaded successfully')
                                            return ret
                                        else: 
                                            logger.error('MeloTTSModel loadingFailure')
                                            ui.notify(position="top", type="negative", message='MeloTTSModel loadingFailure')
                                            return None

                            except aiohttp.ClientError as e:
                                logger.error(f'MeloTTSRequestFailure: {e}')
                                ui.notify(position="top", type="negative", message=f'MeloTTSRequestFailure: {e}')
                            except Exception as e:
                                logger.error(f'MeloTTSUnknown error: {e}')
                                ui.notify(position="top", type="negative", message=f'MeloTTSUnknown error: {e}')
                            
                            return None

                        button_melotts_load_model = ui.button('Load model', on_click=lambda: melotts_load_model(config.get("melotts")), color=button_internal_color).style(button_internal_css)
                    
                    with ui.row():
                        input_melotts_speaker_id = ui.input(label='SpeakerID', value=config.get("melotts", "speaker_id"), placeholder='Integer starting from 0, default:0').style("width:100px;").tooltip("Integer starting from 0, default:0")
                        input_melotts_sdp_ratio = ui.input(label='sdp_ratio', value=config.get("melotts", "sdp_ratio"), placeholder='sdp_ratio').style("width:100px;").tooltip("sdp_ratio")
                        input_melotts_noise_scale = ui.input(label='noise_scale', value=config.get("melotts", "noise_scale"), placeholder='noise_scale').style("width:100px;").tooltip("noise_scale")
                        input_melotts_noise_scale_w = ui.input(label='noise_scale_w', value=config.get("melotts", "noise_scale_w"), placeholder='noise_scale_w').style("width:100px;").tooltip("noise_scale_w")
                        input_melotts_speed = ui.input(label='Speech rate', value=config.get("melotts", "speed"), placeholder='0-10, default:1').style("width:100px;").tooltip("Speech rate, default:1")
            if config.get("webui", "show_card", "tts", "index_tts"): 
                with ui.card().style(card_css):
                    ui.label("Index-TTS")
                    with ui.row():
                        input_index_tts_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("index_tts", "api_ip_port"), 
                            placeholder='Index-TTS APIIP address and Port number of the device the program runs on',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        ).style("width:200px;").tooltip("Index-TTS APIIP address and Port number of the device the program runs on")
                        input_index_tts_prompt_audio = ui.input(label='promptAudio path', value=config.get("index_tts", "prompt_audio"), placeholder='For example:E:\\1.wav').style("width:200px;").tooltip("promptAudio path")
                        input_index_tts_temperature = ui.input(label='temperature', value=config.get("index_tts", "temperature"), placeholder='temperature').style("width:200px;").tooltip("temperature")
                        
        with ui.tab_panel(svc_page).style(tab_panel_css):
            if config.get("webui", "show_card", "svc", "ddsp_svc"):
                with ui.card().style(card_css):
                    ui.label("DDSP-SVC")
                    with ui.row():
                        switch_ddsp_svc_enable = ui.switch('Enable', value=config.get("ddsp_svc", "enable")).style(switch_internal_css)
                        input_ddsp_svc_config_path = ui.input(label='Config file path', placeholder='Path of the model configuration file config.yaml (can be left unconfigured here, not used for now)', value=config.get("ddsp_svc", "config_path"))
                        input_ddsp_svc_config_path.style("width:400px")

                        input_ddsp_svc_api_ip_port = ui.input(
                            label='API address', 
                            placeholder='flask_apiThe ip and Port the service Runs on,For example:http://127.0.0.1:6844', 
                            value=config.get("ddsp_svc", "api_ip_port"),
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        input_ddsp_svc_api_ip_port.style("width:400px")
                        input_ddsp_svc_fSafePrefixPadLength = ui.input(label='Safety prefix padding length', placeholder='Safety prefix padding length, unknown purpose, default:0', value=config.get("ddsp_svc", "fSafePrefixPadLength"))
                        input_ddsp_svc_fSafePrefixPadLength.style("width:300px")
                    with ui.row():
                        input_ddsp_svc_fPitchChange = ui.input(label='Pitch shift', placeholder='Pitch setting, default:0', value=config.get("ddsp_svc", "fPitchChange"))
                        input_ddsp_svc_fPitchChange.style("width:300px")
                        input_ddsp_svc_sSpeakId = ui.input(label='SpeakerID', placeholder='Speaker ID, must correspond to the model data, default:0', value=config.get("ddsp_svc", "sSpeakId"))
                        input_ddsp_svc_sSpeakId.style("width:400px")

                        input_ddsp_svc_sampleRate = ui.input(label='Sampling rate', placeholder='DAWRequired sampling rate, default:44100', value=config.get("ddsp_svc", "sampleRate"))
                        input_ddsp_svc_sampleRate.style("width:300px")
            
            if config.get("webui", "show_card", "svc", "so_vits_svc"):
                with ui.card().style(card_css):
                    ui.label("SO-VITS-SVC")
                    with ui.row():
                        switch_so_vits_svc_enable = ui.switch('Enable', value=config.get("so_vits_svc", "enable")).style(switch_internal_css)
                        input_so_vits_svc_config_path = ui.input(label='Config file path', placeholder='Path of the model configuration file config.json', value=config.get("so_vits_svc", "config_path"))
                        input_so_vits_svc_config_path.style("width:400px")
                    with ui.grid(columns=2):
                        input_so_vits_svc_api_ip_port = ui.input(
                            label='API address', 
                            placeholder='flask_api_full_songThe ip and Port the service Runs on,For example:http://127.0.0.1:1145', 
                            value=config.get("so_vits_svc", "api_ip_port"),
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        input_so_vits_svc_api_ip_port.style("width:400px")
                        input_so_vits_svc_spk = ui.input(label='Speaker', placeholder='Speaker, must correspond to the configuration file content', value=config.get("so_vits_svc", "spk"))
                        input_so_vits_svc_spk.style("width:400px") 
                        input_so_vits_svc_tran = ui.input(label='Pitch', placeholder='Pitch setting, default:1', value=config.get("so_vits_svc", "tran"))
                        input_so_vits_svc_tran.style("width:300px")
                        input_so_vits_svc_wav_format = ui.input(label='Output audio format', placeholder='Output format after audio synthesis', value=config.get("so_vits_svc", "wav_format"))
                        input_so_vits_svc_wav_format.style("width:300px") 
        with ui.tab_panel(visual_body_page).style(tab_panel_css):
            if config.get("webui", "show_card", "visual_body", "live2d"):
                with ui.card().style(card_css):
                    ui.label("Live2D")
                    with ui.row():
                        switch_live2d_enable = ui.switch('Enable', value=config.get("live2d", "enable")).style(switch_internal_css)
                        input_live2d_port = ui.input(label='Port', value=config.get("live2d", "port"), placeholder='webPort the service runs onPort, default: 12345, range: 0-65535, do not change it casually if nothing is wrong')
                        # input_live2d_name = ui.input(label='Model name', value=config.get("live2d", "name"), placeholder='Model name; models are stored under the Live2D\live2d-model path, please make sure the path matches the model content')

                        live2d_names = common.get_folder_names("Live2D/live2d-model") # Hard-coded path
                        logger.info(f"List of local Live2D model names:{live2d_names}")

                        data_json = {}
                        for line in live2d_names:
                            data_json[line] = line
                        # live2d_model_name = common.get_live2d_model_name("Live2D/js/model_name.js") # Hard-coded path
                        select_live2d_name = ui.select(
                            label='Model name', 
                            options=data_json, 
                            value=config.get("live2d", "name")
                        ).style("width:150px") 
            
            if config.get("webui", "show_card", "visual_body", "EasyAIVtuber"):
                with ui.card().style(card_css):
                    ui.label("EasyAIVtuber")
                    with ui.row():
                        input_EasyAIVtuber_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("EasyAIVtuber", "api_ip_port"), 
                            placeholder='The ip and port the EasyAIVtuber app connection listens onPort',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )

            if config.get("webui", "show_card", "visual_body", "digital_human_video_player"):
                with ui.card().style(card_css):
                    ui.label("Digital Human Video Player")
                    with ui.row():
                        select_digital_human_video_player_type = ui.select(
                            label='Type', 
                            options={
                                "easy_wav2lip": "easy_wav2lip", 
                                "sadtalker": "sadtalker", 
                                "genefaceplusplus": "GeneFacePlusPlus",
                                "musetalk": "MuseTalk",
                                "anitalker": "AniTalker",
                            }, 
                            value=config.get("digital_human_video_player", "type")
                        ).style("width:150px") 
                        input_digital_human_video_player_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("digital_human_video_player", "api_ip_port"), 
                            placeholder='The ip and port the Digital Human Video Player connection listens onPort',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                       
            if config.get("webui", "show_card", "visual_body", "metahuman_stream"):
                with ui.card().style(card_css):
                    ui.label("metahuman_stream")
                    with ui.row():
                        select_metahuman_stream_type = ui.select(
                            label='Type', 
                            options={'ernerf': 'ernerf', 'musetalk': 'musetalk', 'wav2lip': 'wav2lip'}, 
                            value=config.get("metahuman_stream", "type")
                        ).style("width:100px;")
                        input_metahuman_stream_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("metahuman_stream", "api_ip_port"), 
                            placeholder='metahuman_streamThe ip and port to listen on after the app starts the APIPort',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )

            if config.get("webui", "show_card", "visual_body", "live2d_TTS_LLM_GPT_SoVITS_Vtuber"):
                with ui.card().style(card_css):
                    ui.label("live2d_TTS_LLM_GPT_SoVITS_Vtuber")
                    with ui.row():
                        input_live2d_TTS_LLM_GPT_SoVITS_Vtuber_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("live2d_TTS_LLM_GPT_SoVITS_Vtuber", "api_ip_port"), 
                            placeholder='live2d_TTS_LLM_GPT_SoVITS_VtuberThe ip and port to listen on after the app starts the APIPort',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )            

            if config.get("webui", "show_card", "visual_body", "xuniren"):
                with ui.card().style(card_css):
                    ui.label("xuniren")
                    with ui.row():
                        input_xuniren_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("xuniren", "api_ip_port"), 
                            placeholder='xunirenThe ip and port to listen on after the app starts the APIPort',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
            
            if config.get("webui", "show_card", "visual_body", "unity"):
                with ui.card().style(card_css):
                    ui.label("Unity")
                    with ui.row():
                        # switch_unity_enable = ui.switch('Enable', value=config.get("unity", "enable")).style(switch_internal_css)
                        input_unity_api_ip_port = ui.input(
                            label='API address', 
                            value=config.get("unity", "api_ip_port"), 
                            placeholder='The ip and port the HTTP relay used to connect the Unity app listens onPort',
                            validation={
                                'Please enter a URL in the correct format': lambda value: common.is_url_check(value),
                            }
                        )
                        input_unity_password = ui.input(label='Password', value=config.get("unity", "password"), placeholder='Port of the HTTP relay used to connect the Unity appPassword')


        with ui.tab_panel(copywriting_page).style(tab_panel_css):
            with ui.row():
                switch_copywriting_auto_play = ui.switch('Auto play', value=config.get("copywriting", "auto_play")).style(switch_internal_css)
                switch_copywriting_random_play = ui.switch('Random audio playback', value=config.get("copywriting", "random_play")).style(switch_internal_css)
                input_copywriting_audio_interval = ui.input(label='Audio playbackInterval', value=config.get("copywriting", "audio_interval"), placeholder='CopywritingAudio playbackInterval between them. That is, the interval between the end of playback of the previous Copywriting and the start of playback of the next Copywriting.').tooltip('CopywritingAudio playbackInterval between them. That is, the interval between the end of playback of the previous Copywriting and the start of playback of the next Copywriting.')
                input_copywriting_switching_interval = ui.input(label='Audio switching interval', value=config.get("copywriting", "switching_interval"), placeholder='CopywritingSwitching interval between audio and Danmaku audio (and vice versa).\nThat is, while Copywriting is playing, if a Danmaku is triggered and synthesized, Copywriting playback is paused, then after waiting this interval, the Danmaku reply audio is played.').tooltip('nThat is, while Copywriting is playing, if a Danmaku is triggered and synthesized, Copywriting playback is paused, then after waiting this interval, the Danmaku reply audio is played.')
            with ui.row():
                input_copywriting_index = ui.input(label='Copywriting index', value="", placeholder='Order number of the copywriting group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                button_copywriting_add = ui.button('Add copywriting group', on_click=copywriting_add, color=button_internal_color).style(button_internal_css)
                button_copywriting_del = ui.button('Delete copywriting group', on_click=lambda: copywriting_del(input_copywriting_index.value), color=button_internal_color).style(button_internal_css)

            copywriting_config_var = {}
            copywriting_config_card = ui.card()
            for index, copywriting_config in enumerate(config.get("copywriting", "config")):
                with copywriting_config_card.style(card_css):
                    with ui.row():
                        copywriting_config_var[str(5 * index)] = ui.input(label=f"Copywriting storage path#{index + 1}", value=copywriting_config["file_path"], placeholder='Path where copywriting files are stored. Changing it is not recommended.').style("width:200px;").tooltip('Path where copywriting files are stored. Changing it is not recommended.')
                        copywriting_config_var[str(5 * index + 1)] = ui.input(label=f"Audio storage path#{index + 1}", value=copywriting_config["audio_path"], placeholder='Path where copywriting audio files are stored. Changing it is not recommended.').style("width:200px;").tooltip('Path where copywriting audio files are stored. Changing it is not recommended.')
                        copywriting_config_var[str(5 * index + 2)] = ui.input(label=f"Continuous play count#{index + 1}", value=copywriting_config["continuous_play_num"], placeholder='Number of audio files played consecutively from the play list; once exceeded, it switches to the next copywriting list').style("width:200px;").tooltip('Number of audio files played consecutively from the play list; once exceeded, it switches to the next copywriting list')
                        copywriting_config_var[str(5 * index + 3)] = ui.input(label=f"Continuous play time#{index + 1}", value=copywriting_config["max_play_time"], placeholder='Duration of audio played consecutively from the play list; once exceeded, it switches to the next copywriting list').style("width:200px;").tooltip('Duration of audio played consecutively from the play list; once exceeded, it switches to the next copywriting list')
                        copywriting_config_var[str(5 * index + 4)] = ui.textarea(label=f"Play list#{index + 1}", value=textarea_data_change(copywriting_config["play_list"]), placeholder='Enter the full names of the audio files to play here, then click Save Config. Copy the full file names from the audio list, separated by line breaks; do not fill in arbitrarily').style("width:500px;").tooltip('Enter the full names of the audio files to play here, then click Save Config. Copy the full file names from the audio list, separated by line breaks; do not fill in arbitrarily')

            with ui.card().style(card_css):
                ui.label("CopywritingAudio synthesis")
                with ui.row():
                    input_copywriting_text_path = ui.input(label='CopywritingText path', value=config.get("copywriting", "text_path"), placeholder='Path of the Copywriting text file to be synthesized').style("width:250px;").tooltip('Path of the Copywriting text file to be synthesized')
                    button_copywriting_text_load = ui.button('Load text', on_click=copywriting_text_load, color=button_internal_color).style(button_internal_css)
                    input_copywriting_audio_save_path = ui.input(label='Audio storage path', value=config.get("copywriting", "audio_save_path"), placeholder='Path where the audio is stored after synthesis').style("width:250px;").tooltip('Path where the audio is stored after synthesis')
                    # input_copywriting_chunking_stop_time = ui.input(label='Sentence pause duration', value=config.get("copywriting", "chunking_stop_time"), placeholder='After automatically splitting sentences by punctuation, the silent duration between 2 sentences').style("width:150px;")
                    select_copywriting_audio_synthesis_type = ui.select(
                        label='Speech synthesis', 
                        options=audio_synthesis_type_options, 
                        value=config.get("copywriting", "audio_synthesis_type")
                    ).style("width:200px;")
                with ui.row():
                    textarea_copywriting_text = ui.textarea(label='CopywritingText', value='', placeholder='Edit the text content of the Copywriting audio to be synthesized here. The Copywriting is automatically split according to the logic, then a complete audio file is synthesized according to the configuration.').style("width:1000px;").tooltip('Edit the text content of the Copywriting audio to be synthesized here. The Copywriting is automatically split according to the logic, then a complete audio file is synthesized according to the configuration.')
                with ui.row():
                    button_copywriting_save_text = ui.button('SaveCopywriting', on_click=copywriting_save_text, color=button_internal_color).style(button_internal_css)
                    button_copywriting_audio_synthesis = ui.button('Synthesize audio', on_click=lambda: copywriting_audio_synthesis(), color=button_internal_color).style(button_internal_css)
                copywriting_audio_card = ui.card()
                with copywriting_audio_card.style(card_css):
                    with ui.row():
                        ui.label("The generated Copywriting audio is shown here, only the most recently synthesized Copywriting audio is shown, and you can delete the synthesized audio here")
        with ui.tab_panel(home_page).style(tab_panel_css):
            from utils.webui_home import build_home_tab
            build_home_tab(config, lambda name: select_page(select_page.by_label[name]))

        with ui.tab_panel(voice_page).style(tab_panel_css):
            from utils.webui_voice import build_voice_tab
            # keep the 'Speech synthesis' select in Common config in sync with the Voice tab's saved engine
            build_voice_tab(config, on_engine_saved=lambda v: setattr(select_audio_synthesis_type, 'value', v))

        with ui.tab_panel(setup_page).style(tab_panel_css):
            from utils.webui_setup import build_setup_tab
            build_setup_tab(config)

        with ui.tab_panel(teach_page).style(tab_panel_css):
            from utils.webui_teach import build_teach_tab
            build_teach_tab(config)
        with ui.tab_panel(schedule_page).style(tab_panel_css):
            from utils.webui_schedule import build_schedule_tab
            build_schedule_tab(config)

        with ui.tab_panel(novel_page).style(tab_panel_css):
            from utils.webui_novel import build_novel_tab
            build_novel_tab(config)
        with ui.tab_panel(avatar_page).style(tab_panel_css):
            from utils.webui_avatar import build_avatar_tab
            build_avatar_tab(config)
        with ui.tab_panel(writer_page).style(tab_panel_css):
            from utils.webui_writer import build_writer_tab
            build_writer_tab(config)
        with ui.tab_panel(story_page).style(tab_panel_css):
            from utils.webui_story import build_story_tab
            build_story_tab(config)

        with ui.tab_panel(tools_page).style(tab_panel_css):
            from utils.webui_tools import build_tools_tab
            build_tools_tab(config)

        with ui.tab_panel(dashboard_page).style(tab_panel_css):
            from utils.webui_dashboard import build_dashboard_tab
            build_dashboard_tab(config)

        with ui.tab_panel(products_page).style(tab_panel_css):
            from utils.webui_products import build_products_tab
            build_products_tab(config)

        with ui.tab_panel(integral_page).style(tab_panel_css):
            with ui.card().style(card_css):
                ui.label("General")
                with ui.grid(columns=3):
                    switch_integral_enable = ui.switch('Enable', value=config.get("integral", "enable")).style(switch_internal_css)
            with ui.card().style(card_css):
                ui.label("Check-in")
                with ui.grid(columns=3):
                    switch_integral_sign_enable = ui.switch('Enable', value=config.get("integral", "sign", "enable")).style(switch_internal_css)
                    input_integral_sign_get_integral = ui.input(label='Points earned', value=config.get("integral", "sign", "get_integral"), placeholder='Points earned for a successful check-in, please enter a positive integer!')
                    textarea_integral_sign_cmd = ui.textarea(label='Command', value=textarea_data_change(config.get("integral", "sign", "cmd")), placeholder='DanmakuSendThe following commands can trigger the check-in function, separate commands with line breaks')
                with ui.card().style(card_css):
                    ui.label("Copywriting")
                    integral_sign_copywriting_var = {}
                    for index, integral_sign_copywriting in enumerate(config.get("integral", "sign", "copywriting")):
                        with ui.grid(columns=2):
                            integral_sign_copywriting_var[str(2 * index)] = ui.input(label=f"Check-in count interval#{index}", value=integral_sign_copywriting["sign_num_interval"], placeholder='Limit the number of check-ins within this interval to trigger the corresponding Copywriting, use the - sign to split the interval, boundary values included')
                            integral_sign_copywriting_var[str(2 * index + 1)] = ui.textarea(label=f"Copywriting#{index}", value=textarea_data_change(integral_sign_copywriting["copywriting"]), placeholder='Copywriting content triggered within this check-in interval, separated by line breaks').style("width:400px;")
            with ui.card().style(card_css):
                ui.label("Gift")
                with ui.grid(columns=3):
                    switch_integral_gift_enable = ui.switch('Enable', value=config.get("integral", "gift", "enable")).style(switch_internal_css)
                    input_integral_gift_get_integral_proportion = ui.input(label='Points earning ratio', value=config.get("integral", "gift", "get_integral_proportion"), placeholder='This ratio is tied to the real Gift amount (in yuan), the default is 1 yuan=10Points')
                with ui.card().style(card_css):
                    ui.label("Copywriting")
                    integral_gift_copywriting_var = {}
                    for index, integral_gift_copywriting in enumerate(config.get("integral", "gift", "copywriting")):
                        with ui.grid(columns=2):
                            integral_gift_copywriting_var[str(2 * index)] = ui.input(label=f"GiftPrice range#{index}", value=integral_gift_copywriting["gift_price_interval"], placeholder='Limit the Gift price within this interval to trigger the corresponding Copywriting, use the - sign to split the interval, boundary values included')
                            integral_gift_copywriting_var[str(2 * index + 1)] = ui.textarea(label=f"Copywriting#{index}", value=textarea_data_change(integral_gift_copywriting["copywriting"]), placeholder='Copywriting content triggered within this Gift interval, separated by line breaks').style("width:400px;")
            with ui.card().style(card_css):
                ui.label("Entrance")
                with ui.grid(columns=3):
                    switch_integral_entrance_enable = ui.switch('Enable', value=config.get("integral", "entrance", "enable")).style(switch_internal_css)
                    input_integral_entrance_get_integral = ui.input(label='Points earned', value=config.get("integral", "entrance", "get_integral"), placeholder='Points earned for a successful check-in, please enter a positive integer!')
                with ui.card().style(card_css):
                    ui.label("Copywriting")
                    integral_entrance_copywriting_var = {}
                    for index, integral_entrance_copywriting in enumerate(config.get("integral", "entrance", "copywriting")):
                        with ui.grid(columns=2):
                            integral_entrance_copywriting_var[str(2 * index)] = ui.input(label=f"EntranceCount interval#{index}", value=integral_entrance_copywriting["entrance_num_interval"], placeholder='Limit the number of Entrance within this interval to trigger the corresponding Copywriting, use the - sign to split the interval, boundary values included')
                            integral_entrance_copywriting_var[str(2 * index + 1)] = ui.textarea(label=f"Copywriting#{index}", value=textarea_data_change(integral_entrance_copywriting["copywriting"]), placeholder='Copywriting content triggered within this Entrance interval, separated by line breaks').style("width:400px;")
            with ui.card().style(card_css):
                ui.label("CRUD")
                with ui.card().style(card_css):
                    ui.label("Query")
                    with ui.grid(columns=3):
                        switch_integral_crud_query_enable = ui.switch('Enable', value=config.get("integral", "crud", "query", "enable")).style(switch_internal_css)
                        textarea_integral_crud_query_cmd = ui.textarea(label="Command", value=textarea_data_change(config.get("integral", "crud", "query", "cmd")), placeholder='DanmakuSendThe following commands can trigger the query function, separate commands with line breaks')
                        textarea_integral_crud_query_copywriting = ui.textarea(label="Copywriting", value=textarea_data_change(config.get("integral", "crud", "query", "copywriting")), placeholder='Copywriting content returned after the query function is triggered, separate commands with line breaks').style("width:400px;")

        with ui.tab_panel(talk_page).style(tab_panel_css): 
            with ui.row().style("position:fixed; top: 100px; right: 20px;"):
                with ui.expansion('ChatRecord', icon="question_answer", value=True):
                    scroll_area_chat_box = ui.scroll_area().style("width:500px; height:700px;")
                

            with ui.row():
                switch_talk_key_listener_enable = ui.switch('EnableKey listener', value=config.get("talk", "key_listener_enable")).style(switch_internal_css).tooltip("EnableAfter that, you can click the configured record key on the keyboard to start the voice recognition conversation function")
                switch_talk_direct_run_talk = ui.switch('Direct voice conversation', value=config.get("talk", "direct_run_talk")).style(switch_internal_css).tooltip("If Enabled, speech recognition starts directly on the first Run without manually clicking the start button. For systems where key presses cannot be triggered, use it together with continuous conversation and wake words")
                
                audio_device_info_list = common.get_all_audio_device_info("in")
                logger.info(f"Sound card input device={audio_device_info_list}")
                audio_device_info_dict = {str(device['device_index']): device['device_info'] for device in audio_device_info_list}

                logger.debug(f"Sound card input device={audio_device_info_dict}")

                select_talk_device_index = ui.select(
                    label='Sound card input device', 
                    options=audio_device_info_dict, 
                    value=config.get("talk", "device_index")
                ).style("width:300px;").tooltip('This is the sound card (microphone) for voice conversation input; just select your corresponding microphone. If you need to listen to the computer sound card, you can use a virtual sound card')
                
                switch_talk_no_recording_during_playback = ui.switch('Do not record during playback', value=config.get("talk", "no_recording_during_playback")).style(switch_internal_css).tooltip('AIDo not record while audio is playing, to prevent circular recording caused by the microphone being too close to the speakerQuestion')
                input_talk_no_recording_during_playback_sleep_interval = ui.input(label='Detection interval (seconds) for not recording during playback)', value=config.get("talk", "no_recording_during_playback_sleep_interval"), placeholder='This value normally does not need to be large, because when “Do not record during playback” is Enabled, the own speech of the AI will not be recorded; setting it too large slows down the time to resume recording').style("width:200px;").tooltip('This value normally does not need to be large, because the own speech of the AI will not be recorded')
                
                input_talk_username = ui.input(label='Your name', value=config.get("talk", "username"), placeholder='LogYour name in it, currently has no practical effect').style("width:200px;")
                switch_talk_continuous_talk = ui.switch('Continuous conversation', value=config.get("talk", "continuous_talk")).style(switch_internal_css).tooltip('Press the record key only once; afterwards there is no need to press it again, recording will automatically continue after splitting and waiting based on the silence threshold')
            with ui.row():
                data_json = {}
                for line in ["google", "baidu", "faster_whisper", "sensevoice"]:
                    data_json[line] = line
                select_talk_type = ui.select(
                    label='RecordingType', 
                    options=data_json, 
                    value=config.get("talk", "type")
                ).style("width:200px;").tooltip('Select the one to useSTTType')

                with open('data/keyboard.txt', 'r') as file:
                    file_content = file.read()
                # Split content by line and remove the line break at the end of each line
                lines = file_content.strip().split('\n')
                data_json = {}
                for line in lines:
                    data_json[line] = line
                select_talk_trigger_key = ui.select(
                    label='Record key', 
                    options=data_json, 
                    value=config.get("talk", "trigger_key"),
                    with_input=True,
                    clearable=True
                ).style("width:200px;").tooltip('Press this key to trigger recording, just press it once')
                select_talk_stop_trigger_key = ui.select(
                    label='Stop-recording key', 
                    options=data_json, 
                    value=config.get("talk", "stop_trigger_key"),
                    with_input=True,
                    clearable=True
                ).style("width:200px;").tooltip('Press this key to Stop recording, just press it once')

                input_talk_volume_threshold = ui.input(label='Volume threshold', value=config.get("talk", "volume_threshold"), placeholder='Volume threshold, the starting volume value that triggers recording, please fine-tune it to the best value for your microphone').style("width:100px;").tooltip('Volume threshold, the starting volume value that triggers recording, please fine-tune it to the best value for your microphone')
                input_talk_silence_threshold = ui.input(label='Stop-recording count', value=config.get("talk", "silence_threshold"), placeholder='Stop-recording count refers to the count of volume below the start value; the larger this value, the slower the audio is split, i.e. it waits longer before Stopping recording, but it should not be too small, otherwise recording stops halfway through speaking').style("width:100px;").tooltip('Silence threshold, the minimum volume value that triggers the Stop path, please fine-tune it to the best value for your microphone')
                input_talk_silence_CHANNELS = ui.input(label='CHANNELS', value=config.get("talk", "CHANNELS"), placeholder='Parameters used for recording').style("width:100px;")
                input_talk_silence_RATE = ui.input(label='RATE', value=config.get("talk", "RATE"), placeholder='Parameters used for recording').style("width:100px;")
                switch_talk_show_chat_log = ui.switch('ChatRecord', value=config.get("talk", "show_chat_log")).style(switch_internal_css)
            
            with ui.row():
                textarea_talk_chat_box = ui.textarea(label='ChatBox - chat with the AI', value="", placeholder='Fill in the conversation content here to chat directly (configure Chat Mode beforehand, remember to Run first)').style("width:500px;").tooltip("Fill in the conversation content here to chat directly (configure Chat Mode beforehand, remember to Run first)")
                
                '''
                    ChatPage-related functions
                '''

                # Send ChatBox content
                async def talk_chat_box_send():
                    global running_flag
                    
                    if running_flag != 1:
                        ui.notify(position="top", type="info", message="Please click “Run” first, then chat")
                        return

                    # Get the Username and text content
                    username = input_talk_username.value
                    content = textarea_talk_chat_box.value

                    # Clear the Chat box
                    textarea_talk_chat_box.value = ""

                    data = {
                        "type": "comment",
                        "data": {
                            "type": "comment",
                            "platform": "webui",
                            "username": username,
                            "content": content
                        }
                    }

                    logger.debug(f"data={data}")

                    main_api_ip = "127.0.0.1" if config.get("api_ip") == "0.0.0.0" else config.get("api_ip")
                    await common.send_async_request(f'http://{main_api_ip}:{config.get("api_port")}/send', "POST", data)


                # Send ChatBox content to carry outRepeat
                async def talk_chat_box_reread(insert_index=-1, type="reread"):
                    global running_flag

                    if running_flag != 1:
                        ui.notify(position="top", type="warning", message="Please click “Run” first, then chat")
                        return
                    
                    # Get the Username and text content
                    username = input_talk_username.value
                    content = textarea_talk_chat_box.value

                    # Clear the Chat box
                    textarea_talk_chat_box.value = ""

                    if insert_index == -1:
                        data = {
                            "type": type,
                            "data": {
                                "type": type,
                                "username": username,
                                "content": content
                            }
                        }
                    else:

                        data = {
                            "type": type,
                            "data": {
                                "type": type,
                                "username": username,
                                "content": content,
                                "insert_index": insert_index
                            }
                        }

                    if switch_talk_show_chat_log.value:
                        show_chat_log_json = {
                            "type": "llm",
                            "data": {
                                "type": type,
                                "username": username,
                                "content_type": "question",
                                "content": content,
                                "timestamp": common.get_bj_time(0)
                            }
                        }
                        data_handle_show_chat_log(show_chat_log_json)

                    main_api_ip = "127.0.0.1" if config.get("api_ip") == "0.0.0.0" else config.get("api_ip")
                    await common.send_async_request(f'http://{main_api_ip}:{config.get("api_port")}/send', "POST", data)

                # Send ChatBox content to carry out LLM tuning
                async def talk_chat_box_tuning():
                    global running_flag

                    if running_flag != 1:
                        ui.notify(position="top", type="warning", message="Please click “Run” first, then chat")
                        return
                    
                    # Get the Username and text content
                    username = input_talk_username.value
                    content = textarea_talk_chat_box.value

                    # Clear the Chat box
                    textarea_talk_chat_box.value = ""

                    data = {
                        "type": "tuning",
                        "data": {
                            "type": "tuning",
                            "username": username,
                            "content": content
                        }
                    }

                    main_api_ip = "127.0.0.1" if config.get("api_ip") == "0.0.0.0" else config.get("api_ip")
                    await common.send_async_request(f'http://{main_api_ip}:{config.get("api_port")}/send', "POST", data)

                button_talk_chat_box_send = ui.button('Send', on_click=lambda: talk_chat_box_send(), color=button_internal_color).style(button_internal_css).tooltip("SendText to the LLM, simulating a Danmaku-triggered operation")
                button_talk_chat_box_reread = ui.button('DirectRepeat', on_click=lambda: talk_chat_box_reread(), color=button_internal_color).style(button_internal_css).tooltip("SendText to the internal mechanism, triggers a TTS Repeat Type message")
                button_talk_chat_box_tuning = ui.button('Tuning', on_click=lambda: talk_chat_box_tuning(), color=button_internal_color).style(button_internal_css).tooltip("SendText to the LLM, but no TTS or other operations are performed")
                button_talk_chat_box_reread_first = ui.button('Direct Repeat - jump the queue', on_click=lambda: talk_chat_box_reread(0, "reread_top_priority"), color=button_internal_color).style(button_internal_css).tooltip("Highest priority, Send text to the internal mechanism, triggers a TTS direct Repeat Type message")
        
            with ui.expansion('Conversation interruption', icon="settings", value=True).classes('w-2/3'):
                with ui.row():
                    switch_talk_interrupt_talk_enable = ui.switch('Enable', value=config.get("talk", "interrupt_talk", "enable")).style(switch_internal_css)
                    textarea_talk_interrupt_talk_keywords = ui.textarea(
                        label='InterruptKeywords', 
                        placeholder='E.g.: wait a moment, shut up. Separate multiple entries with line breaks', 
                        value=textarea_data_change(config.get("talk", "interrupt_talk", "keywords"))
                    ).style("width:200px;").tooltip("Interrupt Keywords; when a sentence contains these words, the conversation is interrupted; what exactly is cleared is customized according to the clear Type")
                    
                    with ui.card().style(card_css):
                        ui.label("ClearType")
                        with ui.row(): 
                            talk_interrupt_clean_type_list = [
                                "message_queue", 
                                "voice_tmp_path_queue",
                                "audio_play"
                            ]
                            talk_interrupt_clean_type_mapping = {
                                "message_queue": "Message queue awaiting synthesis",
                                "voice_tmp_path_queue": "Audio queue awaiting playback",
                                "audio_play": "Audio currently playing",
                            }
                            talk_interrupt_clean_type_var = {}
                            
                            for index, talk_interrupt_clean_type in enumerate(talk_interrupt_clean_type_list):
                                if talk_interrupt_clean_type in config.get("talk", "interrupt_talk", "clean_type"):
                                    talk_interrupt_clean_type_var[str(index)] = ui.checkbox(
                                        text=talk_interrupt_clean_type_mapping[talk_interrupt_clean_type], 
                                        value=True
                                    )
                                else:
                                    talk_interrupt_clean_type_var[str(index)] = ui.checkbox(
                                        text=talk_interrupt_clean_type_mapping[talk_interrupt_clean_type], 
                                        value=False
                                    ) 
            with ui.expansion('Voice wake-up and sleep', icon="settings", value=True).classes('w-2/3'):
                with ui.row():
                    switch_talk_wakeup_sleep_enable = ui.switch('Enable', value=config.get("talk", "wakeup_sleep", "enable")).style(switch_internal_css)
                    select_talk_wakeup_sleep_mode = ui.select(
                        label='Wake-up mode', 
                        options={"Persistent wake-up": "Persistent wake-up", "Single wake-up": "Single wake-up"}, 
                        value=config.get("talk", "wakeup_sleep", "mode")
                    ).style("width:100px").tooltip("Long-term wake-up: after saying the wake word, the prompt is triggered, and later conversation does not need the wake word; single wake-up: every conversation must include the wake word, otherwise it stays asleep by default and the prompt is not triggered")
                    textarea_talk_wakeup_sleep_wakeup_word = ui.textarea(label='Wake word', placeholder='E.g.: butler. Separate multiple entries with line breaks', value=textarea_data_change(config.get("talk", "wakeup_sleep", "wakeup_word"))).style("width:200px;")
                    textarea_talk_wakeup_sleep_sleep_word = ui.textarea(label='Sleep word', placeholder='E.g.: shutdown. Separate multiple entries with line breaks', value=textarea_data_change(config.get("talk", "wakeup_sleep", "sleep_word"))).style("width:200px;")
                    textarea_talk_wakeup_sleep_wakeup_copywriting = ui.textarea(label='Wake-up prompt', placeholder='E.g.: are you there. Separate multiple entries with line breaks', value=textarea_data_change(config.get("talk", "wakeup_sleep", "wakeup_copywriting"))).style("width:300px;")
                    textarea_talk_wakeup_sleep_sleep_copywriting = ui.textarea(label='Sleep prompt', placeholder='E.g.: good night. Separate multiple entries with line breaks', value=textarea_data_change(config.get("talk", "wakeup_sleep", "sleep_copywriting"))).style("width:300px;")

            with ui.expansion('Google', icon="settings", value=False).classes('w-2/3'):
                with ui.grid(columns=1):
                    data_json = {}
                    for line in ["zh-CN", "en-US", "ja-JP"]:
                        data_json[line] = line
                    select_talk_google_tgt_lang = ui.select(
                        label='Target Translation language', 
                        options=data_json, 
                        value=config.get("talk", "google", "tgt_lang")
                    ).style("width:200px")
            with ui.expansion('Baidu', icon="settings", value=False).classes('w-2/3'):
                with ui.grid(columns=3):    
                    input_talk_baidu_app_id = ui.input(label='AppID', value=config.get("talk", "baidu", "app_id"), placeholder='Baidu Cloud speech recognition application AppID')
                    input_talk_baidu_api_key = ui.input(label='API Key', value=config.get("talk", "baidu", "api_key"), placeholder='Baidu Cloud speech recognition application API Key')
                    input_talk_baidu_secret_key = ui.input(label='Secret Key', value=config.get("talk", "baidu", "secret_key"), placeholder='Baidu Cloud speech recognition application Secret Key')
            with ui.expansion('faster_whisper', icon="settings", value=False).classes('w-2/3'):
                with ui.row():    
                    input_faster_whisper_model_size = ui.input(label='model_size', value=config.get("talk", "faster_whisper", "model_size"), placeholder='Size of the model to use')
                    data_json = {}
                    for line in ["Auto detect", 'af', 'am', 'ar', 'as', 'az', 'ba', 'be', 'bg', 'bn', 'bo', 'br', 'bs', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'en', 'es', 'et', 'eu', 'fa', 'fi', 'fo', 'fr', 'gl', 'gu', 'ha', 'haw', 'he', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jw', 'ka', 'kk', 'km', 'kn', 'ko', 'la', 'lb', 'ln', 'lo', 'lt', 'lv', 'mg', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl', 'nn', 'no', 'oc', 'pa', 'pl', 'ps', 'pt', 'ro', 'ru', 'sa', 'sd', 'si', 'sk', 'sl', 'sn', 'so', 'sq', 'sr', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'uk', 'ur', 'uz', 'vi', 'yi', 'yo', 'zh', 'yue']:
                        data_json[line] = line
                    select_faster_whisper_language = ui.select(
                        label='Recognition language', 
                        options=data_json, 
                        value=config.get("talk", "faster_whisper", "language")
                    ).style("width:200px")
                    data_json = {}
                    for line in ["cuda", "cpu", "auto"]:
                        data_json[line] = line
                    select_faster_whisper_device = ui.select(
                        label='device', 
                        options=data_json, 
                        value=config.get("talk", "faster_whisper", "device")
                    ).style("width:200px")
                    data_json = {}
                    for line in ["float16", "int8_float16", "int8"]:
                        data_json[line] = line
                    select_faster_whisper_compute_type = ui.select(
                        label='compute_type', 
                        options=data_json, 
                        value=config.get("talk", "faster_whisper", "compute_type")
                    ).style("width:200px")
                    input_faster_whisper_download_root = ui.input(label='download_root', value=config.get("talk", "faster_whisper", "download_root"), placeholder='Model download path')
                    input_faster_whisper_beam_size = ui.input(label='beam_size', value=config.get("talk", "faster_whisper", "beam_size"), placeholder='Number of most likely candidate sequences the system considers at each step. A larger beam_size makes the system produce more accurate results but may need more computing resources; a smaller beam_size reduces computing needs but may lower accuracy.')
            with ui.expansion('SenseVoice', icon="settings", value=False).classes('w-2/3'):
                with ui.row():    
                    input_sensevoice_asr_model_path = ui.input(label='ASR Model path', value=config.get("talk", "sensevoice", "asr_model_path"), placeholder='ASRModel path').tooltip("ASRModel path")
                    input_sensevoice_vad_model_path = ui.input(label='VAD Model path', value=config.get("talk", "sensevoice", "vad_model_path"), placeholder='VADModel path').tooltip("VADModel path")
                    input_sensevoice_vad_max_single_segment_time = ui.input(label='VAD Model path', value=config.get("talk", "sensevoice", "vad_max_single_segment_time"), placeholder='VADMaximum duration of a single speech segment').tooltip("VADMaximum duration of a single speech segment")
                    input_sensevoice_vad_device = ui.input(label='device', value=config.get("talk", "sensevoice", "device"), placeholder='Device to usedevice').tooltip("Device to usedevice")
                    
                    data_json = {}
                    for line in ['zh', 'en', 'jp']:
                        data_json[line] = line
                    select_sensevoice_language = ui.select(
                        label='Recognition language', 
                        options=data_json, 
                        value=config.get("talk", "sensevoice", "language")
                    ).style("width:100px")
                    input_sensevoice_text_norm = ui.input(label='text_norm', value=config.get("talk", "sensevoice", "text_norm"), placeholder='text_norm').style("width:100px").tooltip("text_norm")
                    input_sensevoice_batch_size_s = ui.input(label='batch_size_s', value=config.get("talk", "sensevoice", "batch_size_s"), placeholder='batch_size_s').style("width:100px").tooltip("batch_size_s")
                    input_sensevoice_batch_size = ui.input(label='batch_size', value=config.get("talk", "sensevoice", "batch_size"), placeholder='batch_size').style("width:100px").tooltip("batch_size")
            
        with ui.tab_panel(image_recognition_page).style(tab_panel_css):
            with ui.card().style(card_css): 
                async def get_llm_resp(screenshot_path: str, send_to_all: bool=True):
                    try:
                        # logger.warning(f"screenshot_path={screenshot_path}")

                        prompt = input_image_recognition_prompt.value

                        if select_image_recognition_model.value == "gemini":
                            from utils.gpt_model.gemini import Gemini

                            gemini = Gemini(config.get("image_recognition", "gemini"))

                            resp_content = gemini.get_resp_with_img(prompt, screenshot_path)

                            data = {
                                "type": "reread",
                                "username": config.get("talk", "username"),
                                "content": resp_content,
                                "insert_index": -1
                            }
                        elif select_image_recognition_model.value == "zhipu":
                            from utils.gpt_model.zhipu import Zhipu

                            zhipu = Zhipu(config.get("image_recognition", "zhipu"))

                            resp_content = zhipu.get_resp_with_img(prompt, screenshot_path)

                            data = {
                                "type": "reread",
                                "data": {
                                    "username": config.get("talk", "username"),
                                    "content": resp_content,
                                    "insert_index": -1
                                }
                            }
                        

                        if send_to_all:
                            if data is not None:
                                main_api_ip = "127.0.0.1" if config.get("api_ip") == "0.0.0.0" else config.get("api_ip")
                                await common.send_async_request(f'http://{main_api_ip}:{config.get("api_port")}/send', "POST", data)

                        return data
                    except Exception as e:
                        logger.error(traceback.format_exc())
                        return None
                        
                async def loop_screenshot_toggle_timer(interval_time: float):
                    global loop_screenshot_timer_running, loop_screenshot_timer


                    async def image_recognition_screenshot_and_send():
                        global running_flag

                        if running_flag != 1:
                            ui.notify(position="top", type="warning", message="Please click “Run” first, then do screenshot recognition")
                            return
                        
                        logger.info(f"Trigger screenshot recognition")

                        # Take a screenshot by window name
                        screenshot_path = common.capture_window_by_title(input_image_recognition_img_save_path.value, select_image_recognition_screenshot_window_title.value)

                        data = await get_llm_resp(screenshot_path)

                        
                    if loop_screenshot_timer_running:
                        # If the timer is already Running, Stop it
                        loop_screenshot_timer.cancel()
                    else:
                        # If the timer is not Running, start it
                        loop_screenshot_timer = ui.timer(interval=interval_time, callback=lambda: image_recognition_screenshot_and_send())  # Set a timer that executes the perform_task function once per second
                        loop_screenshot_timer.activate()
                    loop_screenshot_timer_running = not loop_screenshot_timer_running  # Update the timer Run status

                # Take a screenshot andSendLLM
                async def image_recognition_screenshot_and_send(sleep_time: float):
                    global running_flag

                    if running_flag != 1:
                        ui.notify(position="top", type="warning", message="Please click “Run” first, then do screenshot recognition")
                        return
                    
                    logger.info(f"{input_image_recognition_screenshot_delay.value}Trigger screenshot recognition after")
                    ui.notify(position="top", type="positive", message=f"{input_image_recognition_screenshot_delay.value}Trigger screenshot recognition after")
                    
                    await asyncio.sleep(sleep_time)

                    # Take a screenshot by window name
                    screenshot_path = common.capture_window_by_title(input_image_recognition_img_save_path.value, select_image_recognition_screenshot_window_title.value)
                    data = await get_llm_resp(screenshot_path)

                # Camera screenshot andSendLLM
                async def image_recognition_cam_screenshot_and_send(sleep_time: float):
                    global running_flag

                    if running_flag != 1:
                        ui.notify(position="top", type="warning", message="Please click “Run” first, then do screenshot recognition")
                        return
                    
                    logger.info(f"{input_image_recognition_cam_screenshot_delay.value}Trigger camera screenshot recognition after")
                    ui.notify(position="top", type="positive", message=f"{input_image_recognition_screenshot_delay.value}Trigger camera screenshot recognition after")
                    
                    await asyncio.sleep(sleep_time)

                    # Take a screenshot by camera index
                    screenshot_path = common.capture_image(input_image_recognition_img_save_path.value, int(select_image_recognition_cam_index.value))
                    data = await get_llm_resp(screenshot_path)


                ui.label("General")
                with ui.row():
                    button_image_recognition_enable = ui.switch('Enable', value=config.get("image_recognition", "enable")).style(switch_internal_css)
                    select_image_recognition_model = ui.select(
                        label='Model', 
                        options={'gemini': 'gemini', 'zhipu': 'Zhipu AI'}, 
                        value=config.get("image_recognition", "model")
                    ).style("width:150px")
                    
                    input_image_recognition_img_save_path = ui.input(label='Screenshot save path', value=config.get("image_recognition", "img_save_path"), placeholder='Screenshot save path, supports absolute or relative paths')
                    input_image_recognition_prompt = ui.input(label='Prompt carried along', value=config.get("image_recognition", "prompt"), placeholder='Prompt attached during image recognition, used together with image acquisitionAnswer')
                    
                    
                with ui.card().style(card_css):
                    ui.label("Computer screenshot")
                    with ui.row():
                        window_titles = common.list_visible_windows()
                        data_json = {}
                        for line in window_titles:
                            data_json[line] = line
                        select_image_recognition_screenshot_window_title = ui.select(
                            label='Screenshot window title', 
                            options=data_json, 
                            value=config.get("image_recognition", "screenshot_window_title")
                        ).style("width:300px")
                        input_image_recognition_screenshot_delay = ui.input(label='NTake a screenshot after seconds', value=config.get("image_recognition", "screenshot_delay"), placeholder='Screenshot delay, so the user can open the corresponding window').style("width:100px")
                        button_image_recognition_screenshot_and_send = ui.button('Take a screenshot andSend', on_click=lambda: image_recognition_screenshot_and_send(float(input_image_recognition_screenshot_delay.value)), color=button_internal_color).style(button_internal_css)
                    
                        switch_image_recognition_loop_screenshot_enable = ui.switch('Loop screenshots andSend', value=config.get("image_recognition", "loop_screenshot_enable")).style(switch_internal_css)
                        input_image_recognition_loop_screenshot_delay = ui.input(label='NAutomatically take a screenshot after seconds', value=config.get("image_recognition", "loop_screenshot_delay"), placeholder='Auto screenshot delay, can be triggered automatically when the user is playing a game or watching a videoImage Recognition').style("width:100px")
                        # button_image_recognition_loop_screenshot_and_send = ui.button('Loop screenshots andSend', on_click=lambda: loop_screenshot_toggle_timer(float(input_image_recognition_screenshot_delay.value)), color=button_internal_color).style(button_internal_css)
                with ui.card().style(card_css):
                    ui.label("Camera screenshot")
                    with ui.row():
                        switch_image_recognition_cam_screenshot_enable = ui.switch('Enable', value=config.get("image_recognition", "cam_screenshot_enable")).style(switch_internal_css)
                        
                        if config.get("image_recognition", "cam_screenshot_enable"):
                            cam_indexs = common.list_cameras()
                        else:
                            cam_indexs = []
                        data_json = {}
                        for line in cam_indexs:
                            data_json[line] = line
                        select_image_recognition_cam_index = ui.select(
                            label='Camera index', 
                            options=data_json, 
                            value=config.get("image_recognition", "cam_index")
                        ).style("width:100px")
                        input_image_recognition_cam_screenshot_delay = ui.input(label='NTake a screenshot after seconds', value=config.get("image_recognition", "cam_screenshot_delay"), placeholder='Screenshot delay, so the user can adjust the camera').style("width:100px")
                        button_image_recognition_cam_screenshot_and_send = ui.button('Take a screenshot andSend', on_click=lambda: image_recognition_cam_screenshot_and_send(float(input_image_recognition_cam_screenshot_delay.value)), color=button_internal_color).style(button_internal_css)
                    
                        switch_image_recognition_loop_cam_screenshot_enable = ui.switch('Loop screenshots andSend', value=config.get("image_recognition", "loop_cam_screenshot_enable")).style(switch_internal_css)
                        input_image_recognition_loop_cam_screenshot_delay = ui.input(label='NAutomatically take a screenshot after seconds', value=config.get("image_recognition", "loop_cam_screenshot_delay"), placeholder='Auto screenshot delay, can be triggered automaticallyImage Recognition').style("width:100px")
                        
            with ui.card().style(card_css):
                ui.label("Gemini")
                with ui.row():
                    select_image_recognition_gemini_model = ui.select(
                        label='Model', 
                        options={'gemini-pro-vision': 'gemini-pro-vision'}, 
                        value=config.get("image_recognition", "gemini", "model")
                    ).style("width:150px")
                    input_image_recognition_gemini_api_key = ui.input(label='API Key', value=config.get("image_recognition", "gemini", "api_key"), placeholder='Gemini API KEY')
                    input_image_recognition_gemini_http_proxy = ui.input(label='HTTP proxy address', value=config.get("image_recognition", "gemini", "http_proxy"), placeholder='httpProxy address; a VPN is required to use it, so this must be configured.').style("width:200px;")
                    input_image_recognition_gemini_https_proxy = ui.input(label='HTTPS proxy address', value=config.get("image_recognition", "gemini", "https_proxy"), placeholder='httpsProxy address; a VPN is required to use it, so this must be configured.').style("width:200px;")

            with ui.card().style(card_css):
                ui.label("Zhipu AI")
                with ui.row():
                    select_image_recognition_zhipu_model = ui.select(
                        label='Model', 
                        options={'glm-4v': 'glm-4v'}, 
                        value=config.get("image_recognition", "zhipu", "model")
                    ).style("width:150px")
                    input_image_recognition_zhipu_api_key = ui.input(label='API Key', value=config.get("image_recognition", "zhipu", "api_key"), placeholder='Zhipu API KEY')

        with ui.tab_panel(assistant_anchor_page).style(tab_panel_css):
            with ui.row():
                switch_assistant_anchor_enable = ui.switch('Enable', value=config.get("assistant_anchor", "enable")).style(switch_internal_css)
                input_assistant_anchor_username = ui.input(label='Assistant StreamerName', value=config.get("assistant_anchor", "username"), placeholder='Assistant StreamerUsername of it, not very useful for now')
                select_assistant_anchor_audio_synthesis_type = ui.select(
                    label='Speech synthesis', 
                    options=audio_synthesis_type_options, 
                    value=config.get("assistant_anchor", "audio_synthesis_type")
                ).style("width:200px;")
            with ui.card().style(card_css):
                ui.label("Trigger type")
                with ui.row():
                    # The type list comes from the type values supported by audio_synthesis_handle audio synthesis
                    assistant_anchor_type_list = ["comment", "local_qa_audio", "song", "reread", "read_comment", "gift", 
                                                  "entrance", "follow", "idle_time_task", "reread_top_priority", "schedule", 
                                                  "image_recognition_schedule", "key_mapping", "integral"]
                    assistant_anchor_type_mapping = {
                        "comment": "Comment",
                        "local_qa_audio": "Local Q&A - Audio",
                        "song": "Song request",
                        "reread": "Repeat",
                        "read_comment": "Read danmaku",
                        "gift": "Gift",
                        "entrance": "Entrance",
                        "follow": "Follow",
                        "idle_time_task": "Idle-time task",
                        "reread_top_priority": "Highest priority-Repeat",
                        "schedule": "Scheduled tasks",
                        "image_recognition_schedule": "Image RecognitionScheduled tasks",
                        "key_mapping": "Key mapping",
                        "integral": "Points",
                    }
                    assistant_anchor_type_var = {}
                    
                    for index, assistant_anchor_type in enumerate(assistant_anchor_type_list):
                        if assistant_anchor_type in config.get("assistant_anchor", "type"):
                            assistant_anchor_type_var[str(index)] = ui.checkbox(text=assistant_anchor_type_mapping[assistant_anchor_type], value=True)
                        else:
                            assistant_anchor_type_var[str(index)] = ui.checkbox(text=assistant_anchor_type_mapping[assistant_anchor_type], value=False)
            with ui.grid(columns=4):
                switch_assistant_anchor_local_qa_text_enable = ui.switch('Enable text matching', value=config.get("assistant_anchor", "local_qa", "text", "enable")).style(switch_internal_css)
                select_assistant_anchor_local_qa_text_format = ui.select(
                    label='Storage format',
                    options={'json': 'Custom json', 'text': 'One question, one answer'},
                    value=config.get("assistant_anchor", "local_qa", "text", "format")
                )
                input_assistant_anchor_local_qa_text_file_path = ui.input(label='Text Q&A data path', value=config.get("assistant_anchor", "local_qa", "text", "file_path"), placeholder='Local Q&A text data storage path').style("width:200px;")
                input_assistant_anchor_local_qa_text_similarity = ui.input(label='Text min similarity', value=config.get("assistant_anchor", "local_qa", "text", "similarity"), placeholder='Minimum text matching similarity, i.e. the minimum similarity between the content sent by the user and the content set in the local Q&A library.\nBelow it, the message is treated as a regular danmaku').style("width:200px;")
            with ui.grid(columns=4):
                switch_assistant_anchor_local_qa_audio_enable = ui.switch('Enable audio matching', value=config.get("assistant_anchor", "local_qa", "audio", "enable")).style(switch_internal_css)
                select_assistant_anchor_local_qa_audio_type = ui.select(
                    label='Matching algorithm',
                    options={'Contains': 'Contains', 'Similarity match': 'Similarity match'},
                    value=config.get("assistant_anchor", "local_qa", "audio", "type")
                )
                input_assistant_anchor_local_qa_audio_file_path = ui.input(label='Audio storage path', value=config.get("assistant_anchor", "local_qa", "audio", "file_path"), placeholder='Local Q&A audio file storage path').style("width:200px;")
                input_assistant_anchor_local_qa_audio_similarity = ui.input(label='Audio min similarity', value=config.get("assistant_anchor", "local_qa", "audio", "similarity"), placeholder='Minimum audio matching similarity, i.e. the minimum similarity between the content sent by the user and the audio file names in the local audio library.\nBelow it, the message is treated as a regular danmaku').style("width:200px;")
        
        with ui.tab_panel(translate_page).style(tab_panel_css):
            with ui.row():
                switch_translate_enable = ui.switch('Enable', value=config.get("translate", "enable")).style(switch_internal_css)
                select_translate_type = ui.select(
                        label='Type', 
                        options={'baidu': 'Baidu Translate', 'google': 'Google Translate'}, 
                        value=config.get("translate", "type")
                    ).style("width:100px;")
                select_translate_trans_type = ui.select(
                        label='Translation type', 
                        options={'Comment': 'Comment', 'Reply': 'Reply', 'Comment + Reply': 'Comment + Reply'}, 
                        value=config.get("translate", "trans_type")
                    ).style("width:150px;")
            with ui.card().style(card_css):
                ui.label("Baidu Translate")
                with ui.row():
                    input_translate_baidu_appid = ui.input(label='APP ID', value=config.get("translate", "baidu", "appid"), placeholder='TranslationOpen platform Developer Center APP ID')
                    input_translate_baidu_appkey = ui.input(label='Key', value=config.get("translate", "baidu", "appkey"), placeholder='TranslationOpen platform Developer Center key')
                    select_translate_baidu_from_lang = ui.select(
                        label='Source language', 
                        options={'auto': 'Auto detect', 'zh': 'Chinese', 'cht': 'Traditional Chinese', 'en': 'English', 'jp': 'Japanese', 'kor': 'Korean', 'yue': 'Cantonese', 'wyw': 'Classical Chinese'}, 
                        value=config.get("translate", "baidu", "from_lang")
                    ).style("width:100px;")
                    select_translate_baidu_to_lang = ui.select(
                        label='Target language', 
                        options={'zh': 'Chinese', 'cht': 'Traditional Chinese', 'en': 'English', 'jp': 'Japanese', 'kor': 'Korean', 'yue': 'Cantonese', 'wyw': 'Classical Chinese'}, 
                        value=config.get("translate", "baidu", "to_lang")
                    ).style("width:100px;")
            with ui.card().style(card_css):
                ui.label("Google Translate")
                with ui.row():
                    input_translate_google_proxy = ui.input(label='Proxy address', value=config.get("translate", "google", "proxy"), placeholder='Full address of the proxy, please include the protocol')
                    select_translate_google_src_lang = ui.select(
                        label='Source language', 
                        options={'auto': 'Auto', 'zh-CN': 'Chinese', 'en': 'English', 'ja': 'Japanese'}, 
                        value=config.get("translate", "google", "src_lang")
                    ).style("width:100px;")
                    select_translate_google_tgt_lang = ui.select(
                        label='Target language', 
                        options={'zh-CN': 'Chinese', 'en': 'English', 'ja': 'Japanese'}, 
                        value=config.get("translate", "google", "tgt_lang")
                    ).style("width:100px;")

        with ui.tab_panel(serial_page).style(tab_panel_css):
            with ui.element('div').classes('p-2 bg-blue-100'):
                ui.label("After completing the Serial port configuration on this page, you can use the Serial port mapping configuration function in “Common Config”\n Note!!! After the connection test here is complete, please Close the serial port; because the program is used across processes, not closing it will occupy the Serial port and prevent normal use!")
                        
            with ui.row():
                input_serial_config_index = ui.input(label='Serial portConfig index', value="", placeholder='Serial portOrder number of the config group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                button_serial_config_add = ui.button('Add a Serial port configuration group', on_click=serial_config_add, color=button_internal_color).style(button_internal_css)
                button_serial_config_del = ui.button('Delete the Serial port configuration group', on_click=lambda: serial_config_del(input_serial_config_index.value), color=button_internal_color).style(button_internal_css)

            serial_config_var = {}
            serial_config_card = ui.card()

            # Refresh serial portsList
            async def refresh_serial(index: int):
                logger.warning(index)
                try:
                    from utils.serial_manager_instance import get_serial_manager

                    serial_manager = get_serial_manager()

                    list_ports = await serial_manager.list_ports()
                    logger.info(f"Serial ports found:{list_ports}")
                    ui.notify(position="top", type="positive", message=f"Serial ports found:{list_ports}")
                    serial_config_var[str(8 * index)].set_options(list_ports)
                except Exception as e:
                    logger.error(traceback.format_exc())
                    ui.notify(position="top", type="negative", message=f"{traceback.format_exc()}")
                
            async def connect_serial(index: int):
                logger.warning(index)
                try:
                    from utils.serial_manager_instance import get_serial_manager

                    serial_manager = get_serial_manager()

                    serial_name = serial_config_var[str(8 * index)].value
                    baudrate = serial_config_var[str(8 * index + 1)].value
                    resp_json = await serial_manager.connect(serial_name, baudrate)
                    if resp_json['ret']:
                        ui.notify(position="top", type="positive", message=f"{resp_json['msg']}")
                    else:
                        ui.notify(position="top", type="negative", message=f"{resp_json['msg']}")
                except Exception as e:
                    logger.error(traceback.format_exc())
                    ui.notify(position="top", type="negative", message=f"{traceback.format_exc()}")

            async def disconnect_serial(index: int):
                logger.warning(index)
                try:
                    from utils.serial_manager_instance import get_serial_manager

                    serial_manager = get_serial_manager()

                    serial_name = serial_config_var[str(8 * index)].value
                    resp_json = await serial_manager.disconnect(serial_name)
                    if resp_json['ret']:
                        ui.notify(position="top", type="positive", message=f"{resp_json['msg']}")
                    else:
                        ui.notify(position="top", type="negative", message=f"{resp_json['msg']}")
                except Exception as e:
                    logger.error(traceback.format_exc())
                    ui.notify(position="top", type="negative", message=f"{traceback.format_exc()}")


            async def send_data_to_serial(index: int):
                try:
                    from utils.serial_manager_instance import get_serial_manager

                    serial_manager = get_serial_manager()

                    serial_name = serial_config_var[str(8 * index)].value
                    serial_data_type = serial_config_var[str(8 * index + 5)].value
                    send_data = serial_config_var[str(8 * index + 6)].value
                    resp_json = await serial_manager.send_data(serial_name, send_data, serial_data_type)
                    if resp_json['ret']:
                        ui.notify(position="top", type="positive", message=f"{resp_json['msg']}")
                    else:
                        ui.notify(position="top", type="negative", message=f"{resp_json['msg']}")
                except Exception as e:
                    logger.error(traceback.format_exc())
                    ui.notify(position="top", type="negative", message=f"{traceback.format_exc()}")  

            
            for index, serial_config in enumerate(config.get("serial", "config")):
                with serial_config_card.style(card_css):
                    with ui.row():
                        serial_config_var[str(8 * index)] = ui.select(label=f"Serial port name#{index + 1}", value=serial_config["serial_name"], options={f'{serial_config["serial_name"]}': f'{serial_config["serial_name"]}'}).style("width:200px;").tooltip('Path where copywriting files are stored. Changing it is not recommended.')
                        serial_config_var[str(8 * index + 1)] = ui.select(
                            label=f"Baud rate#{index + 1}", 
                            value=serial_config["baudrate"], 
                            options={'9600': '9600', '19200': '19200', '38400': '38400', '115200': '115200'}
                        ).style("width:200px;").tooltip('Baud rate')

                        # TODO:The parameter passed here is always 0, the index value has a Question, bug yet to be located
                        serial_config_var[str(8 * index + 2)] = ui.button('Refresh serial ports', on_click=lambda idx=index: refresh_serial(idx))
                        serial_config_var[str(8 * index + 3)] = ui.button('Open serial port', on_click=lambda idx=index: connect_serial(idx))
                        serial_config_var[str(8 * index + 4)] = ui.button('Close serial port', on_click=lambda idx=index: disconnect_serial(idx))

                        serial_config_var[str(8 * index + 5)] = ui.select(label=f"Send data type#{index + 1}", value=serial_config["serial_data_type"], options={'ASCII': 'ASCII', 'HEX': 'HEX'},).style("width:100px;").tooltip('Data type to send')
                        serial_config_var[str(8 * index + 6)] = ui.input(label=f"Send data#{index + 1}", value="", placeholder='Enter the content to send; after connecting, click Send').style("width:200px;").tooltip('Enter the content to send; after connecting, click Send')
                        serial_config_var[str(8 * index + 7)] = ui.button('Send', on_click=lambda idx=index: send_data_to_serial(idx))

        with ui.tab_panel(data_analysis_page).style(tab_panel_css):
            from utils.data_analysis import Data_Analysis

            data_analysis = Data_Analysis(config_path)

            data_analysis_comment_word_cloud_card = ui.card()
            with data_analysis_comment_word_cloud_card.style("width:100%;"):
                echart_comment_word_cloud = ui.echart(data_analysis.get_comment_word_cloud_option(
                    int(config.get("data_analysis", "comment_word_cloud", "top_num")))
                ).style(echart_css)
        
                with ui.row():
                    input_data_analysis_comment_word_cloud_top_num = ui.input(label='Top NKeywords', value=config.get("data_analysis", "comment_word_cloud", "top_num"), placeholder='Select the top N DanmakuKeywords as word cloud data')
                    def update_echart_comment_word_cloud():
                        data_analysis_comment_word_cloud_card.remove(0)
                        echart_comment_word_cloud = ui.echart(data_analysis.get_comment_word_cloud_option(
                            int(input_data_analysis_comment_word_cloud_top_num.value))
                        ).style(echart_css)
                        echart_comment_word_cloud.move(data_analysis_comment_word_cloud_card, 0)
                    ui.button('Update data', on_click=lambda: update_echart_comment_word_cloud())
            
            data_analysis_integral_card = ui.card()
            with data_analysis_integral_card.style("width:100%;"):
                echart_integral = ui.echart(data_analysis.get_integral_option(
                    "integral", int(config.get("data_analysis", "integral", "top_num")))
                ).style(echart_css)
        
                with ui.row():
                    input_data_analysis_integral_top_num = ui.input(label='Top Nitems of data', value=config.get("data_analysis", "integral", "top_num"), placeholder='Filter the Top N data')
                    def update_echart_integral(type):
                        data_analysis_integral_card.remove(0)
                        echart_integral = ui.echart(data_analysis.get_integral_option(
                            type,
                            int(input_data_analysis_integral_top_num.value))
                        ).style(echart_css)
                        echart_integral.move(data_analysis_integral_card, 0)
                    ui.button('Get the Points leaderboard', on_click=lambda: update_echart_integral('integral'))
                    ui.button('Get the viewing leaderboard', on_click=lambda: update_echart_integral('view_num'))
                    ui.button('Get the check-in leaderboard', on_click=lambda: update_echart_integral('sign_num'))
                    ui.button('Get the amount leaderboard', on_click=lambda: update_echart_integral('total_price'))
            data_analysis_gift_card = ui.card()
            with data_analysis_gift_card.style("width:100%;"):
                echart_gift = ui.echart(data_analysis.get_gift_option(int(config.get("data_analysis", "gift", "top_num")))).style(echart_css)
        
                with ui.row():
                    input_data_analysis_gift_top_num = ui.input(label='Top Nitems of data', value=config.get("data_analysis", "gift", "top_num"), placeholder='Filter the Top N data')
                    def update_echart_gift():
                        data_analysis_gift_card.remove(0)
                        echart_gift = ui.echart(data_analysis.get_gift_option(
                            int(input_data_analysis_gift_top_num.value))
                        ).style(echart_css)
                        echart_gift.move(data_analysis_gift_card, 0)
                    ui.button('Update data', on_click=lambda: update_echart_gift())
        with ui.tab_panel(web_page).style(tab_panel_css):
            with ui.card().style(card_css):
                ui.label("webuiConfiguration")
                with ui.row():
                    input_webui_title = ui.input(label='Title', placeholder='webuiTitle of it', value=config.get("webui", "title")).style("width:250px;")
                    input_webui_ip = ui.input(label='IP address', placeholder='webuiListeningIP address', value=config.get("webui", "ip")).style("width:150px;")
                    input_webui_port = ui.input(label='Port', placeholder='webuiListeningPort', value=config.get("webui", "port")).style("width:100px;")
                    switch_webui_auto_run = ui.switch('Auto run', value=config.get("webui", "auto_run")).style(switch_internal_css)
            
            with ui.card().style(card_css):
                ui.label("Local path to be accessed via the specified URL path")
                with ui.row():
                    input_webui_local_dir_to_endpoint_index = ui.input(label='Config index', value="", placeholder='Order number of the config group, i.e. the first group is 1, the second is 2, and so on. Please enter a plain integer')
                    button_webui_local_dir_to_endpoint_add = ui.button('Add config group', on_click=webui_local_dir_to_endpoint_add, color=button_internal_color).style(button_internal_css)
                    button_webui_local_dir_to_endpoint_del = ui.button('Delete config group', on_click=lambda: webui_local_dir_to_endpoint_del(input_webui_local_dir_to_endpoint_index.value), color=button_internal_color).style(button_internal_css)
                
                with ui.row():
                    switch_webui_local_dir_to_endpoint_enable = ui.switch('Enable', value=config.get("webui", "local_dir_to_endpoint", "enable")).style(switch_internal_css)
                with ui.row():
                    webui_local_dir_to_endpoint_config_var = {}
                    webui_local_dir_to_endpoint_config_card = ui.card()
                    for index, webui_local_dir_to_endpoint_config in enumerate(config.get("webui", "local_dir_to_endpoint", "config")):
                        with webui_local_dir_to_endpoint_config_card.style(card_css):
                            with ui.row():
                                webui_local_dir_to_endpoint_config_var[str(2 * index)] = ui.input(label=f"URL path#{index + 1}", value=webui_local_dir_to_endpoint_config["url_path"], placeholder='A string starting with a slash (“/”) that identifies the URL path under which files should be served to clients').style("width:200px;")
                                webui_local_dir_to_endpoint_config_var[str(2 * index + 1)] = ui.input(label=f"Local folder path#{index + 1}", value=webui_local_dir_to_endpoint_config["local_dir"], placeholder='Local folder path; a relative path is recommended, preferably one inside the project').style("width:300px;")
                               

            with ui.card().style(card_css):
                ui.label("CSS")
                with ui.row():
                    theme_list = config.get("webui", "theme", "list").keys()
                    data_json = {}
                    for line in theme_list:
                        data_json[line] = line
                    select_webui_theme_choose = ui.select(
                        label='Topic', 
                        options=data_json, 
                        value=config.get("webui", "theme", "choose")
                    )

            with ui.card().style(card_css):
                ui.label("Configuration template")
                with ui.row():
                    # Get the list of file names with the specified extension under the specified path
                    config_template_paths = common.get_specify_extension_names_in_folder("./", "*.json")
                    data_json = {}
                    for line in config_template_paths:
                        data_json[line] = line
                    select_config_template_path = ui.select(
                        label='Configuration template path', 
                        options=data_json, 
                        value="",
                        with_input=True,
                        new_value_mode='add-unique',
                        clearable=True
                    )

                    button_config_template_save = ui.button('Save the webui configuration to a file', on_click=lambda: config_template_save(select_config_template_path.value), color=button_internal_color).style(button_internal_css)
                    button_config_template_load = ui.button('Read the template to local (click with caution)', on_click=lambda: config_template_load(select_config_template_path.value), color=button_internal_color).style(button_internal_css)
                    


            with ui.card().style(card_css):
                ui.label("Show/hide panel")
                
                with ui.card().style(card_css):
                    ui.label("Common Config")
                    with ui.row():
                        switch_webui_show_card_common_config_read_comment = ui.switch('Read danmaku', value=config.get("webui", "show_card", "common_config", "read_comment")).style(switch_internal_css)
                        switch_webui_show_card_common_config_filter = ui.switch('Filter', value=config.get("webui", "show_card", "common_config", "filter")).style(switch_internal_css)
                        switch_webui_show_card_common_config_thanks = ui.switch('Thanks', value=config.get("webui", "show_card", "common_config", "thanks")).style(switch_internal_css)
                        switch_webui_show_card_common_config_local_qa = ui.switch('Local Q&A', value=config.get("webui", "show_card", "common_config", "local_qa")).style(switch_internal_css)
                        switch_webui_show_card_common_config_choose_song = ui.switch('Song request', value=config.get("webui", "show_card", "common_config", "choose_song")).style(switch_internal_css)
                        switch_webui_show_card_common_config_sd = ui.switch('Stable Diffusion', value=config.get("webui", "show_card", "common_config", "sd")).style(switch_internal_css)
                        switch_webui_show_card_common_config_log = ui.switch('Log', value=config.get("webui", "show_card", "common_config", "log")).style(switch_internal_css)
                        switch_webui_show_card_common_config_schedule = ui.switch('Scheduled tasks', value=config.get("webui", "show_card", "common_config", "schedule")).style(switch_internal_css)
                        switch_webui_show_card_common_config_idle_time_task = ui.switch('Idle-time task', value=config.get("webui", "show_card", "common_config", "idle_time_task")).style(switch_internal_css)
                        switch_webui_show_card_common_config_trends_copywriting = ui.switch('Dynamic copywriting', value=config.get("webui", "show_card", "common_config", "trends_copywriting")).style(switch_internal_css)
                        switch_webui_show_card_common_config_database = ui.switch('Database', value=config.get("webui", "show_card", "common_config", "database")).style(switch_internal_css)
                        switch_webui_show_card_common_config_play_audio = ui.switch('Audio playback', value=config.get("webui", "show_card", "common_config", "play_audio")).style(switch_internal_css)
                        switch_webui_show_card_common_config_web_captions_printer = ui.switch('Web captions printer', value=config.get("webui", "show_card", "common_config", "web_captions_printer")).style(switch_internal_css)
                        switch_webui_show_card_common_config_key_mapping = ui.switch('Key/copywriting mapping', value=config.get("webui", "show_card", "common_config", "key_mapping")).style(switch_internal_css)
                        switch_webui_show_card_common_config_custom_cmd = ui.switch('Custom commands', value=config.get("webui", "show_card", "common_config", "custom_cmd")).style(switch_internal_css)
                        
                        switch_webui_show_card_common_config_trends_config = ui.switch('Dynamic config', value=config.get("webui", "show_card", "common_config", "trends_config")).style(switch_internal_css)
                        switch_webui_show_card_common_config_abnormal_alarm = ui.switch('Abnormal alarm', value=config.get("webui", "show_card", "common_config", "abnormal_alarm")).style(switch_internal_css)
                        switch_webui_show_card_common_config_coordination_program = ui.switch('Linked programs', value=config.get("webui", "show_card", "common_config", "coordination_program")).style(switch_internal_css)
                        
                
                with ui.card().style(card_css):
                    ui.label("Large Language Model")
                    with ui.row():
                        switch_webui_show_card_llm_chatgpt = ui.switch('ChatGPT/Wenda', value=config.get("webui", "show_card", "llm", "chatgpt")).style(switch_internal_css)
                        switch_webui_show_card_llm_zhipu = ui.switch('Zhipu AI', value=config.get("webui", "show_card", "llm", "zhipu")).style(switch_internal_css)
                        switch_webui_show_card_llm_chat_with_file = ui.switch('chat_with_file', value=config.get("webui", "show_card", "llm", "chat_with_file")).style(switch_internal_css)
                        switch_webui_show_card_llm_langchain_chatchat = ui.switch('langchain_chatchat', value=config.get("webui", "show_card", "llm", "langchain_chatchat")).style(switch_internal_css)
                        switch_webui_show_card_llm_chatterbot = ui.switch('chatterbot', value=config.get("webui", "show_card", "llm", "chatterbot")).style(switch_internal_css)
                        switch_webui_show_card_llm_text_generation_webui = ui.switch('text_generation_webui', value=config.get("webui", "show_card", "llm", "text_generation_webui")).style(switch_internal_css)
                        switch_webui_show_card_llm_sparkdesk = ui.switch('iFlytek Spark', value=config.get("webui", "show_card", "llm", "sparkdesk")).style(switch_internal_css)
                        switch_webui_show_card_llm_bard = ui.switch('bard', value=config.get("webui", "show_card", "llm", "bard")).style(switch_internal_css)
                        switch_webui_show_card_llm_tongyi = ui.switch('Tongyi Qianwen', value=config.get("webui", "show_card", "llm", "tongyi")).style(switch_internal_css)
                        switch_webui_show_card_llm_tongyixingchen = ui.switch('Tongyi Xingchen', value=config.get("webui", "show_card", "llm", "tongyixingchen")).style(switch_internal_css)
                        switch_webui_show_card_llm_my_wenxinworkshop = ui.switch('Qianfan', value=config.get("webui", "show_card", "llm", "my_wenxinworkshop")).style(switch_internal_css)
                        switch_webui_show_card_llm_gemini = ui.switch('gemini', value=config.get("webui", "show_card", "llm", "gemini")).style(switch_internal_css)
                        switch_webui_show_card_llm_koboldcpp = ui.switch('koboldcpp', value=config.get("webui", "show_card", "llm", "koboldcpp")).style(switch_internal_css)
                        switch_webui_show_card_llm_anythingllm = ui.switch('AnythingLLM', value=config.get("webui", "show_card", "llm", "anythingllm")).style(switch_internal_css)
                        switch_webui_show_card_llm_gpt4free = ui.switch('GPT4Free', value=config.get("webui", "show_card", "llm", "gpt4free")).style(switch_internal_css)
                        switch_webui_show_card_llm_dify = ui.switch('Dify', value=config.get("webui", "show_card", "llm", "dify")).style(switch_internal_css)
                        switch_webui_show_card_llm_volcengine = ui.switch('Volcengine', value=config.get("webui", "show_card", "llm", "volcengine")).style(switch_internal_css)
                        
                        switch_webui_show_card_llm_custom_llm = ui.switch('Custom LLM', value=config.get("webui", "show_card", "llm", "custom_llm")).style(switch_internal_css)
                        switch_webui_show_card_llm_llm_tpu = ui.switch('LLM_TPU', value=config.get("webui", "show_card", "llm", "llm_tpu")).style(switch_internal_css)
                        
                with ui.card().style(card_css):
                    ui.label("Text-to-Speech")
                    with ui.row():
                        switch_webui_show_card_tts_edge_tts = ui.switch('Edge TTS', value=config.get("webui", "show_card", "tts", "edge-tts")).style(switch_internal_css)
                        switch_webui_show_card_tts_vits = ui.switch('VITS', value=config.get("webui", "show_card", "tts", "vits")).style(switch_internal_css)
                        switch_webui_show_card_tts_bert_vits2 = ui.switch('Bert VITS2', value=config.get("webui", "show_card", "tts", "bert_vits2")).style(switch_internal_css)
                        switch_webui_show_card_tts_vits_fast = ui.switch('VITS Fast', value=config.get("webui", "show_card", "tts", "vits_fast")).style(switch_internal_css)
                        switch_webui_show_card_tts_elevenlabs = ui.switch('elevenlabs', value=config.get("webui", "show_card", "tts", "elevenlabs")).style(switch_internal_css)
                        switch_webui_show_card_tts_openai_tts = ui.switch('openai_tts', value=config.get("webui", "show_card", "tts", "openai_tts")).style(switch_internal_css)
                        switch_webui_show_card_tts_gradio_tts = ui.switch('gradio', value=config.get("webui", "show_card", "tts", "gradio_tts")).style(switch_internal_css)
                        switch_webui_show_card_tts_gpt_sovits = ui.switch('gpt_sovits', value=config.get("webui", "show_card", "tts", "gpt_sovits")).style(switch_internal_css)
                        switch_webui_show_card_tts_azure_tts = ui.switch('azure_tts', value=config.get("webui", "show_card", "tts", "azure_tts")).style(switch_internal_css)
                        switch_webui_show_card_tts_cosyvoice = ui.switch('CosyVoice', value=config.get("webui", "show_card", "tts", "cosyvoice")).style(switch_internal_css)
                        switch_webui_show_card_tts_f5_tts = ui.switch('F5-TTS', value=config.get("webui", "show_card", "tts", "f5_tts")).style(switch_internal_css)
                        switch_webui_show_card_tts_multitts = ui.switch('F5-TTS', value=config.get("webui", "show_card", "tts", "multitts")).style(switch_internal_css)
                        switch_webui_show_card_tts_melotts = ui.switch('F5-TTS', value=config.get("webui", "show_card", "tts", "melotts")).style(switch_internal_css)
                        switch_webui_show_card_tts_index_tts = ui.switch('Index-TTS', value=config.get("webui", "show_card", "tts", "index_tts")).style(switch_internal_css)
                        
                with ui.card().style(card_css):
                    ui.label("Voice Changer")
                    with ui.row():
                        switch_webui_show_card_svc_ddsp_svc = ui.switch('DDSP SVC', value=config.get("webui", "show_card", "svc", "ddsp_svc")).style(switch_internal_css)
                        switch_webui_show_card_svc_so_vits_svc = ui.switch('SO-VITS-SVC', value=config.get("webui", "show_card", "svc", "so_vits_svc")).style(switch_internal_css)
                with ui.card().style(card_css):
                    ui.label("Virtual Body")
                    with ui.row():
                        switch_webui_show_card_visual_body_live2d = ui.switch('Live2D', value=config.get("webui", "show_card", "visual_body", "live2d")).style(switch_internal_css)
                        switch_webui_show_card_visual_body_xuniren = ui.switch('xuniren', value=config.get("webui", "show_card", "visual_body", "xuniren")).style(switch_internal_css)
                        switch_webui_show_card_visual_body_metahuman_stream = ui.switch('metahuman_stream', value=config.get("webui", "show_card", "visual_body", "metahuman_stream")).style(switch_internal_css)
                        switch_webui_show_card_visual_body_unity = ui.switch('unity', value=config.get("webui", "show_card", "visual_body", "unity")).style(switch_internal_css)
                        switch_webui_show_card_visual_body_EasyAIVtuber = ui.switch('EasyAIVtuber', value=config.get("webui", "show_card", "visual_body", "EasyAIVtuber")).style(switch_internal_css)
                        switch_webui_show_card_visual_body_digital_human_video_player = ui.switch('digital_human_video_player', value=config.get("webui", "show_card", "visual_body", "digital_human_video_player")).style(switch_internal_css)
                        switch_webui_show_card_visual_body_live2d_TTS_LLM_GPT_SoVITS_Vtuber = ui.switch('live2d_TTS_LLM_GPT_SoVITS_Vtuber', value=config.get("webui", "show_card", "visual_body", "live2d_TTS_LLM_GPT_SoVITS_Vtuber")).style(switch_internal_css)
                                
                    
            
            with ui.card().style(card_css):
                ui.label("AccountManage")
                with ui.row():
                    switch_login_enable = ui.switch('Login function', value=config.get("login", "enable")).style(switch_internal_css)
                    input_login_username = ui.input(label='Username', placeholder='Your Account, nya, configured in config.json', value=config.get("login", "username")).style("width:250px;")
                    input_login_password = ui.input(label='Password', password=True, placeholder='Your Password, nya, configured in config.json', value=config.get("login", "password")).style("width:250px;")
        with ui.tab_panel(docs_page).style(tab_panel_css):
            with ui.row():
                ui.label('Online documentation:')
                ui.link('https://ikaros521.eu.org/site/', 'https://ikaros521.eu.org/site/', new_tab=True)
                ui.link('giteeBackup document', 'https://ikaros-521.gitee.io/luna-docs/site/index.html', new_tab=True)

                ui.label('NiceGUIOfficial documentation:')
                ui.link('nicegui.io/documentation', 'https://nicegui.io/documentation', new_tab=True)

                ui.label('Video tutorial collection:')
                ui.link('Click me to jump', 'https://space.bilibili.com/3709626/channel/collectiondetail?sid=1422512', new_tab=True)

                ui.label('GitHubRepository:')
                ui.link('Ikaros-521/AI-Vtuber', 'https://github.com/Ikaros-521/AI-Vtuber', new_tab=True)
            
            with ui.expansion('Video tutorial', icon='movie_filter', value=True).classes('w-full'):
                ui.html('<iframe src="https://space.bilibili.com/3709626/channel/collectiondetail?sid=1422512" allowfullscreen="true" width="1800" height="800"> </iframe>').style("width:100%")

            with ui.expansion('Document', icon='article', value=True).classes('w-full'):
                ui.html('<iframe src="https://ikaros521.eu.org/site/" width="1800" height="800"></iframe>').style("width:100%")
        with ui.tab_panel(about_page).style(tab_panel_css):
            with ui.card().style(card_css):
                ui.label('Introduction').style("font-size:24px;")
                ui.label('AI Vtuber is a virtual AI streamer that combines state-of-the-art technologies. At its core is a series of efficient AI models, including ChatterBot, GPT, Claude, langchain, chatglm, text-generation-webui, iFlytek Spark, Zhipu AI, Google Bard, ERNIE Bot and Tongyi Xingchen. These models can either Run locally or be supported through cloud services.')
                ui.label('AI Vtuber Its appearance is built with Live2D, Vtube Studio, xuniren and UE5 combined with Audio2Face technology, giving users a lively, interactive virtual avatar. This lets AI Vtuber do real-time interactive livestreams on major streaming Platforms such as Bilibili, Douyin, Kuaishou, Douyu, YouTube and Twitch. Of course, it can also hold personalized conversations with you in a local environment.')
                ui.label('To make communication more natural, AI Vtuber uses advanced natural language processing technology combined with Text-to-Speech systems such as Edge-TTS, VITS-Fast, elevenlabs, VALL-E-X, Ruisheng AI, tts.ai-lab.top and GPT-SoVITS. This not only lets it generate fluent Answers, but also vary the voice through so-vits-svc and DDSP-SVC to suit different scenes and characters.')
                ui.label('In addition, AI Vtuber can also collaborate with Stable Diffusion through specific commands to show artwork. Users can also customize Copywriting for the AI Vtuber to play in a loop, to meet the needs of different occasions.')
            with ui.card().style(card_css):
                ui.label('License').style("font-size:24px;")
                ui.label('This project is licensed under the GNU General Public License (GPL). See the LICENSE file for details.')
            with ui.card().style(card_css):
                ui.label('Note').style("font-size:24px;")
                ui.label('It is strictly forbidden to use this project for any purpose that violates the Constitution of the People Republic of China, the Criminal Law, the Public Security Administration Punishments Law, or the Civil Code.')
                ui.label('Any political use is strictly forbidden.')
            ui.image('./docs/xmind.png').style("width:1000px;")
    with ui.row().classes('bottom-bar items-center no-wrap'):
        button_save = ui.button('Save Config', icon='save', on_click=lambda: save_config(), color=button_bottom_color).style(button_bottom_css).tooltip("Save the webui configuration to a local file; some configurations need a Restart to take effect after saving")
        button_run = ui.button('Start Run', icon='play_arrow', on_click=lambda: run_external_program(), color=button_bottom_color).style(button_bottom_css).tooltip("Runmain.py")
        button_stop = ui.button('Stop Run', icon='stop', on_click=lambda: stop_external_program(), color='negative').style(button_bottom_css).tooltip("StopRunmain.py")
        button_light = ui.button('Lights Off', icon='dark_mode', on_click=lambda: change_light_status(), color=button_bottom_color).style(button_bottom_css)
        button_restart = ui.button('Restart', icon='restart_alt', on_click=lambda: restart_application(), color=button_bottom_color).style(button_bottom_css).tooltip("StopRunmain.pyandRestart webui")

    with ui.row().style("position:fixed; bottom: 20px; right: 20px;"):
        ui.button('⇧', on_click=lambda: scroll_to_top(), color=button_bottom_color).style(button_bottom_css)

    # Whether to Enable the auto-Run function
    if config.get("webui", "auto_run"):
        logger.info("Auto Run isEnable")
        run_external_program(type="api")

# SendHeartbeat packet
ui.timer(9 * 60, lambda: common.send_heartbeat())

# Whether to Enable the login function (not reasonable for now)
if config.get("login", "enable"):

    def my_login():
        try:
            global user_info

            username = input_login_username.value
            password = input_login_password.value

            if username == "" or password == "":
                ui.notify(position="top", type="info", message="UsernameOr the Password cannot be empty")
                return

            API_URL = urljoin(config.get("login", "ums_api"), '/auth/login')
                        
            resp_json = common.check_login(API_URL, username, password)

            if resp_json is None:
                ui.notify(position="top", type="negative", message="LoginFailure")
                return

            if "data" not in resp_json or "success" not in resp_json:
                ui.notify(position="top", type="negative", message="UsernameOr the Password is incorrect")
                return

            if not resp_json["success"]:
                remainder = common.time_difference_in_seconds(resp_json["data"]["expiration_ts"])
                ui.notify(position="top", type="warning", message=f'Account expiration time:{resp_json["data"]["expiration_ts"]}, expired, please contact the administrator to renew')
                return

            user_info = resp_json["data"]
            expiration_ts = resp_json["data"]["expiration_ts"]

            remainder = common.time_difference_in_seconds(expiration_ts)
            if remainder < 0:
                ui.notify(position="top", type="warning", message=f"AccountExpired:{remainder}seconds ago, please contact the administrator to renew")
                return

            ui.notify(position="top", type="info", message=f'Login Success, Account expiration time:{resp_json["data"]["expiration_ts"]}, remaining time: {remainder} seconds')

            label_login.delete()
            input_login_username.delete()
            input_login_password.delete()
            button_login.delete()
            button_login_forget_password.delete()

            login_column.style("")
            login_card.style("position: unset;")

            goto_func_page()

            return
        except Exception as e:
            logger.error(traceback.format_exc())
            return

    # @ui.page('/forget_password')
    def forget_password():
        ui.notify(position="top", type="info", message="Please contact the administrator to change the Password!")


    login_column = ui.column().style("width:100%;text-align: center;")
    with login_column:
        login_card = ui.card().style(config.get("webui", "theme", "list", theme_choose, "login_card"))
        with login_card:
            label_login = ui.label('AI    Vtuber').style("font-size: 30px;letter-spacing: 5px;color: #3b3838;")
            input_login_username = ui.input(label='Username', placeholder='Your Account, please ask the administrator to apply for one', value="").style("width:250px;")
            input_login_password = ui.input(label='Password', password=True, placeholder='Your Password, please ask the administrator to apply for one', value="").style("width:250px;")
            button_login = ui.button('Login', on_click=lambda: my_login()).style("width:250px;")
            button_login_forget_password = ui.button('What if you forget your Account/Password?', on_click=lambda: forget_password()).style("width:250px;")
            # link_login_forget_password = ui.link('What if you forget your Account Password?', forget_password)

else:
    login_column = ui.column().style("width:100%;text-align: center;")
    with login_column:
        login_card = ui.card().style(config.get("webui", "theme", "list", theme_choose, "login_card"))
        
        # Go to the function page
        goto_func_page()


ui.run(host=webui_ip, port=webui_port, title=webui_title, favicon="./ui/favicon-64.ico", language="zh-CN", dark=False, reload=False)
# ui.run(host=webui_ip, port=webui_port, title=webui_title, favicon="./ui/favicon-64.ico", language="zh-CN", dark=False, reload=False,
#        ssl_certfile="F:\\FunASR_WS\\cert.pem", ssl_keyfile="F:\\FunASR_WS\\key.pem")