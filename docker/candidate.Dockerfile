FROM mcr.microsoft.com/playwright/python:v1.58.0-noble
COPY docker/candidate_entry.py /opt/candidate_entry.py
USER pwuser
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/opt/candidate_entry.py"]
