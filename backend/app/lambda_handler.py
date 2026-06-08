"""AWS Lambda 핸들러. Mangum이 APIGW/Function URL 이벤트를 ASGI로 변환한다."""

from mangum import Mangum

from app.main import app

handler = Mangum(app, lifespan="on")
