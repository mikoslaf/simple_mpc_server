from pathlib import Path
from loguru import logger

from mcp.server.fastmcp import FastMCP
from simple_mpc_server.core.tool_response import ToolResponse
from simple_mpc_server.core.Atool import ATool
    
class FileSystemTool(ATool):
    """Narzędzie do operacji na systemie plików."""
    
    ROOT_PATH = Path("C:\\Users\\Lenovo\\Praca\\smienata\\simple_mpc_server")
    
    def __init__(self):
        """Inicjalizuje narzędzie i tworzy katalog główny, jeśli nie istnieje."""
        self.ROOT_PATH.mkdir(parents=True, exist_ok=True)
    
    def __create_file(self, file_name: str, file_content: str) -> tuple[bool, str]:
        """Tworzy nowy plik w systemie plików."""
        file_path = self.ROOT_PATH / file_name
        try:
            file_path.write_text(file_content, encoding='utf-8')
            logger.debug(f"Utworzono plik: {file_path}")
            return (True, f"Plik {file_name} został utworzony w {self.ROOT_PATH}")
        except Exception as e:
            logger.error(f"Błąd podczas tworzenia pliku {file_path}: {e}")
            return (False, str(e))
    
    def __read_file(self, file_name: str) -> tuple[bool, str]:
        """Odczytuje zawartość pliku z systemu plików."""
        file_path = self.ROOT_PATH / file_name
        if not file_path.exists():
            logger.error(f"Plik nie istnieje: {file_path}")
            return (False, f"Plik {file_name} nie istnieje.")
        content = file_path.read_text(encoding='utf-8')
        logger.debug(f"Odczytano plik: {file_path}")
        return (True, content)
    
    def register(self, mcp: FastMCP) -> None:
        """Rejestruje narzędzia związane z systemem plików w instancji MCP."""
        
        @mcp.tool(name="create_file")
        def create_file(file_name: str, file_content: str) -> str:
            """Tworzy nowy plik w systemie plików"""
            logger.debug(f"Tworzenie pliku: {file_name}")
            success, message = self.__create_file(file_name, file_content)
            if success:
                return ToolResponse.ok(message, f"Plik {file_name} utworzony pomyślnie.")
            else:
                return ToolResponse.fail(f"Błąd podczas tworzenia pliku {file_name}: {message}")

        @mcp.tool(name="read_file")
        def read_file(file_name: str) -> str:
            """Odczytuje zawartość pliku z systemu plików"""
            logger.debug(f"Odczytywanie pliku: {file_name}")
            success, content = self.__read_file(file_name)
            if success:
                return ToolResponse.ok(content, f"Pomyślnie odczytano plik {file_name}.")
            else:
                return ToolResponse.fail(f"Błąd podczas odczytu pliku {file_name}: {content}")