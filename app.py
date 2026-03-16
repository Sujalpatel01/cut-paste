from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import io
import gc
import os
from PIL import Image, ImageFilter

# Set U2NET_HOME to /tmp for serverless environments (like Vercel) which have read-only file systems
os.environ["U2NET_HOME"] = "/tmp"

try:
    from rembg import remove, new_session
except ImportError:
    print("Please install dependencies: pip install rembg pillow fastapi uvicorn python-multipart")

app = FastAPI(title="CutPaste Web API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy loading session to avoid Vercel deployment timeouts during build/cold-start
sess = None

def get_session():
    global sess
    if sess is None:
        try:
            print("Loading u2net model...")
            sess = new_session("u2net")
        except Exception as e:
            print(f"Failed to load model: {e}")
    return sess

@app.post("/api/remove-bg")
async def remove_background(file: UploadFile = File(...)):
    session = get_session()
    if session is None:
        return Response(content="Model not loaded or rembg is not installed", status_code=500)
    
    data = await file.read()
    orig = Image.open(io.BytesIO(data)).convert("RGBA")
    W, H = orig.size

    # Remove background with alpha matting and post processing (same as original script)
    out_bytes = remove(
        data, session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=270,
        alpha_matting_background_threshold=20,
        alpha_matting_erode_size=11,
        post_process_mask=True,
    )

    res = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
    rW, rH = res.size

    # Preserve original resolution with clean edges
    if (rW, rH) != (W, H):
        _,_,_,alpha = res.split()
        lanczos = getattr(Image, "Resampling", Image).LANCZOS
        alpha = alpha.resize((W,H), lanczos)
        alpha = alpha.filter(ImageFilter.SMOOTH_MORE)
        alpha = alpha.filter(ImageFilter.MaxFilter(3))
        alpha = alpha.filter(ImageFilter.MinFilter(3))
        alpha = alpha.filter(ImageFilter.SMOOTH)
        r,g,b,_ = orig.split()
        res = Image.merge("RGBA", (r,g,b,alpha))

    img_byte_arr = io.BytesIO()
    res.save(img_byte_arr, format='PNG', compress_level=1)
    img_byte_arr.seek(0)
    
    del orig, res, data, out_bytes
    gc.collect()

    return Response(content=img_byte_arr.getvalue(), media_type="image/png")

# Mount the static site at the root level
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
