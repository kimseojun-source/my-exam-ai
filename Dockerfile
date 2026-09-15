FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_ROOT=/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/*

COPY My_Exam_AI_Website_6_0.zip /tmp/app.zip
RUN unzip /tmp/app.zip -d /tmp/src \
    && cp -a /tmp/src/My_Exam_AI_Website_6_0/. /app/ \
    && rm -rf /tmp/app.zip /tmp/src

COPY server.py /app/server.py

RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /data

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
