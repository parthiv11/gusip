FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 gusip \
    && useradd --uid 10001 --gid gusip --create-home --shell /usr/sbin/nologin gusip

COPY requirements.txt .
# CPU wheels only. `pip install ultralytics` on amd64 otherwise pulls CUDA torch (~6GB).
RUN grep -v '^ultralytics' requirements.txt > /tmp/req.txt \
 && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r /tmp/req.txt \
 && pip install --no-cache-dir ultralytics==8.3.70 --no-deps \
 && pip install --no-cache-dir opencv-python-headless matplotlib pandas seaborn psutil py-cpuinfo ultralytics-thop scipy tqdm requests

COPY --chown=gusip:gusip . .
RUN mkdir -p /app/data && chown -R gusip:gusip /app/data

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
