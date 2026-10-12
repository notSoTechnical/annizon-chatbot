FROM python:3.12-slim

WORKDIR /app

# install deps first (cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Streamlit reads secrets from env vars too: GEMINI_API_KEY, RESEND_API_KEY, ADMIN_PASSWORD
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
