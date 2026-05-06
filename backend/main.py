from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 允许跨域
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()   # 来自 database.py

@app.post("/process")
async def process_complaint(
    text: str = Form(...),
    image: UploadFile = File(None)
):
    """
    接收文本和可选图片/视频，返回标准工单 JSON。
    实现步骤：
        1. 若有图片，读取字节，调用 extract_text_from_image 得到 ocr_text
        2. 调用 call_llm(user_text=text, ocr_text=ocr_text) 得到 llm_result
        3. 调用 get_sop_guide(issue_category, urgency_level) 得到 sop_extra
        4. 拼接最终回复 auto_reply = llm_result["reply"] + "\n" + sop_extra
        5. 若有 sn_code，调用 check_warranty(sn_code) 得到保修状态
        6. 组装 ticket dict，调用 save_ticket(ticket)
        7. 返回 ticket JSON
    """
    # TODO: 实现上述流程，异常处理返回 500
    pass

@app.get("/history")
async def history():
    """返回所有历史工单"""
    tickets = get_all_tickets()
    return {"tickets": tickets}

@app.get("/health")
async def health():
    return {"status": "ok"}