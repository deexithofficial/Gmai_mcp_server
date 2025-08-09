from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test")

@mcp.tool()
def say_hello(name: str):
    """Say hello to a person"""
    return f"Hello {name}!"

@mcp.tool()
def build_vector_db(
    documents: list[str],
    metadata: list[dict],
    name: str,
    description: str,
    ) -> str:
    """Build a vector database from a list of documents and metadata"""

if __name__ == "__main__":
    mcp.run()