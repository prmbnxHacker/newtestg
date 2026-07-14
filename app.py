import os
import random
import re
import fitz
import shutil
import hashlib
import uuid
import gc
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from supabase import create_client, Client

# ==================== CONFIG ====================
SUPABASE_URL = "https://xfjurdncpizltrierozw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhmanVyZG5jcGl6bHRyaWVyb3p3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Mjk5MjE0OCwiZXhwIjoyMDk4NTY4MTQ4fQ.xP1ZRgLIJLi7OQE5l0RoovJ6wZvFQ_Z5EVrM__Ujdtg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="toolscraft-hub-super-secret-key-xyz-2026")

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
TEMPLATE_FILE = "template.pdf"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==================== HELPER FUNCTIONS ====================
def get_bdt_date():
    return (datetime.utcnow() + timedelta(hours=6)).strftime("%Y-%m-%d")

def get_bdt_time():
    return (datetime.utcnow() + timedelta(hours=6)).strftime("%Y-%m-%d %I:%M %p")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_active_session(request: Request):
    username = request.session.get("username")
    token = request.session.get("session_token")
    if not username or not token:
        return False
    try:
        res = supabase.table("users").select("session_token").eq("username", username).execute()
        if res.data and res.data[0].get("session_token") == token:
            return True
    except:
        pass
    return False

def check_and_reset_credits(username):
    try:
        res = supabase.table("users").select("daily_credits").eq("username", username).execute()
        if res.data:
            return res.data[0].get("daily_credits", 0)
    except:
        pass
    return 0

# ==================== IMPROVED PROCESS MASTER PDF ====================
def process_master_pdf(user_pdf_path, output_path, original_filename, ai_percentage, shared_id):
    user_doc = fitz.open(user_pdf_path)
    if len(user_doc) > 0:
        user_doc.delete_page(0)

    actual_pages_count, actual_words, actual_chars = len(user_doc), 0, 0
    for p in user_doc:
        body_rect = fitz.Rect(0, 38, p.rect.width, p.rect.height - 38)
        text = p.get_text("text", clip=body_rect)
        actual_words += len(text.split())
        actual_chars += len(text)

    new_size = f"{os.path.getsize(user_pdf_path) / 1024:.1f} KB"
    new_id = shared_id
    base_name = re.sub(r'(?i)ai\s*report', '', os.path.splitext(original_filename)[0].replace("_", " ")).strip()
    new_title = " ".join(base_name.split()[:5]) if base_name.split() else "Document"

    now = datetime.utcnow() + timedelta(hours=6)
    sub_time = now - timedelta(minutes=2)
    sub_date_str = sub_time.strftime(f"%b {sub_time.day}, %Y, {sub_time.strftime('%I').lstrip('0')}:%M %p GMT+6")
    down_date_str = now.strftime(f"%b {now.day}, %Y, {now.strftime('%I').lstrip('0')}:%M %p GMT+6")

    template_doc = fitz.open(TEMPLATE_FILE)
    page1 = template_doc[0]
    base_dir = os.path.dirname(os.path.abspath(__file__))

    notosans_path = os.path.join(base_dir, "static", "NotoSans-Regular.ttf")
    notosans_sb_path = os.path.join(base_dir, "static", "NotoSans-SemiBold.ttf")
    lexend_path = os.path.join(base_dir, "static", "LexendDeca-Medium.ttf")

    font_noto = None
    font_noto_sb = None
    font_lexend = None

    if os.path.exists(notosans_path):
        try:
            font_noto = page1.insert_font(fontname="notosans", fontfile=notosans_path)
        except:
            font_noto = None

    if os.path.exists(notosans_sb_path):
        try:
            font_noto_sb = page1.insert_font(fontname="notosans_sb", fontfile=notosans_sb_path)
        except:
            font_noto_sb = None

    if os.path.exists(lexend_path) and len(template_doc) > 1:
        try:
            page2 = template_doc[1]
            font_lexend = page2.insert_font(fontname="lexend", fontfile=lexend_path)
        except:
            font_lexend = None

    # Page 1 replacements
    page1_text = page1.get_text()

    replacements = {
        re.search(r"trn:oid:::\d:\d+", page1_text).group(0) if re.search(r"trn:oid:::\d:\d+", page1_text) else None: new_id,
    }

    for old_txt, new_txt in replacements.items():
        if not old_txt: continue
        for inst in page1.search_for(old_txt):
            page1.add_redact_annot(inst, fill=(1, 1, 1))
            page1.apply_redactions()
            page1.insert_text((inst.x0, inst.y1 - 1), str(new_txt), fontsize=9.5, fontname="helv", color=(0, 0, 0))

    # Labib Hasan
    for inst in page1.search_for("Aa Aa"):
        page1.add_redact_annot(fitz.Rect(inst.x0 - 2, inst.y0 - 2, inst.x1 + 10, inst.y1 + 2), fill=(1, 1, 1))
        page1.apply_redactions()
        if font_noto_sb:
            page1.insert_text((inst.x0, inst.y1), "Labib Hasan", fontsize=20, fontname="notosans_sb", color=(0, 0, 0))
        else:
            page1.insert_text((inst.x0, inst.y1), "Labib Hasan", fontsize=20, fontname="helv", color=(0, 0, 0))

    # Page 2
    if len(template_doc) > 1:
        page2 = template_doc[1]
        for inst in page2.search_for("58% detected as AI"):
            page2.add_redact_annot(fitz.Rect(inst.x0, inst.y0 - 2, inst.x1 + 5, inst.y1 - 4), fill=(1, 1, 1))
            page2.apply_redactions()
            if font_lexend:
                page2.insert_text((inst.x0, inst.y1 - 4), f"{ai_percentage}% detected as AI", fontsize=16.5, fontname="lexend", color=(0, 0, 0))
            else:
                page2.insert_text((inst.x0, inst.y1 - 4), f"{ai_percentage}% detected as AI", fontsize=17, fontname="helv", color=(0, 0, 0))

    template_doc.insert_pdf(user_doc)

    logo_path = os.path.join(base_dir, "static", "logo.png")

    for i, page in enumerate(template_doc):
        rect = page.rect
        header_text = f"Page {i + 1} of {len(template_doc)} - {'Cover Page' if i == 0 else 'AI Writing Overview' if i == 1 else 'AI Writing Submission'}"

        page.clean_contents()
        page.add_redact_annot(fitz.Rect(0, 0, rect.width, 50), fill=(1, 1, 1))
        page.add_redact_annot(fitz.Rect(0, rect.height - 50, rect.width, rect.height), fill=(1, 1, 1))
        page.apply_redactions()

        if os.path.exists(logo_path):
            page.insert_image(fitz.Rect(20, 15, 90, 35), filename=logo_path)
            page.insert_image(fitz.Rect(20, rect.height - 35, 90, rect.height - 15), filename=logo_path)

        page.insert_text(fitz.Point(110, 30), header_text, fontsize=7, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(rect.width - 200, 30), f"Submission ID {new_id}", fontsize=7, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(110, rect.height - 20), header_text, fontsize=7, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(rect.width - 200, rect.height - 20), f"Submission ID {new_id}", fontsize=7, fontname="helv", color=(0, 0, 0))

    template_doc.save(output_path, deflate=True, garbage=4)
    template_doc.close()
    user_doc.close()
    gc.collect()


