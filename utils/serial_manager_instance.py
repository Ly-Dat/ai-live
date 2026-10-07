from utils.serial_manager import SerialManager

class SingletonSerialManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SerialManager()
        return cls._instance

# Use a function to return the singleton instance
def get_serial_manager():
    return SingletonSerialManager.get_instance()
