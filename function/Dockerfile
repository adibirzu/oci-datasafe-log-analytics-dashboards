FROM fnproject/python:3.11-dev AS build-stage
WORKDIR /function
COPY function/requirements.txt .
RUN pip3 install --target /python/ --no-cache-dir -r requirements.txt

FROM fnproject/python:3.11
WORKDIR /function
COPY --from=build-stage /python /python
COPY src/oci_datasafe_exporter /function/oci_datasafe_exporter
COPY scripts/deploy_detections.py /function/deploy_detections.py
COPY terraform/detections.json /function/detections.json
COPY function/func.py /function/func.py
ENV PYTHONPATH=/python:/function
ENV DETECTIONS_CATALOG=/function/detections.json
ENV PATH=/python/bin:${PATH}
ENTRYPOINT ["/python/bin/fdk", "/function/func.py", "handler"]
