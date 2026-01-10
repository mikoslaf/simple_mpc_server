from loguru import logger

from simple_mpc_server.core.tool_response import ToolResponse
from ..core.Atool import ATool
from mcp.server.fastmcp import FastMCP

class MonsterTool(ATool):
    __monsters = {
    1: "Smok Żarłacz",
    2: "Bazyliszek Krzemowy",
    3: "Hydra Kwantowa",
    4: "Golem Widmowy",
    5: "Lewiatan Fraktalny",
    }
    
    def __get_monster_by_id(self, id: int) -> str:
        """Zwraca nazwę potwora na podstawie liczby."""
        return self.__monsters.get(id, "Nieznany Potwór")
    
    def register(self, mcp: FastMCP) -> None:
        """Rejestruje narzędzia związane z potworami w instancji MCP."""
        
        @mcp.tool(name="get_monster")
        def get_monster(id: int) -> ToolResponse[str]:
            """Zwraca nazwę potwora na podstawie liczby."""
            
            if id not in self.__monsters:
                logger.error(f"Nieprawidłowe ID potwora: {id}")
                return ToolResponse.fail(f"ID potwora musi być między {min(self.__monsters.keys())} a {max(self.__monsters.keys())}. Otrzymano: {id}")   
        
            logger.debug(f"Pobieranie potwora o ID: {id}")
            return ToolResponse.ok(self.__get_monster_by_id(id), f"Pobrano potwora o ID: {id}")