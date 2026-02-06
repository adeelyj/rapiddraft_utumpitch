FROM node:20-bullseye AS web-build

WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM mambaorg/micromamba:1.5.8

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY server/requirements.txt server/requirements_pythonocc.txt /app/server/
RUN micromamba create -y -n app -c conda-forge python=3.11 freecad pythonocc-core \
  && micromamba clean -a -y
RUN micromamba run -n app pip install --no-cache-dir -r /app/server/requirements.txt

COPY server /app/server
COPY template /app/template
COPY --from=web-build /app/web/dist /app/web/dist

ENV FREECAD_LIB=/opt/conda/envs/app/lib
ENV FREECAD_BIN=/opt/conda/envs/app/bin
ENV PATH=/opt/conda/envs/app/bin:$PATH

USER root
RUN mkdir -p /app/server/data/models /app/server/data/processing \
  && chown -R ${MAMBA_USER}:${MAMBA_USER} /app/server/data
USER ${MAMBA_USER}

EXPOSE 8000
CMD ["sh", "-c", "micromamba run -n app uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
