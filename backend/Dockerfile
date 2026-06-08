FROM public.ecr.aws/lambda/python:3.11

# Pillow 의존성 (Lambda 환경에서 libjpeg 등 필요)
RUN dnf install -y gcc libjpeg-turbo-devel zlib-devel && dnf clean all

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ${LAMBDA_TASK_ROOT}/app/

CMD ["app.lambda_handler.handler"]
