from fastapi import FastAPI,Form,Depends,HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal,engine,Base
from models import User
from schemas import UserCreate
from passlib.context import CryptContext
import httpx
from fastapi import Request, UploadFile, File
import os
from dotenv import load_dotenv
from google import genai

#initialize
app=FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)
pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto")

load_dotenv()
GEMINI_API_KEY=os.getenv("GenEd_Gemini_API_KEY")

#dependency to get the DB session
def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

#hash password
def hash_password(password:str):
    return pwd_context.hash(password)

# Password verification
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


#Routes
#home page
@app.get("/")
def index(request:Request):
    return templates.TemplateResponse("index.html", {"request":request})

#dashboard
@app.get("/dashboard")
def dashboard_page(request:Request):
    return templates.TemplateResponse("dashboard.html",{"request": request})

#Signup endpoint
@app.post("/signup")
def signup(fullname:str=Form(...),username:str=Form(...),email:str=Form(...),password:str=Form(...),db:Session=Depends(get_db)):
    #check if username or email already exists
    if db.query(User).filter(User.username==username).first():
        raise HTTPException(status_code=400, details="Username already exists")
    user= User(username=username, email=email, password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return{"message":"User created successfully", "user Id": user.id}

#login route
# Login route
@app.post("/login")
def login(user: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if "@" in user:
        db_user = db.query(User).filter(User.email == user).first()
    else:
        db_user = db.query(User).filter(User.username == user).first()
    
    if not db_user or not verify_password(password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    return RedirectResponse(url="/dashboard", status_code=303)

# Serve signup/login pages
@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("sign-in.html", {"request": request})

@app.get("/login")
def signup_page(request: Request):
    return templates.TemplateResponse("sign-in.html", {"request": request})


# Dashboard page
@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


#upload files endpoint and logic
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content_bytes = await file.read()


    #forward to Gemini for text extraction
    client=genai.Client(api_key=GEMINI_API_KEY)

    uploaded_file=client.files.upload(file=content_bytes, file_name=file.filename)

    prompt="Extract all the text from the uploaded file and return it as a single block of text,adding paragraphs where necessary"

    response=client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[uploaded_file,prompt]
    )

    extracted_text=response.text

    return{
        "filename": file.filename,
        "extracted_text": extracted_text
    }







