import asyncio
import serial
import serial.tools.list_ports
from typing import Dict, List, Tuple

from .my_log import logger


class SerialManager:
    def __init__(self):
        self.connections: Dict[str, Tuple[serial.Serial, asyncio.Task]] = {}
        self.buffers: Dict[str, bytearray] = {}

    async def list_ports(self) -> List[str]:
        # List all available serial ports
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    async def connect(self, port: str, baudrate: int = 115200, timeout: int = 1) -> dict:
        # Connect to the specified serial port
        if port in self.connections:
            logger.warning(f"{port} Already connected")
            return {'ret': False, 'msg': f'{port} is already connected'}

        try:
            # loop = asyncio.get_running_loop()
            serial_conn = serial.Serial(port, baudrate, timeout=timeout)
            task = None
            # task = loop.run_in_executor(None, self._read_serial, port, serial_conn)
            self.connections[port] = (serial_conn, task)
            self.buffers[port] = bytearray()
            logger.info(f"Connected to {port}")
            return {'ret': True, 'msg': f'Connected to {port}'}
        except Exception as e:
            logger.error(f"Error connecting to {port}: {e}")
            return {'ret': False, 'msg': f'Error connecting to {port}: {e}'}

    async def disconnect(self, port: str) -> dict:
        # Disconnect the specified serial port
        if port not in self.connections:
            logger.warning(f"{port} Not connected, no need to close")
            return {'ret': False, 'msg': f'{port} is not connected'}

        serial_conn, task = self.connections.pop(port)
        serial_conn.close()
        # task.cancel()
        del self.buffers[port]
        logger.info(f"Disconnected from {port}")
        return {'ret': True, 'msg': f'Disconnected from {port}'}

    async def send_data(self, port: str, data: str, data_type: str = 'ascii', timeout: float = 1.0) -> str:
        # Send data and wait for the response, with a timeout mechanism
        if port not in self.connections:
            logger.warning(f"{port} Not connected")
            return {'ret': False, 'msg': f"{port} is not connected"}

        serial_conn, _ = self.connections[port]
        try:
            self.buffers[port] = bytearray()  # Clear the buffer

            # Encode according to data_type
            if data_type in ['ascii', 'ASCII']:
                encoded_data = data.encode()
            elif data_type in ['hex', 'HEX']:
                encoded_data = bytes.fromhex(data)
            else:
                logger.error(f"Invalid data type: {data_type}")
                return {'ret': False, 'msg': f"Invalid data type: {data_type}"}

            serial_conn.write(encoded_data)
            logger.info(f"Sending {data_type} data:{data}")
            return {'ret': True, "msg": f"Sent {data_type} data: {data}"}
            # resp_json = await self._read_response(port, timeout)
            # return resp_json
        except Exception as e:
            logger.error(f"Error sending data to {port}: {e}")
            return {'ret': False, 'msg': f"Error sending data to {port}: {e}"}

    async def _read_response(self, port: str, timeout: float) -> str:
        # Read the data returned by the serial port, with a timeout mechanism
        try:
            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(None, self._wait_for_data, port)
            response = await asyncio.wait_for(future, timeout)
            return {'ret': True, "msg": f"Received HEX response: {response}"}
        except asyncio.TimeoutError:
            logger.error(f"Timed out reading data from {port}")
            return {'ret': True, "msg": f"Timed out reading from {port}"}
        except Exception as e:
            logger.error(f"Error reading data from {port}: {e}")
            return {'ret': False, "msg": f"Error reading data from {port}: {e}"}

    def _wait_for_data(self, port: str) -> str:
        # Wait for data to arrive, and read from the buffer
        while True:
            if port not in self.buffers:
                return ""
            buffer = self.buffers[port]
            if buffer:
                response = buffer[:]
                self.buffers[port] = bytearray()  # Clear the buffer
                return self._process_data("hex", response)

    def _read_serial(self, port: str, serial_conn: serial.Serial):
        try:
            # Background task: continuously read serial port data and process it
            while True:
                data = serial_conn.read(1024)  # Read a certain amount of data
                if data:
                    self.buffers[port].extend(data)
                    logger.info(f"Received data from {port}: {self._process_data('hex', data)}")
        except serial.SerialException as e:
            logger.error(f"{port} Serial port exception: {e}")
        except Exception as e:
            logger.error(f"Error reading {port}: {e}")
        finally:
            if port in self.connections:
                serial_conn.close()
                del self.connections[port]
                del self.buffers[port]
                logger.info(f"{port} Disconnected")


    def _process_data(self, type: str, data: bytes) -> str:
        try:
            if type == "hex":
                # Return the hex representation
                return data.hex()
            elif type == "str":
                # Try to decode as a string
                return data.decode('utf-8')
            else:
                # Unknown type, return the hex representation
                return data.hex()
        except UnicodeDecodeError:
            # If it cannot be decoded to a string, return the hex representation
            return data.hex()

async def main():
    serial_manager = SerialManager()

    # List all available serial ports
    ports = await serial_manager.list_ports()
    logger.info(f"Available serial ports: {ports}")

    # Connect to a serial port
    if ports:
        port = ports[0]
        connected = await serial_manager.connect(port)
        if connected['ret']:
            # Send data and wait for the response
            response = await serial_manager.send_data(port, "Hello", timeout=2)
            logger.info(f"Return: {response}")

            # Disconnect from the serial port
            await serial_manager.disconnect(port)

if __name__ == "__main__":
    logger.add("serial_manager.log", rotation="1 MB")
    asyncio.run(main())