"""Small deployment helper for Supabase's shared pooler.

Supabase projects in the same region can live on different Supavisor shards
(e.g. aws-0, aws-1).  DATABASE_URL remains a secret in Render, while this
module allows only the pooler hostname to be corrected independently through
SUPABASE_POOLER_HOST.  Credentials are never copied into source control.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit


def apply_pooler_host_override() -> bool:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    override_host = os.environ.get("SUPABASE_POOLER_HOST", "").strip()
    if not database_url or not override_host:
        return False

    parsed = urlsplit(database_url)
    current_host = (parsed.hostname or "").lower()
    override_host = override_host.lower()

    # Only allow a Supabase pooler hostname to replace another Supabase pooler
    # hostname.  This prevents the secret DATABASE_URL from being redirected to
    # an arbitrary server because of a bad environment value.
    if not current_host.endswith(".pooler.supabase.com"):
        return False
    if not override_host.endswith(".pooler.supabase.com"):
        raise RuntimeError("SUPABASE_POOLER_HOST deve ser um host pooler.supabase.com.")

    userinfo = ""
    if "@" in parsed.netloc:
        userinfo = parsed.netloc.rsplit("@", 1)[0] + "@"
    port = parsed.port or 5432
    new_netloc = f"{userinfo}{override_host}:{port}"
    os.environ["DATABASE_URL"] = urlunsplit(
        (parsed.scheme, new_netloc, parsed.path, parsed.query, parsed.fragment)
    )
    return current_host != override_host
