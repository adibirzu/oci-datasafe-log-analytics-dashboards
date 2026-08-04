from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_function_image_exposes_dependencies_and_handler_to_fdk():
    dockerfile = (ROOT / "function" / "Dockerfile").read_text()
    assert "ENV PYTHONPATH=/python:/function" in dockerfile
    assert 'ENTRYPOINT ["/python/bin/fdk", "/function/func.py", "handler"]' in dockerfile
    assert "COPY scripts/deploy_detections.py /function/deploy_detections.py" in dockerfile
    assert "COPY terraform/detections.json /function/detections.json" in dockerfile
