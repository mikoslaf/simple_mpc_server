from loguru import logger
import serial
import time


class ArduinoBoard:
    """Uniwersalna klasa do komunikacji z płytką Arduino przez UART."""
    
    def __init__(self, port: str, baudrate: int = 9600):
        """
        Inicjalizuje połączenie z płytką Arduino.
        
        Args:
            port: Port szeregowy (np. 'COM5' na Windows, '/dev/ttyACM0' na Linux)
            baudrate: Prędkość komunikacji (domyślnie 9600)
        """
        self.port = port
        self.baudrate = baudrate
        self._serial = None
        self._is_connected = False
    
    def connect(self):
        """Nawiązuje połączenie z płytką Arduino."""
        try:
            logger.info(f"Łączenie z Arduino na porcie {self.port}...")
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Czekaj na reset Arduino po otwarciu portu
            self._is_connected = True
            logger.info(f"Połączono z Arduino na {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Błąd podczas łączenia z Arduino: {e}")
            self._is_connected = False
            return False
    
    def disconnect(self):
        """Rozłącza połączenie z płytką Arduino."""
        if self._serial and self._is_connected:
            try:
                self._serial.close()
                self._is_connected = False
                logger.info("Rozłączono z Arduino")
            except Exception as e:
                logger.error(f"Błąd podczas rozłączania: {e}")
    
    def is_connected(self):
        """Sprawdza czy połączenie jest aktywne."""
        return self._is_connected
    
    def send_command(self, command: str):
        """
        Wysyła komendę do Arduino.
        
        Args:
            command: Komenda tekstowa (np. 'D13=1', 'AN0?')
        """
        if not self._is_connected or not self._serial:
            logger.error("Brak połączenia z Arduino")
            return None
        
        try:
            self._serial.write(f"{command}\n".encode())
            logger.debug(f"Wysłano komendę: {command}")
            return True
        except Exception as e:
            logger.error(f"Błąd wysyłania komendy: {e}")
            return False
    
    def read_response(self):
        """Odczytuje odpowiedź z Arduino."""
        if not self._is_connected or not self._serial:
            logger.error("Brak połączenia z Arduino")
            return None
        
        try:
            if self._serial.in_waiting > 0:
                response = self._serial.readline().decode().strip()
                logger.debug(f"Odebrano: {response}")
                return response
            return None
        except Exception as e:
            logger.error(f"Błąd odczytu odpowiedzi: {e}")
            return None
    
    def digital_write(self, pin: int, value: bool):
        """
        Ustawia stan cyfrowy pinu.
        
        Args:
            pin: Numer pinu cyfrowego (np. 13)
            value: True (HIGH) lub False (LOW)
        """
        command = f"D{pin}={1 if value else 0}"
        return self.send_command(command)
    
    def digital_read(self, pin: int):
        """
        Odczytuje stan cyfrowy pinu.
        
        Args:
            pin: Numer pinu cyfrowego
        """
        command = f"D{pin}?"
        self.send_command(command)
        time.sleep(0.1)
        response = self.read_response()
        if response:
            try:
                return int(response) == 1
            except ValueError:
                return None
        return None
    
    def analog_read(self, pin: int):
        """
        Odczytuje wartość analogową z pinu.
        
        Args:
            pin: Numer pinu analogowego (0-5 dla A0-A5)
        """
        command = f"A{pin}?"
        self.send_command(command)
        time.sleep(0.1)
        response = self.read_response()
        if response:
            try:
                return int(response)
            except ValueError:
                return None
        return None
    
    def pwm_write(self, pin: int, value: int):
        """
        Ustawia PWM na pinie.
        
        Args:
            pin: Numer pinu z PWM (np. 3, 5, 6, 9, 10, 11 na Uno)
            value: Wartość PWM 0-255
        """
        if not 0 <= value <= 255:
            logger.error(f"Wartość PWM musi być 0-255, otrzymano: {value}")
            return False
        
        command = f"P{pin}={value}"
        return self.send_command(command)
    
    def __enter__(self):
        """Context manager enter."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()