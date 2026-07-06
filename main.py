from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import osmnx as ox
import networkx as nx
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="GPS Art Graph Engine")

# Allow CodePen frontend to talk to this local backend
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
        # 1. Find the center of the user's drawing to download the local map grid
        center_lat = sum(p.lat for p in payload.points) / len(payload.points)
        center_lng = sum(p.lng for p in payload.points) / len(payload.points)

        # 2. Download the street graph (nodes and edges) from OpenStreetMap
        # network_type="walk" ensures we get pedestrian paths, alleys, and sidewalks
        G = ox.graph_from_point((center_lat, center_lng), dist=500, network_type="walk")

        route_coordinates = []
        
        # 3. Find the absolute closest street node to every point in the drawing
        nearest_nodes = []
        for pt in payload.points:
            node = ox.distance.nearest_nodes(G, X=pt.lng, Y=pt.lat)
            nearest_nodes.append(node)

        # Close the loop by appending the first node to the end
        nearest_nodes.append(nearest_nodes[0])

        # 4. Connect the dots using NetworkX graph theory (Shortest Path between our anchor nodes)
        for i in range(len(nearest_nodes) - 1):
            start_node = nearest_nodes[i]
            end_node = nearest_nodes[i+1]
            
            try:
                # Find the path connecting the two nodes through the street grid
                path = nx.shortest_path(G, start_node, end_node, weight='length')
                
                # Convert the node IDs back into Lat/Lng coordinates for the frontend
                for node_id in path:
                    node_data = G.nodes[node_id]
                    route_coordinates.append([node_data['y'], node_data['x']])
            except nx.NetworkXNoPath:
                continue # Skip if a gap exists (e.g., crossing a river with no bridge)

        return {"status": "success", "route": route_coordinates}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
