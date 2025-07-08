import os
import csv
import io
import aiohttp
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiofiles
import uuid
import re
import logging
from fastapi.responses import FileResponse
import pandas as pd
import asyncio
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

PHOTO_DIR = "photo"
UPLOAD_DIR = "static/uploads"
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Глобальный кэш для обработанных URL
url_cache: Dict[str, str] = {}
folder_cache: Dict[str, List[str]] = {}

@app.get("/", response_class=HTMLResponse)
async def main():
    async with aiofiles.open("index.html", "r") as f:
        content = await f.read()
    return HTMLResponse(content=content)

def sanitize_filename(filename):
    filename = re.sub(r'[^A-Za-z0-9]+', '-', filename)
    filename = filename[:20].strip('-')
    return filename

async def download_yandex_file(url: str, session: aiohttp.ClientSession) -> Optional[bytes]:
    try:
        # Проверяем кэш
        if url in url_cache:
            logger.info(f"Using cached result for URL: {url}")
            return None  # Уже обработан

        file_id = url.split('/')[-1]
        api_url = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={url}"

        async with session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()
                direct_url = data.get('href')

                if direct_url:
                    async with session.get(direct_url) as download_response:
                        if download_response.status == 200:
                            content = await download_response.read()
                            if len(content) > MAX_FILE_SIZE:
                                logger.error(f"Downloaded file too large: {len(content)} bytes")
                                return None
                            return content

        logger.error(f"Failed to download from Yandex.Disk: {url}")
        return None
    except Exception as e:
        logger.error(f"Error downloading from Yandex.Disk: {str(e)}")
        return None

async def get_yandex_folder_contents(folder_url: str, session: aiohttp.ClientSession) -> List[dict]:
    try:
        # Проверяем кэш папки
        if folder_url in folder_cache:
            logger.info(f"Using cached folder contents for: {folder_url}")
            return [{"name": f"cached_{i}.jpg", "download_url": url} for i, url in enumerate(folder_cache[folder_url])]

        api_url = f"https://cloud-api.yandex.net/v1/disk/public/resources?public_key={folder_url}&limit=1000"

        async with session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()
                items = data.get('_embedded', {}).get('items', [])

                image_files = []
                for item in items:
                    if item.get('type') == 'file':
                        mime_type = item.get('mime_type', '')
                        if mime_type.startswith('image/'):
                            image_files.append({
                                'name': item.get('name', ''),
                                'download_url': item.get('file', '')
                            })

                return image_files
            else:
                logger.error(f"Failed to get folder contents: {response.status}")
                return []
    except Exception as e:
        logger.error(f"Error getting folder contents: {str(e)}")
        return []

MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_FILES_COUNT = 20
MAX_CONCURRENT_DOWNLOADS = 10  # Ограничиваем количество одновременных загрузок