def apply_header_and_footer(input_pdf_path, output_path, shared_id):
    doc = fitz.open(input_pdf_path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "static", "logo.png")

    for i, page in enumerate(doc):
        rect = page.rect
        header_text = f"Page {i + 1} of {len(doc)} - Integrity Submission"
        if os.path.exists(logo_path):
            page.insert_image(fitz.Rect(20, 15, 90, 35), filename=logo_path)
            page.insert_image(fitz.Rect(20, rect.height - 35, 90, rect.height - 15), filename=logo_path)
        page.insert_text(fitz.Point(110, 30), header_text, fontsize=7, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(rect.width - 200, 30), f"Submission ID {shared_id}", fontsize=7, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(110, rect.height - 20), header_text, fontsize=7, fontname="helv", color=(0, 0, 0))
        page.insert_text(fitz.Point(rect.width - 200, rect.height - 20), f"Submission ID {shared_id}", fontsize=7, fontname="helv", color=(0, 0, 0))

    doc.save(output_path)
    doc.close()


# ==================== ROUTES ====================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": None})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        res = supabase.table("users").select("role").eq("username", username).eq("password", hash_password(password)).execute()
        if res.data:
            role = res.data[0]['role']
            token = str(uuid.uuid4())
            supabase.table("users").update({"session_token": token}).eq("username", username).execute()
            request.session.update({"username": username, "role": role, "session_token": token})
            return RedirectResponse(url="/", status_code=303)
        return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "ভুল ইউজারনেম বা পাসওয়ার্ড!"})
    except Exception as e:
        return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": f"সিস্টেম এরর: {str(e)}"})

@app.get("/logout")
async def logout(request: Request):
    username = request.session.get("username")
    if username:
        try:
            supabase.table("users").update({"session_token": None}).eq("username", username).execute()
        except:
            pass
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not check_active_session(request):
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
    username = request.session.get("username")
    role = request.session.get("role")
    credits = check_and_reset_credits(username)
    user_files = []
    try:
        res = supabase.table("file_history").select("id, filename, processed_date").eq("username", username).order("id", desc=True).limit(10).execute()
        if res.data:
            user_files = [(f['id'], f['filename'], f['processed_date']) for f in res.data]
    except:
        pass
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "username": username, "role": role, "credits": credits, "user_files": user_files})

