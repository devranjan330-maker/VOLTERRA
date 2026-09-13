from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Example metrics
def_requests_total = Counter(
    "volterra_requests_total", "Total number of HTTP requests", ["method", "endpoint"]
)
request_latency_seconds = Histogram(
    "volterra_request_latency_seconds",
    "Latency of HTTP requests in seconds",
    ["method", "endpoint"],
)

router = APIRouter()

@router.get("/metrics")
async def metrics():
    # The Prometheus client already tracks default process metrics.
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
