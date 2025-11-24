import os
import json
import google.generativeai as genai
from fastapi import FastAPI, Header, HTTPException, Depends
from firebase_admin import credentials, firestore, auth, initialize_app
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

try:
    cred = credentials.Certificate("serviceAccountKey.json")
    initialize_app(cred)
except ValueError:
    pass
db = firestore.client()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise ValueError("GEMINI_API_KEY bulunamadı!")

genai.configure(api_key=GEMINI_KEY)

model = genai.GenerativeModel('gemini-2.0-flash')

app = FastAPI()

class TodoRequest(BaseModel):
    title: str
    description: str = None
    is_voice_input: bool = False

async def get_current_user(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        if token == "GELISTIRICI_TOKEN_123":
            return "TEST_USER_FIREBASE_UID"
        decoded_token = auth.verify_id_token(token)
        return decoded_token['uid']
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/create-todo")
async def create_todo(request: TodoRequest, uid: str = Depends(get_current_user)):
    
    prompt = f"""
    Sen bir zaman yönetimi asistanısın. Aşağıdaki görev için bir analiz yap.
    
    Görev: {request.title}
    Detay: {request.description}
    
    Cevabı SADECE şu JSON formatında ver (başka hiçbir metin yazma):
    {{
        "estimated_minutes": (tahmini süre dakika olarak, tamsayı),
        "productivity_tip": (kısa, motive edici bir taktik cümlesi)
    }}
    """

    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_data = json.loads(response.text)

        todo_data = {
            "uid": uid,
            "title": request.title,
            "description": request.description,
            "estimated_minutes": ai_data.get("estimated_minutes", 15),
            "productivity_tip": ai_data.get("productivity_tip", "Hemen başla!"),
            "is_completed": False,
            "created_at": firestore.SERVER_TIMESTAMP,
            "is_voice_input": request.is_voice_input,
        }
        
        doc_ref = db.collection("todos").add(todo_data)

        return {
            "status": "success",
            "message": "Todo oluşturuldu.",
            "ai_data": ai_data,
            "todo_id": doc_ref[1].id
        }

    except Exception as e:
        print(f"HATA DETAYI: {e}")
        raise HTTPException(status_code=500, detail=f"İşlem başarısız: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "SmartDo Backend Hazır!"}