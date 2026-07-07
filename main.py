from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import osmnx as ox
import networkx as nx
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="GPS Art Graph Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

class Point(BaseModel):
    lat: float
    lng: float

class ShapePayload(BaseModel):
    points: List[Point]

@app.post("/match-shape")
async def match_shape(payload: ShapePayload):
    if len(payload.points) < 3:
        raise HTTPException(status_code=400, detail="Need at least 3 points to form a shape.")

    try:
        center_lat = sum(p.lat for p in payload.points) / len(payload.points)
        center_lng = sum(p.lng for p in payload.points) / len(payload.points)

        # CRITICAL FIX 1: Use "drive" network to guarantee fully connected road coverage
        # CRITICAL FIX 2: Increase search radius to 800m to easily cover your drawn shapes
        G = ox.graph_from_point((center_lat, center_lng), dist=800, network_type="drive")
        
        # CRITICAL FIX 3: Force the engine to only use the largest connected web of streets
        # This completely prevents "No Path" dead-end errors
        G = ox.utils_graph.get_largest_component(G, strongly=True)

        route_coordinates = []
        
        nearest_nodes = []
        for pt in payload.points:
            node = ox.distance.nearest_nodes(G, X=pt.lng, Y=pt.lat)
            nearest_nodes.append(node)

        # Close the loop
        nearest_nodes.append(nearest_nodes[0])

        for i in range(len(nearest_nodes) - 1):
            start_node = nearest_nodes[i]
            end_node = nearest_nodes[i+1]
            
            try:
                # Find the shortest path through the actual street grid
                path = nx.shortest_path(G, start_node, end_node, weight='length')
                
                for node_id in path:
                    node_data = G.nodes[node_id]
                    route_coordinates.append([node_data['y'], node_data['x']])
            except nx.NetworkXNoPath:
                continue 

        return {"status": "success", "route": route_coordinates}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
