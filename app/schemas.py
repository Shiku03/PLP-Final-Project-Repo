from pydantic import BaseModel,EmailStr
from typing import Optional
import datetime

#create base user class
class UserBase(BaseModel):
    fullname:str
    username:str
    email:EmailStr
    phone_number:Optional[str]=None

#create user creation class that inherits from base class
class UserCreate(UserBase):
    password:str

#create user output class that inherits from base class
#this will be used when returning user data from the API
class UserOut(UserBase):
    id:int
    role:str
    created_at:datetime.datetime
    updated_at:datetime.datetime

    class Config:
        orm_mode =True

#base document class
class DocumentBase(BaseModel):
    doc_name: str
    file_path: str

#document creation class
class DocumentCreate(DocumentBase):
    user_id: int


#document output class
#will be used when returning document data from the API
class DocumentOut(DocumentBase):
    id: int
    user_id: int
    uploaded_at: datetime.datetime

    class Config:
        orm_mode = True


#base summary class
class SummaryBase(BaseModel):
    summary_text: str

#summary creation class
class SummaryCreate(SummaryBase):
    user_id: int
    document_id: Optional[int] = None

#summary output class
#will be used when returning summary data from the API
class SummaryOut(SummaryBase):
    id: int
    user_id: int
    document_id: Optional[int]
    created_at: datetime.datetime

    class Config:
        orm_mode = True

#base video class
class VideoBase(BaseModel):
    video_name: str
    video_path: str

#video creation class
class VideoCreate(VideoBase):
    user_id: int
    summary_id: Optional[int] = None
    document_id: Optional[int] = None

#video output class
#will be used when returning video data from the API
class VideoOut(VideoBase):
    id: int
    user_id: int
    summary_id: Optional[int]
    document_id: Optional[int]
    generated_at: datetime.datetime

    class Config:
        orm_mode = True

#download creation class
class DownloadCreate(BaseModel):
    user_id: int
    video_id: int

#download output class
#will be used when returning download data from the API
class DownloadOut(BaseModel):
    id: int
    user_id: int
    video_id: int
    download_date: datetime.datetime

    class Config:
        orm_mode = True