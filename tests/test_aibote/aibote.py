# 1. Import the WinBotMain class
from PyAibote import WinBotMain
import time,os

# 2. Define a custom script class that inherits from WinBotMain
class CustomWinScript(WinBotMain):

    # 2.1. Set terminal output. DEBUG: print, INFO: do not print. Default is to print
    Log_Level = "DEBUG" 

    # 2.2. Whether to save terminal output to a LOG file. True: save, False: do not save
    Log_Storage = True  


    # 2.3. Note: script_main is the script entry point and must exist
    def script_main(self):
        # Query all window handles
        # result = self.find_windows()
        # print(result)
        print("Start running the custom script")
    
        # Usage example [Demo]
        result = self.init_speech_clone_service("178asdf325c95eafdaaasee3bbf64741", "tIdj8l8nPdqV86Ueasdf")
        print(result)

        # Usage example [Demo]
        result = self.init_metahuman("F:/AiboteHumanLive/DigitalHumanMain_V1.0.4_RC/Static/humanModelFemale", 0.5, 0.5, False)
        print(result)

        # result = self.train_human_model(
        #     "dfjklDJFLJlfjkdljf", 
        #     "E:\\GitHub_pro\\AI-Vtuber\\tests\\test_aibote\\1.png", 
        #     "E:\\GitHub_pro\\AI-Vtuber\\tests\\test_aibote\\humanModel", 
        #     "E:\\GitHub_pro\\AI-Vtuber\\tests\\test_aibote\\newHumanModel"
        # )
        # print(result)

        result = self.metahuman_speech("D:/AiboteMetahuman/voice/1.mp3", "PyAibote is an excellent automation framework", "zh-cn", "zh-cn-XiaochenNeural", 0, True, 0, "General")


if __name__ == '__main__':
    # 3. IPis: 0.0.0.0, listening on port 9999
    # 3.1. When deploying the script remotely, set Debug=False; when starting WindowsDriver.exe manually on the client, specify the remote IP or port
    # 3.2. Command-line startup example:"127.0.0.1" 9999 {'Name':'PyAibote'}
    CustomWinScript.execute("0.0.0.0", 9999, Debug=True)