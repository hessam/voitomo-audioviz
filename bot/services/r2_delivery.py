"""Deliver finished videos through Cloudflare R2 at full quality.

R2 speaks the S3 protocol, so this signs requests with AWS Signature V4 using only the standard
library plus aiohttp (no new dependency). The bot uploads the file, then sends the user a
presigned link that stops working after `expires` seconds. Delete the stored object with a bucket
lifecycle rule (Object lifecycle rules > delete after 1 day); the bot never needs delete rights.
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import aiohttp

DEFAULT_EXPIRES_S = 24 * 3600


@dataclass
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    region: str = "auto"

    @property
    def host(self) -> str:
        return f"{self.account_id}.r2.cloudflarestorage.com"


def load_config() -> Optional[R2Config]:
    """None when R2 is not configured, so callers fall back to Telegram delivery."""
    values = [os.environ.get(k, "").strip() for k in
              ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")]
    return R2Config(*values) if all(values) else None


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def presign(method: str, host: str, path: str, region: str, access_key: str, secret_key: str,
            expires: int = DEFAULT_EXPIRES_S, now: Optional[datetime] = None) -> str:
    """Presigned URL (query-string SigV4, unsigned payload) for `method` on `path` at `host`."""
    now = now or datetime.now(timezone.utc)
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    scope = f"{day}/{region}/s3/aws4_request"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": stamp,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    query = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(params.items()))
    canonical = "\n".join([method, quote(path, safe="/"), query, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(("AWS4" + secret_key).encode(), day)
    for part in (region, "s3", "aws4_request"):
        k = _sign(k, part)
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    return f"https://{host}{quote(path, safe='/')}?{query}&X-Amz-Signature={signature}"


async def upload_and_link(config: R2Config, file_path: str, object_key: str,
                          expires: int = DEFAULT_EXPIRES_S) -> str:
    """Upload `file_path` to R2 and return a link valid for `expires` seconds."""
    path = f"/{config.bucket}/{object_key}"
    put_url = presign("PUT", config.host, path, config.region, config.access_key_id,
                      config.secret_access_key, expires=900)
    size = os.path.getsize(file_path)
    timeout = aiohttp.ClientTimeout(total=900)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        with open(file_path, "rb") as handle:
            async with session.put(put_url, data=handle, headers={
                "Content-Type": "video/mp4", "Content-Length": str(size)}) as response:
                if response.status >= 300:
                    raise RuntimeError(f"R2 upload failed: HTTP {response.status} {(await response.text())[:200]}")
    return presign("GET", config.host, path, config.region, config.access_key_id,
                   config.secret_access_key, expires=expires)
