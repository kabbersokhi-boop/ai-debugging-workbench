FROM python:3.12.14-slim-bookworm@sha256:0f5b26b9518d002b6173fd61daad821fa340635ebfec5bba471013f9ca114579
# Fixed, build-time dependencies; candidate execution never resolves dependencies.
RUN pip install --no-cache-dir pytest==8.3.5 iniconfig==2.1.0 packaging==24.2 pluggy==1.5.0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
WORKDIR /source
USER 1000:1000
