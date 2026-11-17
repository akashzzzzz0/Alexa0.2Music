FROM python:3.12-alpine
WORKDIR /app
COPY app.py .
COPY conversation_brain.py .
COPY model_runtime.py .

# Fail during image build, rather than at runtime, if the dialogue module
# was omitted from the Docker build context or cannot be imported.
RUN python -m py_compile app.py conversation_brain.py model_runtime.py \
    && python -c "import conversation_brain; assert callable(conversation_brain.respond)"

ENV PORT=3000
EXPOSE 3000
CMD ["python", "app.py"]
