import urllib.parse
import re
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import aiofiles
import boto3
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

S3_URL = "https://s3.timeweb.cloud"
S3_REGION = "ru-1"
S3_PUBLIC_VIRTUAL_HOSTED_STYLE = "https://solrikk.s3.timeweb.cloud/{file_name}"
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")

s3_client = boto3.client('s3',
                         endpoint_url=S3_URL,
                         aws_access_key_id=S3_ACCESS_KEY,
                         aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                         region_name=S3_REGION)


@app.get("/", response_class=HTMLResponse)
async def main():
  async with aiofiles.open("index.html", "r") as f:
    content = await f.read()
  return HTMLResponse(content=content)


def sanitize_filename(filename):
  filename = re.sub(r'[^A-Za-z0-9]+', '-', filename)
  filename = filename[:20].strip('-')
  return filename


@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...)):
  supported_file_types = ('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov',
                          '.avi', '.mkv', '.zip', '.rar')
  file_urls = []
  for file in files:
    if not file.filename.lower().endswith(supported_file_types):
      continue

    unique_id = uuid.uuid4().hex[:8]
    sanitized_filename = sanitize_filename(file.filename.rsplit('.', 1)[0])
    file_extension = file.filename.rsplit('.', 1)[1]
    new_filename = f"{unique_id}-{sanitized_filename}.{file_extension}"

    # Читаем файл в память
    content = await file.read()

    try:
      # Upload to S3
      s3_client.put_object(Bucket=S3_BUCKET,
                           Key=new_filename,
                           Body=content,
                           ACL='public-read',
                           ContentType=file.content_type)
    except Exception as e:
      print(f"S3 Upload Error: {str(e)}")
      if "AccessDenied" in str(e):
        raise HTTPException(status_code=500,
                          detail="S3 access denied. Check your credentials.")
      elif "NoSuchBucket" in str(e):
        raise HTTPException(status_code=500,
                          detail="S3 bucket not found. Check your bucket name.")
      else:
        raise HTTPException(status_code=500,
                          detail=f"S3 upload failed: {str(e)}")

    file_url = S3_PUBLIC_VIRTUAL_HOSTED_STYLE.format(file_name=new_filename)
    file_urls.append(file_url)

  return JSONResponse(content={"file_urls": file_urls})


@app.get("/files/")
async def get_files():
  response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
  files = response.get('Contents', [])
  available_files = []
  for file in files:
    file_url = S3_PUBLIC_VIRTUAL_HOSTED_STYLE.format(
        file_name=urllib.parse.quote(file['Key'], safe=''))
    available_files.append({"filename": file['Key'], "url": file_url})
  return JSONResponse(content={"available_files": available_files})


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="127.0.0.1", port=8000)
