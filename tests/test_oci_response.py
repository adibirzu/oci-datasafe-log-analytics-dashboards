import pytest
from urllib3.response import HTTPResponse

from oci_datasafe_exporter.oci_response import response_bytes


class ContentResponse:
    content = b"content-body"


class DataResponse:
    data = b"data-body"


def test_response_bytes_accepts_raw_and_streaming_sdk_payloads():
    assert response_bytes(b"raw") == b"raw"
    assert response_bytes(bytearray(b"bytearray")) == b"bytearray"
    assert response_bytes(ContentResponse()) == b"content-body"
    assert response_bytes(DataResponse()) == b"data-body"


def test_response_bytes_reads_the_urllib3_stream_used_by_oci_functions():
    response = HTTPResponse(body=b'{"exported": 1}', preload_content=True)
    assert response_bytes(response) == b'{"exported": 1}'


def test_response_bytes_rejects_unknown_response_shape():
    with pytest.raises(TypeError, match="byte payload"):
        response_bytes(object())
