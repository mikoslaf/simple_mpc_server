"""
Arduino MCP Server - Python implementation.

Run from the project root:
    poetry run python -m simple_mpc_server.main
    
Or directly:
    poetry run python src/simple_mpc_server/main.py
"""

from loguru import logger
from mcp.server.fastmcp import FastMCP
from simple_mpc_server.tools.file_system_tool import FileSystemTool
from simple_mpc_server.tools.monster_tool import MonsterTool
from simple_mpc_server.tools.thinker_tool import ThinkerTool

# Create an MCP server
mcp = FastMCP("ArduinoMcpServer")

# Register tools from modules
FileSystemTool().register(mcp)
MonsterTool().register(mcp)
ThinkerTool().register(mcp)

if __name__ == "__main__":
    # Equivalent to app.Run("http://localhost:4444")
    logger.info("Starting Arduino MCP Server on streamable-http transport... [TEST MODE]")
    mcp.run(
        transport="streamable-http",
    )

# import serial, time

# ser = serial.Serial("COM4", 115200, timeout=1)
# print(ser.readline().decode(errors="ignore").strip())  # READY

# ser.write(b"PING\n")
# print("<-", ser.readline().decode().strip())

# ser.write(b"LED 1\n")
# print("<-", ser.readline().decode().strip())
# time.sleep(1)
# ser.write(b"LED 0\n")
# print("<-", ser.readline().decode().strip())

# ser.write(b"SET D 13 1\n")
# print("<-", ser.readline().decode().strip())

# ser.write(b"GET D 13\n")
# print("<-", ser.readline().decode().strip())

# ser.write(b"GET A 0\n")  # A0
# print("<-", ser.readline().decode().strip())

# ser.close()