from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

app = FastAPI(title="PoE 2 Build Item Checker", version="0.1.0")
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    if request.url.path.endswith("/equipment/import"):
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "invalid_equipment_snapshot",
                    "message": "Der Equipment-Snapshot ist unvollständig oder entspricht nicht dem unterstützten Schema.",
                }
            },
        )
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


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
