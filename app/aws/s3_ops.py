import re
import json
from datetime import datetime
from botocore.exceptions import ClientError


def get_next_upload_folder(s3_client, bucket: str, prefix: str) -> str:
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        existing_max = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []) or []:
                p = cp.get("Prefix", "")
                m = re.search(r"upload_id_(\d{3,})/\Z", p)
                if m:
                    existing_max = max(existing_max, int(m.group(1)))
        next_id = existing_max + 1
        return f"{prefix}upload_id_{next_id:03d}/"
    except Exception:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{prefix}upload_id_{ts}/"


def upload_fileobj(s3_client, bucket: str, key: str, fileobj, content_type: str) -> None:
    s3_client.upload_fileobj(
        Fileobj=fileobj,
        Bucket=bucket,
        Key=key,
        ExtraArgs={"ContentType": content_type},
    )


def put_json(s3_client, bucket: str, key: str, data: dict) -> None:
    s3_client.put_object(
        Body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        Bucket=bucket,
        Key=key,
        ContentType="application/json; charset=utf-8",
    )


def get_json_or_none(s3_client, bucket: str, key: str):
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        body = obj.get("Body").read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        return json.loads(body)
    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "")
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise
    except Exception:
        return None
