# Sandbox for agent runs: OpenCode plus everything the Anthropic skills (pptx, docx, xlsx, frontend-design) call for.
# build.sh copies the host's opencode binary into the build context. Agents never install anything at run time.
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    git ripgrep ca-certificates curl nodejs npm \
    libreoffice-writer libreoffice-impress libreoffice-calc libreoffice-java-common- default-jre-headless- \
    poppler-utils pandoc graphviz gcc libc6-dev \
    fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu fonts-urw-base35 fonts-noto-core fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

# Node libraries named by the skills: pptxgenjs, docx, react-icons with react and react-dom, sharp.
# three 0.147 still ships the UMD build and OrbitControls, so the scene agent can inline them into one HTML file.
ENV NODE_PATH=/usr/local/lib/node_modules
RUN npm install -g --no-fund --no-audit pptxgenjs docx react-icons react react-dom sharp three@0.147.0 \
 && npm cache clean --force

RUN pip install --no-cache-dir \
    python-docx==1.1.2 python-pptx==1.0.2 openpyxl==3.1.5 pandas==2.2.3 matplotlib==3.9.2 numpy==2.1.3 \
    "markitdown[pptx,docx,xlsx]" Pillow defusedxml lxml

COPY opencode /usr/local/bin/opencode
COPY preview.py /usr/local/bin/ar-preview
COPY sheets_json.py /usr/local/bin/ar-sheets-json
COPY look.py /usr/local/bin/ar-look
COPY pptx_helpers.js /usr/local/lib/ar/pptx_helpers.js
RUN chmod +x /usr/local/bin/ar-preview /usr/local/bin/ar-sheets-json /usr/local/bin/ar-look

RUN useradd --create-home --uid 1000 runner
USER runner
ENV HOME=/home/runner MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1 SAL_USE_VCLPLUGIN=svp
WORKDIR /work
