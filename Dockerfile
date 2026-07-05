# CARINA — containerized laptop profile (implementation-plan Phase 0:
# "the demo, but on a cluster"). Contracts and products are baked into the
# image; mount a volume over /app/products to override, and over /app/data
# to persist the lakehouse between restarts.

FROM python:3.11-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.11-slim
RUN useradd --system --uid 10001 --create-home carina
COPY --from=build /src/dist/*.whl /tmp/
RUN WHEEL=$(ls /tmp/*.whl) && pip install --no-cache-dir "${WHEEL}[auth]" && rm -f /tmp/*.whl

WORKDIR /app
COPY products ./products
# Group 0 ownership + group-write: runs as uid 10001 on vanilla Kubernetes
# and under OpenShift's restricted SCC (arbitrary UID, GID 0) unchanged.
RUN mkdir -p /app/data && chown -R carina:0 /app && chmod -R g+rwX /app
ENV CARINA_ROOT=/app

USER carina
EXPOSE 8899
CMD ["carina", "serve", "--host", "0.0.0.0", "--port", "8899"]
