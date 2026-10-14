"""Metadaten-Import (AniList / Jikan) – nur für Admins."""
from flask import Blueprint, request

from .. import metadata, security
from ..auth import can, current_user, role_required
from ..security import fail, limited_response, ok

bp = Blueprint("api_import", __name__)


def _limit():
    return security.rate_limit("import", 40, 600, key=current_user()["id"])


@bp.get("/api/admin/import/search")
@role_required(can.manage_content)
def import_search():
    allowed, retry = _limit()
    if not allowed:
        return limited_response(retry)
    provider = request.args.get("provider", "anilist")
    if provider not in ("anilist", "jikan"):
        return fail("Unbekannter Anbieter.")
    kind = "movie" if request.args.get("kind") == "movie" else "series"
    try:
        return ok(metadata.search(provider, request.args.get("q", ""), kind))
    except metadata.MetadataError as exc:
        return fail(str(exc), 502)


@bp.get("/api/admin/import/fetch")
@role_required(can.manage_content)
def import_fetch():
    allowed, retry = _limit()
    if not allowed:
        return limited_response(retry)
    provider = request.args.get("provider", "anilist")
    item_id = request.args.get("id", "")
    if provider not in ("anilist", "jikan") or not item_id.isdigit():
        return fail("Ungültige Anfrage.")
    movie = request.args.get("kind") == "movie"
    try:
        result = metadata.fetch(provider, int(item_id), with_titles=request.args.get("titles", "1") == "1" and not movie, follow=not movie)
    except metadata.MetadataError as exc:
        return fail(str(exc), 502)
    return ok(result)
