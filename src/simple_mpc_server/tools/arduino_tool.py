from simple_mpc_server.core.Atool import ATool


class ArduinoTool(ATool):
    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate

    def connect(self):
        # Code to establish connection to the Arduino device
        pass

    def disconnect(self):
        # Code to disconnect from the Arduino device
        pass

    def send_data(self, data: str):
        # Code to send data to the Arduino device
        pass

    def receive_data(self) -> str:
        # Code to receive data from the Arduino device
        return ""