from dataclasses import dataclass

@dataclass
class ToolResponse[T]:
    """Generyczna klasa odpowiedzi narzędzia MCP."""
    success: bool
    data: T | None
    description: str
    
    @staticmethod
    def ok(data: T, description: str = "") -> "ToolResponse[T]":
        """Zwraca pomyślną odpowiedź."""
        return ToolResponse(success=True, data=data, description=description)
    
    @staticmethod
    def fail(description: str) -> "ToolResponse[T]":
        """Zwraca odpowiedź błędu."""
        return ToolResponse(success=False, data=None, description=description)
    

    
    
    