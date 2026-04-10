FROM python:3.13-slim

WORKDIR /app
COPY . .
RUN cd backend && pip install .

CMD cd backend && uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
