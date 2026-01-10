from abc import ABC, abstractmethod
from mcp.server.fastmcp import FastMCP

class ATool(ABC):
    """Abstrakcyjna klasa bazowa dla wszystkich narzędzi MCP."""
    
    @abstractmethod
    def register(mcp: FastMCP) -> None:
        """Rejestruje narzędzia w instancji MCP."""
        pass