FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 애플리케이션 파일 복사
COPY app.py .

# 포트 설정
EXPOSE 5000

# 애플리케이션 실행
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
