import os
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase


class Neo4jClient:
    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self._uri = uri or os.environ["NEO4J_URI"]
        self._username = username or os.environ["NEO4J_USERNAME"]
        self._password = password or os.environ["NEO4J_PASSWORD"]
        self._database = database or os.environ.get("NEO4J_DATABASE", "neo4j")
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._username, self._password)
        )

    async def run_query(
        self, cypher: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return a list of record dicts."""
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, params or {})
            records = await result.data()
            return records

    async def close(self) -> None:
        await self._driver.close()
