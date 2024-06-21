from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import aiofiles
import boto3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

S3_URL = "https://s3.timeweb.cloud"
S3_REGION = "ru-1"
S3_PUBLIC_PATH_STYLE = "https://s3.timeweb.cloud/68597a50-solrikk/{file_name}"
S3_PUBLIC_VIRTUAL_HOSTED_STYLE = "https://_yourkey_k.s3.timeweb.cloud/{file_name}"

S3_ACCESS_KEY = "2YLZ7SZSE6AJQE58PK85"
S3_SECRET_ACCESS_KEY = "_yourkey_"
S3_BUCKET = "_yourkey_"

s3_client = boto3.client('s3',
                         endpoint_url=S3_URL,
                         aws_access_key_id=S3_ACCESS_KEY,
                         aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                         region_name=S3_REGION)


def shorten_filename(filename, max_length=10):
  ext = filename[filename.rfind('.'):]
  base_name = filename[:filename.rfind('.')]
  return base_name[:max_length].replace(' ', '_') + ext


@app.get("/", response_class=HTMLResponse)
async def main():
  async with aiofiles.open("index.html", "r") as f:
    content = await f.read()
  return HTMLResponse(content=content)


@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...)):
  supported_file_types = ('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov',
                          '.avi', '.mkv', '.zip', '.rar')

  file_urls = []

  for file in files:
    if not file.filename.lower().endswith(supported_file_types):
      continue

    original_filename = file.filename
    short_filename = shorten_filename(original_filename)
    unique_filename = f"{uuid.uuid4().hex[:8]}_{short_filename}"

    content = await file.read()

    s3_client.put_object(Bucket=S3_BUCKET,
                         Key=unique_filename,
                         Body=content,
                         ACL='public-read',
                         ContentType=file.content_type)

    file_url = S3_PUBLIC_VIRTUAL_HOSTED_STYLE.format(file_name=unique_filename)
    file_urls.append(file_url)

  return JSONResponse(content={"file_urls": file_urls})


@app.get("/files/")
async def get_files():
  response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
  files = response.get('Contents', [])

  available_files = []
  for file in files:
    file_url = S3_PUBLIC_VIRTUAL_HOSTED_STYLE.format(file_name=file['Key'])
    available_files.append({"filename": file['Key'], "url": file_url})

  return JSONResponse(content={"available_files": available_files})


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)
