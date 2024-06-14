from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import aiofiles
import psycopg2.pool

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

DATABASE_URL = "postgres://youremail:yourpassword@localhost:5432/yourdatabase"
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
  file_urls = []

  for file in files:
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    content = await file.read()

    async with aiofiles.open(file_path, 'wb') as out_file:
      await out_file.write(content)

    file_url = f"http://{os.environ.get('HOSTNAME', 'localhost')}/uploads/{unique_filename}"
    file_urls.append(file_url)

    conn = pool.getconn()
    cur = conn.cursor()
    cur.execute(
        """
            INSERT INTO uploads (filename, file_url, file_content)
            VALUES (%s, %s, %s)
            """, (file.filename, file_url, content))
    conn.commit()
    cur.close()
    pool.putconn(conn)

  return JSONResponse(content={"file_urls": file_urls})


if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=8000)
