from qdrant_client import QdrantClient
client = QdrantClient(":memory:")
client.create_collection("test", vectors_config={"size": 4, "distance": "Cosine"})
client.upload_points("test", points=[{"id": 1, "vector": [0.1, 0.2, 0.3, 0.4], "payload": {"foo": "bar"}}])
res = client.query_points(collection_name="test", query=[0.1, 0.2, 0.3, 0.4], limit=1)
print(type(res))
print(res)
