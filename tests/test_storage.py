import os
from hashlib import sha256
from urllib.error import HTTPError
from urllib.request import urlopen
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from call_summary.storage import S3Storage


@pytest.fixture
def storage():
    if not os.environ.get("TEST_S3"):
        pytest.skip("Set TEST_S3=1 and S3_* settings for real MinIO")
    return S3Storage()


def test_s3_contract_and_private_bucket(storage):
    prefix = f"spec01-test/{uuid4()}/"
    data = b"synthetic bytes; no real call audio"
    keys = [prefix + str(i) + ".ogg" for i in range(3)]
    try:
        storage.ready()
        for key in keys:
            assert storage.put(key, data) == sha256(data).hexdigest()
        assert storage.head(keys[0])["ContentLength"] == len(data)
        assert storage.get(keys[0], sha256(data).hexdigest()) == data
        with storage.download(keys[0], sha256(data).hexdigest()) as path:
            assert path.read_bytes() == data
        assert not path.exists()
        with pytest.raises(ValueError), storage.download(keys[0], "0" * 64):
            pytest.fail("checksum mismatch accepted")
        found = []
        cursor = None
        while True:
            page = storage.list(prefix, limit=1, cursor=cursor)
            found.extend(o["Key"] for o in page["objects"])
            if not page["has_more"]:
                break
            assert page["cursor"]
            cursor = page["cursor"]
        assert sorted(found) == keys
        with pytest.raises(HTTPError) as denied:
            urlopen(f"{storage.settings.s3_endpoint_url}/{storage.bucket}/{keys[0]}")
        assert denied.value.code == 403
        assert {b["Name"] for b in storage.client.list_buckets()["Buckets"]} == {
            storage.bucket
        }
        with pytest.raises(ClientError) as denied:
            storage.client.create_bucket(Bucket="spec01-forbidden-" + str(uuid4()))
        assert denied.value.response["Error"]["Code"] == "AccessDenied"
    finally:
        for key in keys:
            storage.delete(key)
    assert not storage.list(prefix)["objects"]
