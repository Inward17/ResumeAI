# ResumeAI backend — runs on a Hugging Face Docker Space (or any container host).
# CPU-only PyTorch keeps the image small enough for free hosting.
FROM python:3.13-slim

# Hugging Face Spaces run containers as uid 1000
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    RESUMES_DIR=/home/user/resumes \
    PORT=7860

WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      -r requirements.txt

COPY --chown=user . .
USER user
RUN mkdir -p "$RESUMES_DIR"

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
