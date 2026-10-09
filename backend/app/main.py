from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .routes import chat, inventory, scan

log = config.get_logger("munim")
app = FastAPI(title="Munim")

# Frontend is served from a different port (python -m http.server 5500).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(scan.router)
app.include_router(chat.router)
app.include_router(inventory.router)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # Contract: malformed input is 400; semantic problems are raised as 422 by the routes.
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first["loc"] if p != "body")
    return JSONResponse({"error": f"{where}: {first['msg']}"}, status_code=400)


@app.exception_handler(Exception)
async def unexpected(_: Request, exc: Exception):
    log.exception("unhandled error")
    return JSONResponse({"error": "internal error"}, status_code=500)


@app.get("/api/health")
async def health():
    return {"ok": True, "stubs": __import__("app.routes.errors", fromlist=["x"]).use_stubs()}
