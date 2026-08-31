# Hugging Face Spaces (Docker SDK) build for trace-gui.
#
# This installs trace-hep straight from the GitHub repo (not PyPI --
# TRACE-HEP is only on TestPyPI right now) and runs the live viewer bound to
# the port Spaces expects, with --no-browser since there's no browser here.
#
# To deploy: create a Space with SDK=Docker, then push this directory's
# contents (Dockerfile + README.md) as the Space repo's root -- see
# deploy/huggingface-space/README.md in the main repo for exact commands.

FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "trace-hep[all] @ git+https://github.com/wasikatcern/TRACE-HEP.git"

EXPOSE 7860

CMD ["python", "-m", "tracehep.webapp", "--host", "0.0.0.0", "--port", "7860", "--no-browser"]
