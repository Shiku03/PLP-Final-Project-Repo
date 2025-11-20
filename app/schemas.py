from pydantic import BaseModel,EmailStr

class UserCreate(BaseModel):
    fullname:str
    username:str
    email:EmailStr
    password:str