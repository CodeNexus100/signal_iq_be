import networkx as nx
from typing import Dict, Any, Tuple

class RoadNetwork:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_intersection(self, intersection_id: str, pos: Tuple[float, float]):
        self.graph.add_node(intersection_id, pos=pos, type="intersection")

    def add_road(self, u: str, v: str, length: float, lanes: int = 1, geometry: Any = None):
        self.graph.add_edge(u, v, length=length, lanes=lanes, geometry=geometry)

    def get_edge_data(self, u: str, v: str) -> Dict[str, Any]:
        return self.graph.get_edge_data(u, v)

    def get_node_pos(self, u: str) -> Tuple[float, float]:
        return self.graph.nodes[u].get('pos', (0.0, 0.0))
