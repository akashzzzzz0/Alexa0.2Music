FROM python:3.12-alpine
WORKDIR /app
COPY app.py .
COPY conversation_brain.py .
ENV PORT=3000
EXPOSE 3000
CMD ["python", "app.py"]
