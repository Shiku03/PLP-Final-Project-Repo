from fastapi import FastAPI, Form, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User, UserRole, Document, Summary, Video, Download
from passlib.context import CryptContext
import os
import shutil
import uuid
from dotenv import load_dotenv
from google import genai
import time
from typing import Optional
from app import schemas
import asyncio
from fastapi import Depends, HTTPException
from pathlib import Path
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from google.genai import types
from app import crud

# initialize
app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
origins=["http://127.0.0.1:5500", "http://localhost:5500"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
       SessionMiddleware,
       secret_key="your_super_secret_key_here",
       same_site="strict",
       https_only=False,
   )

load_dotenv()
GEMINI_API_KEY = os.getenv("GenEd_Gemini_API_KEY")

# dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Routes
# home page
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# dashboard page
@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Signup endpoint
@app.post("/signup")
def signup(
    fullname: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: Optional[str] = Form("user"),
    phone_number: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):

    # validate with pydantic schema
    try:
        user_in = schemas.UserCreate(
            fullname=fullname,
            username=username,
            email=email,
            password=password,
            role=UserRole(role) if role else UserRole.user,
            phone_number=phone_number,
        )
    except Exception as e:
           return JSONResponse(
        status_code=400,
        content={"message": f"Invalid input: {e}"}
    )
    # check if username or email already exists
    if crud.get_user_by_username(db, username=user_in.username):
        return JSONResponse(
            status_code=400,
            content={
                "message": "Username already exists. Redirecting to login page",
                "redirect": "/login"
            }
        )   
    if crud.get_user_by_email(db, email=user_in.email):
        return JSONResponse(
            status_code=400,
            content={
                "message": "Email already exists. Redirecting to login page",
                "redirect": "/login"
            }
        )
    try:
        crud.create_user(db, user_in)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "message": f"Error creating user: {e}",
                "redirect": "/signup"
            }
        )

    return JSONResponse(
    status_code=200,
    content={
        "message": "Signup successful",
        "redirect": "/dashboard"
    }
)

# Login route
@app.post("/login")
def login(request:Request, user: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if "@" in user:
        db_user = crud.get_user_by_username(db, user)
    else:
        db_user = crud.get_user_by_email(db, user)
    
    
    if not db_user:
            
        return JSONResponse(
          status_code=404,
          content={"message": "User not found. Please sign up first", 
            "redirect": "/signup"}
     )
    
    if not crud.verify_password(password, db_user.password):
        return JSONResponse(
        status_code=400,
        content={"message": "Invalid credentials. Please try again", "redirect": "/login"}
    )
    
    request.session["user_id"] = db_user.id  # ← save logged-in user ID

    return JSONResponse(
    status_code=200,
    content={
        "message": "Login successful",
        "redirect": "/dashboard"
    }
    )

@app.post("/change-password")
def change_password(
    username: str = Form(...),                 
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    # 1. Get the user
    db_user = crud.get_user_by_username(db , username)
    if not db_user:
        return JSONResponse(
            status_code=404,
            content={
                "message": "User not found",
                "redirect": "/signup"}
        )

    # 2. Verify old password
    if not crud.verify_password(old_password, db_user.password):
        return JSONResponse(
            status_code=400,
            content={
                "message": "Old password is incorrect"
                }
        )

    # 3. Update password
    db_user.password = crud.hash_password(new_password)
    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "message": "Password changed successfully", 
            "redirect": "/login"
        }
    )
  

# Serve signup/login pages
@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("sign-in.html", {"request": request})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/change-password")
def change_password_page(request: Request):
    return templates.TemplateResponse("change-password.html", {"request": request})

# upload files endpoint and logic