@app.post("/upload")
async def upload_file(request: Request, file_ai: UploadFile = File(...), file_sim: UploadFile = File(...), ai_percentage: str = Form(...)):
    if not check_active_session(request):
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    username = request.session.get("username")
    credits = check_and_reset_credits(username)
    if credits <= 0:
        return HTMLResponse(content="<h3>আপনার আজকের ক্রেডিট শেষ!</h3><br><a href='/'>Back</a>", status_code=403)

    try:
        unique_id = str(uuid.uuid4())[:8]
        saved_ai_filename = f"{unique_id}_AI_{file_ai.filename}"
        input_ai_path = os.path.join(UPLOAD_DIR, saved_ai_filename)
        with open(input_ai_path, "wb") as buffer:
            shutil.copyfileobj(file_ai.file, buffer)

        saved_sim_filename = f"{unique_id}_SIM_{file_sim.filename}"
        input_sim_path = os.path.join(UPLOAD_DIR, saved_sim_filename)
        with open(input_sim_path, "wb") as buffer:
            shutil.copyfileobj(file_sim.file, buffer)

        output_report_path = os.path.join(OUTPUT_DIR, f"Report_{saved_ai_filename}")
        output_edited_path = os.path.join(OUTPUT_DIR, f"Edited_{saved_sim_filename}")
        shared_submission_id = f"trn:oid:::1:{random.randint(1000000000, 9999999999)}"

        process_master_pdf(input_ai_path, output_report_path, file_ai.filename, ai_percentage, shared_submission_id)
        apply_header_and_footer(input_sim_path, output_edited_path, shared_submission_id)

        res_u = supabase.table("users").select("used_credits").eq("username", username).execute()
        current_used = res_u.data[0].get("used_credits", 0) if res_u.data and res_u.data[0].get("used_credits") is not None else 0

        if credits < 900000:
            supabase.table("users").update({"daily_credits": credits - 1, "used_credits": current_used + 1}).eq("username", username).execute()
        else:
            supabase.table("users").update({"used_credits": current_used + 1}).eq("username", username).execute()

        current_time = get_bdt_time()
        supabase.table("file_history").insert([
            {"username": username, "filename": f"Report_{saved_ai_filename}", "processed_date": current_time},
            {"username": username, "filename": f"Edited_{saved_sim_filename}", "processed_date": current_time}
        ]).execute()

        supabase.table("credit_logs").insert({"username": username, "usage_date": get_bdt_date()}).execute()
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        return HTMLResponse(content=f"<h3>Error: {str(e)}</h3>", status_code=500)

@app.get("/download_past_file/{file_id}")
async def download_past_file(request: Request, file_id: int, background_tasks: BackgroundTasks):
    if not check_active_session(request):
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
    
    username = request.session.get("username")
    try:
        res = supabase.table("file_history").select("filename").eq("id", file_id).eq("username", username).execute()
        if res.data:
            saved_filename = res.data[0]['filename']
            output_path = os.path.join(OUTPUT_DIR, saved_filename)
            upload_filename = saved_filename.replace("Report_", "", 1) if saved_filename.startswith("Report_") else saved_filename.replace("Edited_", "", 1)
            
            if os.path.exists(output_path):
                background_tasks.add_task(delete_file_and_history, file_id, output_path, upload_filename)
                return FileResponse(output_path, media_type="application/pdf", filename=saved_filename[9:])
    except Exception as e:
        print(e)
        
    return HTMLResponse("<h3>ফাইলটি সার্ভারে পাওয়া যায়নি বা ইতিমধ্যে ডিলিট হয়ে গেছে!</h3><br><a href='/'>হোমে ফিরে যান</a>", status_code=404)

def delete_file_and_history(file_id: int, output_path: str, upload_filename: str):
    time.sleep(30)
    try:
        if os.path.exists(output_path): os.remove(output_path)
        in_path = os.path.join(UPLOAD_DIR, upload_filename)
        if os.path.exists(in_path): os.remove(in_path)
        supabase.table("file_history").delete().eq("id", file_id).execute()
    except Exception as e:
        print("Delete error:", e)

@app.post("/delete_my_file")
async def delete_my_file(request: Request, file_id: int = Form(...)):
    if not check_active_session(request):
        return RedirectResponse(url="/login", status_code=303)
    username = request.session.get("username")
    try:
        res = supabase.table("file_history").select("filename").eq("id", file_id).eq("username", username).execute()
        if res.data:
            saved_filename = res.data[0]['filename']
            out_path = os.path.join(OUTPUT_DIR, saved_filename)
            upload_filename = saved_filename.replace("Report_", "", 1) if saved_filename.startswith("Report_") else saved_filename.replace("Edited_", "", 1)
            in_path = os.path.join(UPLOAD_DIR, upload_filename)
            if os.path.exists(in_path): os.remove(in_path)
            if os.path.exists(out_path): os.remove(out_path)
            supabase.table("file_history").delete().eq("id", file_id).execute()
    except:
        pass
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete_all_files")
async def delete_all_files(request: Request):
    if not check_active_session(request):
        return RedirectResponse(url="/login", status_code=303)
    try:
        supabase.table("file_history").delete().eq("username", request.session.get("username")).execute()
    except:
        pass
    return RedirectResponse(url="/", status_code=303)

