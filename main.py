import osmnx as ox
import networkx as nx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
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

        # 1. Download ALL paths (roads, sidewalks, alleys)
        G = ox.graph_from_point((center_lat, center_lng), dist=800, network_type="all")
        
        # 2. Convert to an undirected graph. This deletes all one-way street rules so the math can route anywhere!
        G = G.to_undirected()
        
        # 3. Keep only the largest connected chunk of streets (deletes isolated nodes/islands)
        largest_cc = max(nx.connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()

        route_coordinates = []
        nearest_nodes = []
        
        # 4. Snap drawing points to the nearest valid map node
        for pt in payload.points:
            node = ox.distance.nearest_nodes(G, X=pt.lng, Y=pt.lat)
            nearest_nodes.append(node)

        nearest_nodes.append(nearest_nodes[0]) # Close the loop

        # 5. Connect the dots
        for i in range(len(nearest_nodes) - 1):
            start_node = nearest_nodes[i]
            end_node = nearest_nodes[i+1]
            
            if start_node == end_node:
                continue # Skip if points snapped to the same exact intersection
            
            try:
                path = nx.shortest_path(G, start_node, end_node, weight='length')
                for node_id in path:
                    node_data = G.nodes[node_id]
                    route_coordinates.append([node_data['y'], node_data['x']])
            except nx.NetworkXNoPath:
                continue 

        if not route_coordinates:
            raise HTTPException(status_code=400, detail="Path calculation failed to find any routes.")

        return {"status": "success", "route": route_coordinates}

    except Exception as e:
        # This catches ANY crash and sends the exact error reason back to your CodePen!
        raise HTTPException(status_code=500, detail=f"Python Crash: {str(e)}")