@app.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a file, save it, extract text using Gemini, and store in database
    """
    # Get user_id from session
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={
                "message": "Please login first",
                "redirect": "/login"
            }
        )
    
    # Validate user exists
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return JSONResponse(
            status_code=404,
            content={"message": "User not found"}
        )
    
    # Validate file type
    allowed_extensions = {'.txt', '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        return JSONResponse(
            status_code=400,
            content={"message": f"File type {file_ext} not allowed"}
        )
    
    # Create uploads directory if it doesn't exist
    upload_dir = Path("media/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    unique_filename = f"{user_id}_{int(time.time())}_{file.filename}"
    file_path = upload_dir / unique_filename
    
    # Save file to disk
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to save file: {str(e)}"}
        )
    
    # Extract text using Gemini API
    extracted_text = ""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Read file bytes
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()
        
        # Upload to Gemini
        uploaded = client.files.upload(
            file=file_bytes,
            file_name=file.filename
        )
        
        # Extract text
        extract_prompt = "Extract all text from the uploaded file and return it as plain text without any formatting or markdown."
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[extract_prompt, uploaded]
        )
        
        extracted_text = response.text if hasattr(response, 'text') else ""
        
    except Exception as e:
        # If extraction fails, still save the document but with empty text
        print(f"Text extraction failed: {e}")
        extracted_text = f"[Text extraction failed: {str(e)}]"
    
    # Save document to database
    try:
        document = Document(
            user_id=user_id,
            doc_name=file.filename,
            file_path=str(file_path),
            extracted_text=extracted_text
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "File uploaded and text extracted successfully",
                "document_id": document.id,
                "filename": file.filename,
                "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
                "text_length": len(extracted_text)
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to save to database: {str(e)}"}
        )








# generate video from summary / document / raw text
@app.post("/generate-video", response_model=schemas.VideoOut)
async def generate_video(
    user_id: int = Form(...),
    summary_id: Optional[int] = Form(None),
    document_id: Optional[int] = Form(None),
    raw_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # validate user
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # determine text source
    source_text = ""
    used_summary_id = summary_id

    if summary_id:
        summary = db.query(Summary).filter(Summary.id == summary_id).first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        source_text = summary.summary_text

    elif raw_text:
        source_text = raw_text

    elif document_id:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        # read file and ask model to extract text
        try:
            with open(doc.file_path, "rb") as fh:
                file_bytes = fh.read()
            uploaded = client.files.upload(file=file_bytes, file_name=os.path.basename(doc.file_path))
            extract_prompt = "Extract all text from the uploaded file and return a single block of text."
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[extract_prompt],
                files=[uploaded] if hasattr(uploaded, "id") else None
            )
            source_text = getattr(resp, "text", None) or getattr(resp, "content", None) or ""
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to extract text from document: {e}")

    if not source_text:
        raise HTTPException(status_code=400, detail="No source text provided for video generation")

    # if there is no pre-existing summary, create a concise summary to base the video on
    if not summary_id:
        try:
            summary_prompt = "Summarize the following text into a concise paragraph:\n\n" + source_text
            sum_resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[summary_prompt]
            )
            summary_text = getattr(sum_resp, "text", None) or getattr(sum_resp, "content", None) or source_text[:200]
        except Exception:
            summary_text = source_text[:200]

        summary = Summary(user_id=user_id, document_id=document_id if document_id else None, summary_text=summary_text)
        db.add(summary)
        db.commit()
        db.refresh(summary)
        used_summary_id = summary.id
    else:
        summary_text = source_text

    # generate video from the summary_text
    media_dir = Path("media/videos")
    media_dir.mkdir(parents=True, exist_ok=True)
    video_name = f"video_{user_id}_{int(time.time())}.mp4"
    output_path = media_dir / video_name

    try:
        operation = client.models.generate_video(
            model="veo-2.0-generate-001",
            prompt=summary_text,
            output_file_name=video_name,
            config={"aspectRatio": "16:9", "durationSeconds": 6}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video generation request failed: {e}")

    # poll operation (async)
    max_wait = 60 * 5
    waited = 0
    interval = 5
    while not getattr(operation, "done", False) and waited < max_wait:
        await asyncio.sleep(interval)
        waited += interval
        try:
            operation = client.operations.get(getattr(operation, "name", operation))
        except Exception:
            break

    if not getattr(operation, "done", False):
        raise HTTPException(status_code=500, detail="Video generation did not complete in time")

    try:
        gen_vid = operation.response.generated_videos[0]
    except Exception:
        raise HTTPException(status_code=500, detail="No generated video returned by the operation")

    # download video bytes (SDK dependent)
    video_bytes = None
    try:
        if hasattr(gen_vid, "file_id"):
            downloaded = client.files.download(file=gen_vid.file_id)
            video_bytes = getattr(downloaded, "content", None) or getattr(downloaded, "data", None)
        elif hasattr(gen_vid, "video") and hasattr(gen_vid.video, "content"):
            video_bytes = gen_vid.video.content
    except Exception:
        video_bytes = None

    if not video_bytes:
        raise HTTPException(status_code=500, detail="Failed to download generated video")

    with open(output_path, "wb") as f:
        f.write(video_bytes)

    video = Video(
        user_id=user_id,
        document_id=document_id if document_id else None,
        summary_id=used_summary_id,
        video_name=video_name,
        video_path=str(output_path),
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    return schemas.VideoOut.from_orm(video)


# endpoint to record download and return file
@app.get("/download-video/{video_id}")
def download_video(video_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # optional user validation
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    # create download record if user provided (or skip but best to record if user present)
    if user_id:
        download = Download(user_id=user_id, video_id=video_id)
        db.add(download)
        db.commit()

    if not Path(video.video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found on server")

    return FileResponse(path=video.video_path, media_type="application/octet-stream", filename=video.video_name)






