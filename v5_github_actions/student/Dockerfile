FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY database.py .
COPY models.py .
COPY streamlit_app.py .
COPY services/ ./services/
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8000
EXPOSE 8501

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
