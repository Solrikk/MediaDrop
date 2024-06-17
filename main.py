from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import aiofiles
import psycopg2.pool
from pyunpack import Archive
from pathlib import Path
import shutil

app = FastAPI()

UPLOAD_DIR = Path("uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

DATABASE_URL = "postgresql://gen_user:y~%25%3BG9934fsP%26H@176.57.217.236:5432/default_db"
pool = psycopg2.pool.SimpleConnectionPool(0, 80, DATABASE_URL)


@app.on_event("shutdown")
async def shutdown():
  pool.closeall()


def create_table():
  conn = pool.getconn()
  cur = conn.cursor()
  cur.execute("DROP TABLE IF EXISTS uploads;")
  cur.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            file_url TEXT NOT NULL,
            file_content BYTEA NOT NULL
        );
    """)
  conn.commit()
  cur.close()
  pool.putconn(conn)


create_table()


@app.get("/", response_class=HTMLResponse)
async def main():
  async with aiofiles.open("index.html", "r") as f:
    content = await f.read()
  return HTMLResponse(content=content)


@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...)):
  supported_file_types = ('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov',
                          '.avi', '.mkv', '.zip', '.rar')
  temp_dir = Path('temp_uploads')
  temp_dir.mkdir(parents=True, exist_ok=True)

  file_urls = []
  uploaded_files = set()

  for file in files:
    if file.filename in uploaded_files or not file.filename.lower().endswith(
        supported_file_types):
      continue

    sanitized_filename = ''.join(
        c if c.isalnum() or c in '-_.' else '_'
        for c in file.filename.replace(' ', '_')).strip('_')

    filename_main_part = "_".join(sanitized_filename.split('_')[:5])
    filename_ext = file.filename.split('.')[-1]

    if filename_ext in ['zip', 'rar']:
      archive_path = temp_dir / file.filename
      async with aiofiles.open(archive_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
      Archive(str(archive_path)).extractall(str(temp_dir))

      extracted_files = list(temp_dir.glob('**/*'))
      for extracted_file in extracted_files:
        if extracted_file.suffix.lower() in supported_file_types:
          content = extracted_file.read_bytes()
          await handle_single_file(extracted_file.name, content, file_urls)

    else:
      content = await file.read()
      await handle_single_file(file.filename, content, file_urls)

    uploaded_files.add(file.filename)

  shutil.rmtree(temp_dir)
  return JSONResponse(content={"file_urls": file_urls})


async def handle_single_file(filename, content, file_urls):
  unique_filename = f"{Path(filename).stem}_{uuid.uuid4().hex[:8]}{Path(filename).suffix}"
  file_path = UPLOAD_DIR / unique_filename

  async with aiofiles.open(file_path, 'wb') as out_file:
    await out_file.write(content)

  file_url = f"http://{os.environ.get('HOSTNAME', 'localhost')}/uploads/{unique_filename}"
  file_urls.append(file_url)

  conn = pool.getconn()
  cur = conn.cursor()
  cur.execute(
      "INSERT INTO uploads (filename, file_url, file_content) VALUES (%s, %s, %s)",
      (filename, file_url, content))
  conn.commit()
  cur.close()
  pool.putconn(conn)


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)
