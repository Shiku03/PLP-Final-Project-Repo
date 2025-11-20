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

#initialize
app=FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)
pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto")
EXTERNAL_AI_URL=""
API_KEY=""

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
    content = await file.read()
    #read incoming file
    file_bytes= await file.read

    #forward to external AI
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            EXTERNAL_AI_URL, headers={
                "Authorization": f"Bearer {API_KEY}",
                },
                files={"file": (file.filename, file_bytes, file.content_type)},
        )
        return {
            "status_code": "forwarded",
            "external_ai_response": response.json(),
        }
    if response.status_code !=200:
        raise HTTPException(status_code=500, detail="Error processing file with external AI service")
    return response.json()