async def process_url_batch(urls: List[str], session: aiohttp.ClientSession, request: Request) -> Dict[str, str]:
    """Обрабатывает пакет уникальных URL параллельно"""
    url_mapping = {}
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

    async def process_single_url(url: str) -> None:
        async with semaphore:
            if url in url_cache:
                url_mapping[url] = url_cache[url]
                return

            logger.info(f"Processing URL: {url}")

            folder_items = await get_yandex_folder_contents(url, session)

            if folder_items:
                logger.info(f"Found folder with {len(folder_items)} images")
                folder_urls = []

                # Обрабатываем только первые 5 изображений для производительности
                for item in folder_items[:5]:
                    if item['download_url']:
                        try:
                            async with session.get(item['download_url']) as response:
                                if response.status == 200:
                                    file_content = await response.read()

                                    if len(file_content) > MAX_FILE_SIZE:
                                        continue

                                    unique_id = uuid.uuid4().hex[:8]
                                    original_name = item['name']
                                    if '.' in original_name:
                                        extension = original_name.split('.')[-1].lower()
                                        if extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                                            new_filename = f"{unique_id}.{extension}"
                                        else:
                                            new_filename = f"{unique_id}.jpg"
                                    else:
                                        new_filename = f"{unique_id}.jpg"

                                    photo_path = os.path.join(PHOTO_DIR, new_filename)

                                    async with aiofiles.open(photo_path, 'wb') as photo_file:
                                        await photo_file.write(file_content)

                                    new_url = f"{request.base_url}photos/{new_filename}"
                                    folder_urls.append(new_url)
                        except Exception as e:
                            logger.error(f"Error downloading {item['name']}: {str(e)}")
                            continue

                if folder_urls:
                    result = "///".join(folder_urls)
                    url_mapping[url] = result
                    url_cache[url] = result
                    folder_cache[url] = folder_urls
            else:
                file_content = await download_yandex_file(url, session)
                if file_content:
                    unique_id = uuid.uuid4().hex[:8]
                    new_filename = f"{unique_id}.jpg"
                    photo_path = os.path.join(PHOTO_DIR, new_filename)

                    async with aiofiles.open(photo_path, 'wb') as photo_file:
                        await photo_file.write(file_content)

                    new_url = f"{request.base_url}photos/{new_filename}"
                    url_mapping[url] = new_url
                    url_cache[url] = new_url

    # Обрабатываем уникальные URL параллельно
    unique_urls = list(set(urls))
    logger.info(f"Processing {len(unique_urls)} unique URLs out of {len(urls)} total URLs")

    tasks = [process_single_url(url) for url in unique_urls]
    await asyncio.gather(*tasks, return_exceptions=True)

    return url_mapping

@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...), columns: str = Form(None)):
    logger.info("Starting file upload process")

    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(status_code=400, detail=f"Too many files. Maximum {MAX_FILES_COUNT} files allowed")

    for file in files:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} is too large. Maximum size is 50MB")
        await file.seek(0)

    supported_file_types = ('.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov',
                           '.avi', '.mkv', '.zip', '.rar', '.csv', '.txt')
    file_urls = []
    link_replacements = {}

    csv_columns = None
    for file in files:
        if file.filename.lower().endswith('.csv'):
            content = (await file.read()).decode('utf-8-sig')
            csv_reader = csv.DictReader(io.StringIO(content), delimiter=';')
            csv_columns = list(next(csv_reader).keys())
            await file.seek(0)
            break

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for file in files:
            try:
                if file.filename.lower().endswith('.csv'):
                    if not columns and csv_columns:
                        columns = ",".join(csv_columns)
                    if not columns:
                        columns = "Образец ткани,Фотоконтент,Техническая информация"
                    process_columns = [col.strip() for col in columns.split(',')]

                    content = await file.read()
                    csv_content = content.decode('utf-8-sig')
                    csv_reader = csv.DictReader(io.StringIO(csv_content), delimiter=';')

                    all_urls = []
                    for row in csv_reader:
                        for col in process_columns:
                            if col in row and row[col]:
                                text = row[col]
                                urls = re.findall(r'https://disk\.yandex\.ru/[^\s,"\']+', text)
                                all_urls.extend(urls)

                    # Обрабатываем все URL пакетом
                    if all_urls:
                        request = Request({"type": "http", "headers": []})
                        request._base_url = "/"
                        url_mapping = await process_url_batch(all_urls, session, request)
                        link_replacements.update(url_mapping)
                        file_urls.extend(url_mapping.values())

                elif file.filename.lower().endswith(supported_file_types):
                    unique_id = uuid.uuid4().hex[:8]
                    sanitized_filename = sanitize_filename(file.filename.rsplit('.', 1)[0])
                    file_extension = file.filename.rsplit('.', 1)[1]
                    new_filename = f"{unique_id}-{sanitized_filename}.{file_extension}"

                    content = await file.read()
                    photo_path = os.path.join(PHOTO_DIR, new_filename)
                    async with aiofiles.open(photo_path, 'wb') as photo_file:
                        await photo_file.write(content)

                    file_url = f"/photos/{new_filename}"
                    file_urls.append(file_url)

                elif file.filename.lower().endswith(".txt"):
                    content = (await file.read()).decode("utf-8")
                    urls = re.findall(r"https://disk\.yandex\.ru/[^\s,\"']+", content)

                    if urls:
                        request = Request({"type": "http", "headers": []})
                        request._base_url = "/"
                        url_mapping = await process_url_batch(urls, session, request)
                        link_replacements.update(url_mapping)
                        file_urls.extend(url_mapping.values())

            except Exception as e:
                print(f"Error processing file {file.filename}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing file {file.filename}")

    return JSONResponse(content={"file_urls": file_urls, "link_replacements": link_replacements})

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/photos", StaticFiles(directory=PHOTO_DIR), name="photos")

