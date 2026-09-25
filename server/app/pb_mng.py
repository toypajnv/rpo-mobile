from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response

from .pwa_assets import make_icon_png

router = APIRouter()
PB_MNG_DIR = Path(__file__).resolve().parent / "pb_mng"


@router.get("/pb-mng", include_in_schema=False)
def pb_mng_redirect():
    return RedirectResponse("/pb-mng/", status_code=307)


@router.get("/pb-mng/", include_in_schema=False)
def pb_mng_index():
    return FileResponse(
        PB_MNG_DIR / "index.html",
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/pb-mng/app.css", include_in_schema=False)
def pb_mng_css():
    return FileResponse(PB_MNG_DIR / "app.css", media_type="text/css; charset=utf-8")


@router.get("/pb-mng/app.js", include_in_schema=False)
def pb_mng_js():
    return FileResponse(PB_MNG_DIR / "app.js", media_type="application/javascript; charset=utf-8")


@router.get("/pb-mng/coordinator.js", include_in_schema=False)
def pb_mng_coordinator_js():
    return FileResponse(
        PB_MNG_DIR / "coordinator.js",
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/pb-mng/manifest.webmanifest", include_in_schema=False)
def pb_mng_manifest():
    return FileResponse(
        PB_MNG_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/pb-mng/sw.js", include_in_schema=False)
def pb_mng_service_worker():
    return FileResponse(
        PB_MNG_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/pb-mng/"},
    )


@router.get("/pb-mng/icon-{size}.png", include_in_schema=False)
def pb_mng_icon(size: int):
    try:
        content = make_icon_png(size)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Иконка не найдена") from exc
    return Response(content=content, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
