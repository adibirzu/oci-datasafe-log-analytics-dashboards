FROM fnproject/python:3.11-dev AS build-stage
WORKDIR /function
COPY function/requirements.txt .
RUN pip3 install --target /python/ --no-cache-dir -r requirements.txt

FROM fnproject/python:3.11
WORKDIR /function
COPY --from=build-stage /python /python
COPY src/oci_datasafe_exporter /function/oci_datasafe_exporter
COPY function/func.py /function/func.py
ENV PYTHONPATH=/python:/function
ENV PATH=/python/bin:${PATH}
ENTRYPOINT ["/python/bin/fdk", "/function/func.py", "handler"]