@app.get("/files/")
async def get_files():
    files = []
    for filename in os.listdir(UPLOAD_DIR):
        file_url = f"/uploads/{filename}"
        files.append({"filename": filename, "url": file_url})
    return JSONResponse(content={"available_files": files})

@app.post("/process_text_file/")
async def process_text_file(request: Request, file: UploadFile = File(...)):
    try:
        logger.info("Starting text file processing")
        if not file.filename.lower().endswith('.txt'):
            raise HTTPException(status_code=400, detail="Only .txt files are supported")

        content = (await file.read()).decode('utf-8')
        urls = re.findall(r'https://disk\.yandex\.ru/[^\s,"\']+', content)
        new_content = content

        if urls:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url_mapping = await process_url_batch(urls, session, request)

                for original_url, new_url in url_mapping.items():
                    new_content = new_content.replace(original_url, new_url)

        output_filename = f"processed_{file.filename}"
        output_path = os.path.join(UPLOAD_DIR, output_filename)

        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(new_content)

        return FileResponse(output_path, filename=output_filename)

    except Exception as e:
        logger.error(f"Error processing text file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download_processed_csv/{filename}")
async def download_processed_csv(filename: str):
    try:
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            return FileResponse(file_path, filename=f"processed_{filename}")
        return {"error": "File not found"}
    except Exception as e:
        logger.error(f"Error downloading CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading file")

@app.post("/process_yandex_url/")
async def process_yandex_url(url: str = Form(...)):
    try:
        logger.info(f"Processing Yandex.Disk URL: {url}")

        if not url.startswith('https://disk.yandex.ru/'):
            raise HTTPException(status_code=400, detail="Invalid Yandex.Disk URL")

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            folder_items = await get_yandex_folder_contents(url, session)

            if folder_items:
                logger.info(f"Found folder with {len(folder_items)} images")
                processed_files = []

                for item in folder_items:
                    try:
                        if item['download_url']:
                            async with session.get(item['download_url']) as response:
                                if response.status == 200:
                                    file_content = await response.read()

                                    unique_id = uuid.uuid4().hex[:8]
                                    original_name = item['name']
                                    if '.' in original_name:
                                        extension = original_name.split('.')[-1].lower()
                                        if extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                                            new_filename = f"{unique_id}.{extension}"
                                        else:
                                            new_filename = f"{unique_id}.jpg"
                                    else:
                                        new_filename = f"{unique_id}.jpg"

                                    photo_path = os.path.join(PHOTO_DIR, new_filename)

                                    async with aiofiles.open(photo_path, 'wb') as photo_file:
                                        await photo_file.write(file_content)

                                    new_url = f"/photos/{new_filename}"
                                    processed_files.append({
                                        "original_name": original_name,
                                        "new_url": new_url,
                                        "filename": new_filename
                                    })

                                    logger.info(f"Downloaded: {original_name} -> {new_filename}")
                    except Exception as e:
                        logger.error(f"Error downloading {item['name']}: {str(e)}")
                        continue

                if processed_files:
                    return JSONResponse(content={
                        "success": True,
                        "type": "folder",
                        "original_url": url,
                        "processed_files": processed_files,
                        "total_files": len(processed_files)
                    })
                else:
                    raise HTTPException(status_code=400, detail="No images could be downloaded from the folder")

            else:
                file_content = await download_yandex_file(url, session)
                if not file_content:
                    raise HTTPException(status_code=400, detail="Failed to download file from Yandex.Disk")

                unique_id = uuid.uuid4().hex[:8]
                new_filename = f"{unique_id}.jpg"
                photo_path = os.path.join(PHOTO_DIR, new_filename)

                async with aiofiles.open(photo_path, 'wb') as photo_file:
                    await photo_file.write(file_content)

                new_url = f"/photos/{new_filename}"

                return JSONResponse(content={
                    "success": True,
                    "type": "file",
                    "original_url": url,
                    "new_url": new_url,
                    "filename": new_filename
                })

    except Exception as e:
        logger.error(f"Error processing Yandex URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process_multiple_text_files/")
