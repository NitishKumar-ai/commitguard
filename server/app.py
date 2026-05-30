"""CommitGuard v2 — FastAPI server with v2 scan endpoints and v1 legacy compatibility.

Endpoints:
    POST /scan              Enqueue a repo scan job
    GET  /status/{job_id}   Poll job status and partial results
    GET  /findings/{job_id} Return full findings list
    GET  /health            Liveness check
    POST /reset             Legacy v1 endpoint
    POST /step              Legacy v1 endpoint
    GET  /state             Legacy v1 endpoint
"""

from commitguard_env.server import app as v1_app, main as v1_main
from commitguard_env.server_v2 import create_v2_app

# Build the unified app
app = create_v2_app(v1_app)


def main() -> None:
    """Run the unified v1+v2 server."""
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
