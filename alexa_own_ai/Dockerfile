FROM python:3.12-alpine
WORKDIR /app
COPY app.py .
COPY conversation_brain.py .
COPY deep_understanding.py .
COPY context_envelope.py .
COPY conversation_intelligence.py .
COPY personality_profile.py .
COPY feedback_learning.py .
COPY response_decision.py .
COPY model_runtime.py .
COPY ai_router.py .
COPY bootstrap.py .

# Validate all runtime modules during image build, not after deployment.
RUN python -m py_compile app.py conversation_brain.py deep_understanding.py context_envelope.py conversation_intelligence.py personality_profile.py feedback_learning.py response_decision.py model_runtime.py ai_router.py bootstrap.py \
    && python -c "import conversation_brain, deep_understanding, context_envelope, conversation_intelligence, personality_profile, feedback_learning, response_decision, model_runtime, ai_router; assert callable(ai_router.route_response)"

ENV PORT=3000
EXPOSE 3000
CMD ["python", "bootstrap.py"]