# ==================== ADMIN ROUTES ====================
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not check_active_session(request) or request.session.get("role") != "admin":
        return HTMLResponse("Access Denied", status_code=403)
    
    users, history, daily_usage_list = [], [], []
    today = get_bdt_date()
    
    try:
        users_res = supabase.table("users").select("username, role, daily_credits, used_credits").execute()
        if users_res.data:
            for u in users_res.data:
                uname = u['username']
                logs_today = supabase.table("credit_logs").select("id").eq("username", uname).eq("usage_date", today).execute()
                used_today = len(logs_today.data) if logs_today.data else 0
                total_used = u.get('used_credits', 0) if u.get('used_credits') is not None else 0
                users.append((uname, u['role'], u['daily_credits'], used_today, total_used))

        hist_res = supabase.table("file_history").select("username, filename, processed_date").order("id", desc=True).limit(50).execute()
        if hist_res.data:
            history = [(h['username'], h['filename'], h['processed_date']) for h in hist_res.data]
                
        five_days_ago = (datetime.utcnow() + timedelta(hours=6) - timedelta(days=5)).strftime("%Y-%m-%d")
        supabase.table("credit_logs").delete().lt("usage_date", five_days_ago).execute()
        
        usage_res = supabase.table("credit_logs").select("username, usage_date").execute()
        if usage_res.data:
            usage_dict = {}
            for row in usage_res.data:
                key = (row['username'], row['usage_date'])
                usage_dict[key] = usage_dict.get(key, 0) + 1
            daily_usage_list = sorted([{"username": u, "date": d, "used": count} for (u, d), count in usage_dict.items()], key=lambda x: x['date'], reverse=True)
            
    except:
        pass
    
    total_files = len(os.listdir(UPLOAD_DIR)) + len(os.listdir(OUTPUT_DIR))
    return templates.TemplateResponse(request=request, name="admin.html", context={"request": request, "users": users, "history": history, "total_files": total_files, "daily_usage": daily_usage_list})

@app.post("/admin/create_user")
async def create_user(request: Request, new_username: str = Form(...), new_password: str = Form(...), initial_credits: int = Form(5)):
    if not check_active_session(request) or request.session.get("role") != "admin":
        return HTMLResponse("Access Denied", status_code=403)
    try:
        supabase.table("users").insert({
            "username": new_username, 
            "password": hash_password(new_password), 
            "role": "user", 
            "daily_credits": initial_credits, 
            "credit_limit": initial_credits, 
            "used_credits": 0, 
            "last_reset_date": get_bdt_date()
        }).execute()
    except:
        pass
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/update_credits")
async def update_credits(request: Request, up_username: str = Form(...), new_credits: int = Form(...)):
    if not check_active_session(request) or request.session.get("role") != "admin":
        return HTMLResponse("Access Denied", status_code=403)
    try:
        supabase.table("users").update({
            "daily_credits": int(new_credits), 
            "credit_limit": int(new_credits)
        }).eq("username", up_username).execute()
    except:
        pass
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/reset_used_credits")
async def reset_used_credits(request: Request, rst_username: str = Form(...)):
    if not check_active_session(request) or request.session.get("role") != "admin":
        return HTMLResponse("Access Denied", status_code=403)
    try:
        supabase.table("users").update({"used_credits": 0}).eq("username", rst_username).execute()
    except:
        pass
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/delete_user")
async def delete_user(request: Request, del_username: str = Form(...)):
    if not check_active_session(request) or request.session.get("role") != "admin":
        return HTMLResponse("Access Denied", status_code=403)
    if del_username == "admin":
        return HTMLResponse("Admin account cannot be deleted!", status_code=400)
    try:
        supabase.table("users").delete().eq("username", del_username).execute()
    except:
        pass
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/clear_all_files")
async def clear_all_files(request: Request):
    if not check_active_session(request) or request.session.get("role") != "admin":
        return HTMLResponse("Access Denied", status_code=403)
    for folder in [UPLOAD_DIR, OUTPUT_DIR]:
        for f in os.listdir(folder):
            if os.path.isfile(os.path.join(folder, f)):
                os.remove(os.path.join(folder, f))
    try:
        supabase.table("file_history").delete().neq("id", 0).execute()
    except:
        pass
    return RedirectResponse(url="/admin", status_code=303)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
