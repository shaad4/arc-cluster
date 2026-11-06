from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, directory: str):
    root = Path(directory).resolve()
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "API route not found")
        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(
                503, "Frontend not built; run npm ci && npm run build in frontend"
            )
        if path and Path(path).suffix:
            raise HTTPException(404, "Asset not found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
