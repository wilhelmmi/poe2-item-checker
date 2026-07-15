from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

app = FastAPI(title="PoE 2 Gear & Trade Checker", version="0.1.0")
app.include_router(router)


@app.get("/api/{path:path}", include_in_schema=False)
async def unknown_api(path: str) -> None:
    raise HTTPException(status_code=404)

static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = static_dir / path
        return FileResponse(candidate if candidate.is_file() else static_dir / "index.html")
