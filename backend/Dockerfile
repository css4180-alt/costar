FROM public.ecr.aws/lambda/python:3.11

# Pillow는 manylinux wheel에 libjpeg-turbo/zlib를 번들로 포함하므로
# 별도 시스템 패키지나 컴파일러가 필요 없다(소스 빌드 없이 wheel 설치).

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ${LAMBDA_TASK_ROOT}/app/

CMD ["app.lambda_handler.handler"]