async def process_multiple_text_files(request: Request, files: list[UploadFile] = File(...)):
    try:
        logger.info(f"Starting batch text file processing for {len(files)} files")

        for file in files:
            if not (file.filename.lower().endswith('.txt') or file.filename.lower().endswith('.csv')):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a .txt or .csv file")

        if len(files) > MAX_FILES_COUNT:
            raise HTTPException(status_code=400, detail=f"Too many files. Maximum {MAX_FILES_COUNT} files allowed")

        processed_files = []
        timeout = aiohttp.ClientTimeout(total=300)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for file in files:
                try:
                    if file.filename.lower().endswith('.csv'):
                        content = (await file.read()).decode('utf-8-sig')
                        urls = re.findall(r'https://disk\.yandex\.ru/[^\s,"\']+', content)

                        if urls:
                            url_mapping = await process_url_batch(urls, session, request)

                            new_content = content
                            for original_url, new_url in url_mapping.items():
                                new_content = new_content.replace(original_url, new_url)
                        else:
                            new_content = content
                            url_mapping = {}

                    else:
                        content = (await file.read()).decode('utf-8')
                        urls = re.findall(r'https://disk\.yandex\.ru/[^\s,"\']+', content)

                        if urls:
                            url_mapping = await process_url_batch(urls, session, request)
                            processed_urls = list(url_mapping.values())
                            new_content = "///".join(processed_urls)
                        else:
                            new_content = content
                            url_mapping = {}

                    output_filename = f"processed_{file.filename}"
                    output_path = os.path.join(UPLOAD_DIR, output_filename)

                    async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                        await f.write(new_content)

                    processed_files.append({
                        "original_filename": file.filename,
                        "processed_filename": output_filename,
                        "download_url": f"{request.base_url}download_processed_csv/{output_filename}",
                        "urls_processed": len(url_mapping)
                    })

                except Exception as e:
                    logger.error(f"Error processing file {file.filename}: {str(e)}")
                    processed_files.append({
                        "original_filename": file.filename,
                        "error": str(e)
                    })

        return JSONResponse(content={
            "success": True,
            "processed_files": processed_files,
            "total_files": len(files)
        })

    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/")
async def get_stats():
    try:
        photo_count = len([f for f in os.listdir(PHOTO_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])
        upload_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])

        total_size = 0
        for root, dirs, files in os.walk(PHOTO_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)

        return {
            "photo_count": photo_count,
            "upload_count": upload_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "supported_formats": ['.png', '.jpg', '.jpeg', '.gif', '.mp4', '.mov', '.avi', '.mkv', '.zip', '.rar', '.csv', '.txt'],
            "cache_stats": {
                "cached_urls": len(url_cache),
                "cached_folders": len(folder_cache)
            }
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting statistics")

@app.get("/clear_cache/")
async def clear_cache():
    """Очищает кэш URL для освобождения памяти"""
    global url_cache, folder_cache
    cache_size = len(url_cache) + len(folder_cache)
    url_cache.clear()
    folder_cache.clear()
    return {"message": f"Cache cleared. Removed {cache_size} entries."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
