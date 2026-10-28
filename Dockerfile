FROM python:3.12.16-slim-bookworm@sha256:ab7b5e5ee6144ffa29f93cce3db53f1b41c86414af84f869625a474999e6ef63
WORKDIR /opt/tas
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY production_runtime.py ./production_runtime.py
COPY bin/runtime_adapter bin/runtime_adapter
COPY runners runners
RUN chmod +x production_runtime.py bin/runtime_adapter runners/*.sh
ENTRYPOINT ["/opt/tas/runners/entrypoint.sh"]
