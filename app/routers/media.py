import uuid

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app import db
from app.auth import get_current_user
from app.media_validate import (
    MAX_PHOTOS,
    MAX_VIDEOS,
    MediaValidationError,
    validate_photo,
    validate_video,
)
from app.storage import StorageError, post_key, upload_and_verify
from app.templating import templates

router = APIRouter()

_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
}


@router.get("/posts/{post_id}/media", response_class=HTMLResponse)
def media_form(request: Request, post_id: str):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    if post is None or post["user_id"] != user["user_id"]:
        return RedirectResponse(f"/posts/{post_id}", status_code=303)

    media = db.list_product_media(post_id)
    photo_count = sum(1 for m in media if m["media_type"] == "photo")
    video_count = sum(1 for m in media if m["media_type"] == "video")
    return templates.TemplateResponse(
        request, "media_form.html",
        {
            "post": post, "media": media, "error": None,
            "photos_left": max(0, MAX_PHOTOS - photo_count),
            "videos_left": max(0, MAX_VIDEOS - video_count),
        },
    )


def _media_form_error(request: Request, post, status_code: int, error: str) -> HTMLResponse:
    media = db.list_product_media(post["post_id"])
    photo_count = sum(1 for m in media if m["media_type"] == "photo")
    video_count = sum(1 for m in media if m["media_type"] == "video")
    return templates.TemplateResponse(
        request, "media_form.html",
        {
            "post": post, "media": media, "error": error,
            "photos_left": max(0, MAX_PHOTOS - photo_count),
            "videos_left": max(0, MAX_VIDEOS - video_count),
        },
        status_code=status_code,
    )


@router.post("/posts/{post_id}/media")
async def media_upload(
    request: Request,
    post_id: str,
    photos: list[UploadFile] = File(default=[]),
    video: UploadFile | None = File(default=None),
):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    if post is None or post["user_id"] != user["user_id"]:
        return RedirectResponse(f"/posts/{post_id}", status_code=303)

    existing = db.list_product_media(post_id)
    photo_count = sum(1 for m in existing if m["media_type"] == "photo")
    video_count = sum(1 for m in existing if m["media_type"] == "video")

    photos = [p for p in photos if p.filename]
    has_video = video is not None and bool(video.filename)

    if photo_count + len(photos) > MAX_PHOTOS:
        return _media_form_error(
            request, post, 422, f"Máximo de {MAX_PHOTOS} fotos por produto (já tens {photo_count})."
        )
    if has_video and video_count + 1 > MAX_VIDEOS:
        return _media_form_error(
            request, post, 422, f"Máximo de {MAX_VIDEOS} vídeo por produto (já tens {video_count})."
        )

    order = photo_count
    try:
        for photo in photos:
            data = await photo.read()
            validate_photo(data, photo.content_type)
            ext = _EXT_BY_CONTENT_TYPE[photo.content_type]
            key = post_key(post_id, f"media/photo-{uuid.uuid4().hex[:8]}.{ext}")
            uploaded = upload_and_verify(key, data, photo.content_type)
            db.add_product_media(
                uuid.uuid4().hex, post_id, "photo", uploaded.key, uploaded.content_type,
                uploaded.size, uploaded.sha256, uploaded.url, order,
            )
            order += 1

        if has_video:
            data = await video.read()
            validate_video(data, video.content_type)
            ext = _EXT_BY_CONTENT_TYPE[video.content_type]
            key = post_key(post_id, f"media/video-{uuid.uuid4().hex[:8]}.{ext}")
            uploaded = upload_and_verify(key, data, video.content_type)
            db.add_product_media(
                uuid.uuid4().hex, post_id, "video", uploaded.key, uploaded.content_type,
                uploaded.size, uploaded.sha256, uploaded.url, 0,
            )
    except MediaValidationError as exc:
        return _media_form_error(request, post, 422, str(exc))
    except StorageError as exc:
        return _media_form_error(request, post, 502, f"Falha ao guardar no B2: {exc}")

    return RedirectResponse(f"/posts/{post_id}", status_code=303)


@router.post("/posts/{post_id}/media/{media_id}/apagar")
def media_delete(request: Request, post_id: str, media_id: str):
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/entrar", status_code=303)

    post = db.get_post(post_id)
    media = db.get_product_media(media_id)
    if post is None or media is None or post["user_id"] != user["user_id"] or media["post_id"] != post_id:
        return RedirectResponse(f"/posts/{post_id}", status_code=303)

    db.delete_product_media(media_id)
    return RedirectResponse(f"/posts/{post_id}/media", status_code=303)
