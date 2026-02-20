"""
Arduino MCP Server - Python implementation.

Run from the project root:
    poetry run python -m simple_mpc_server.main
    
Or directly:
    poetry run python src/simple_mpc_server/main.py
"""

from loguru import logger
from mcp.server.fastmcp import FastMCP
from simple_mpc_server.tools.camera_tool import CameraTool
from simple_mpc_server.tools.file_system_tool import FileSystemTool
from simple_mpc_server.tools.monster_tool import MonsterTool
from simple_mpc_server.tools.thinker_tool import ThinkerTool
from simple_mpc_server.tools.arduino_tool import ArduinoTool
from simple_mpc_server.tools.robot_tool import RobotTool

# Create an MCP server
mcp = FastMCP("ArduinoMcpServer")

# Register tools from modules
FileSystemTool().register(mcp)
MonsterTool().register(mcp)
ThinkerTool().register(mcp)
ArduinoTool().register(mcp)
RobotTool().register(mcp)
CameraTool().register(mcp)

if __name__ == "__main__":
    # Equivalent to app.Run("http://localhost:4444")
    logger.info("Starting Arduino MCP Server on streamable-http transport... [TEST MODE]")
    mcp.run(
        transport="streamable-http",
    )