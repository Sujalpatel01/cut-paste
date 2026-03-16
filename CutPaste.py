"""
CutPaste — Perfect HD Background Remover
==========================================
INSTALL (one time):
    pip install rembg[gpu] pillow PyQt5

OR (no GPU):
    pip install rembg pillow PyQt5

RUN:
    python CutPaste.py
"""
import sys, os, gc, traceback
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QColor, QPalette
from PIL import Image, ImageFilter
import io

class Worker(QThread):
    prog  = pyqtSignal(int, str)
    done  = pyqtSignal(str, int, int)
    error = pyqtSignal(str)

    def __init__(self, inp, out):
        super().__init__()
        self.inp = inp
        self.out = out

    def run(self):
        try:
            from rembg import remove, new_session
            self.prog.emit(10, "AI model load...")
            sess = new_session("u2net")          # best quality model
            self.prog.emit(25, "Image read...")
            data = open(self.inp,'rb').read()
            orig = Image.open(io.BytesIO(data)).convert("RGBA")
            W, H = orig.size
            self.prog.emit(40, f"AI processing {W}×{H}...")

            out_bytes = remove(
                data, session=sess,
                alpha_matting=True,
                alpha_matting_foreground_threshold=270,
                alpha_matting_background_threshold=20,
                alpha_matting_erode_size=11,
                post_process_mask=True,          # extra cleanup pass
            )

            self.prog.emit(78, "HD mask apply...")
            res = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
            rW, rH = res.size

            if (rW,rH) != (W,H):
                _,_,_,alpha = res.split()
                alpha = alpha.resize((W,H), Image.LANCZOS)
                alpha = alpha.filter(ImageFilter.SMOOTH_MORE)
                # extra cleanup: remove tiny dark blobs
                alpha = alpha.filter(ImageFilter.MaxFilter(3))
                alpha = alpha.filter(ImageFilter.MinFilter(3))
                alpha = alpha.filter(ImageFilter.SMOOTH)
                r,g,b,_ = orig.split()
                res = Image.merge("RGBA",(r,g,b,alpha))

            self.prog.emit(92, "Save HD PNG...")
            res.save(self.out, "PNG", compress_level=1)
            del orig, res, data, out_bytes; gc.collect()
            self.prog.emit(100, "Done!")
            self.done.emit(self.out, W, H)
        except ImportError:
            self.error.emit("rembg install નથી!\n\npip install rembg pillow PyQt5")
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class ImgLabel(QLabel):
    dropped = pyqtSignal(str)
    def __init__(self, ph):
        super().__init__(ph)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self._p = None
    def setImg(self, path):
        self._p = QPixmap(path)
        self._sc()
    def clearImg(self, ph=""):
        self._p = None; self.setPixmap(QPixmap()); self.setText(ph)
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._p: self._sc()
    def _sc(self):
        self.setPixmap(self._p.scaled(self.width()-16, self.height()-16,
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.accept()
        else: e.ignore()
    def dropEvent(self, e):
        p = e.mimeData().urls()[0].toLocalFile()
        if p.lower().endswith(('.jpg','.jpeg','.png','.webp','.bmp','.tiff')):
            self.dropped.emit(p)


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.inp = self.out = self.worker = None
        self._ui()

    def _ui(self):
        self.setWindowTitle("✂  CutPaste — Perfect Background Remover")
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(CSS)
        root = QWidget(); root.setObjectName("root")
        self.setCentralWidget(root)
        vl = QVBoxLayout(root)
        vl.setContentsMargins(24,22,24,22); vl.setSpacing(14)

        t = QLabel("✂  CutPaste — Perfect HD Background Remover")
        t.setObjectName("title"); t.setAlignment(Qt.AlignCenter); vl.addWidget(t)
        s = QLabel("rembg u2net  ·  Alpha Matting  ·  Edge Cleanup  ·  Same Resolution  ·  No API Key")
        s.setObjectName("sub"); s.setAlignment(Qt.AlignCenter); vl.addWidget(s)

        row = QHBoxLayout(); row.setSpacing(16)
        lv = QVBoxLayout(); lv.setSpacing(5)
        lv.addWidget(self._lbl("ORIGINAL"))
        self.orig = ImgLabel("📂  Photo drop કરો\nઅથવા Upload button")
        self.orig.setObjectName("prev"); self.orig.setMinimumSize(400,340)
        self.orig.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.orig.dropped.connect(self._load)
        lv.addWidget(self.orig,1); row.addLayout(lv)

        rv = QVBoxLayout(); rv.setSpacing(5)
        rv.addWidget(self._lbl("RESULT — SAME RESOLUTION"))
        self.res = ImgLabel("✨  Perfect result\nઅહીં આવશે")
        self.res.setObjectName("prev_r"); self.res.setMinimumSize(400,340)
        self.res.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        rv.addWidget(self.res,1); row.addLayout(rv)
        vl.addLayout(row,1)

        self.pbar = QProgressBar(); self.pbar.setObjectName("pbar")
        self.pbar.setRange(0,100); self.pbar.setValue(0)
        self.pbar.setTextVisible(False); self.pbar.setFixedHeight(7)
        vl.addWidget(self.pbar)

        self.status = QLabel("Photo upload કરો — 100% perfect background remove")
        self.status.setObjectName("status"); self.status.setAlignment(Qt.AlignCenter)
        vl.addWidget(self.status)

        br = QHBoxLayout(); br.setSpacing(10)
        self.bUp  = self._btn("📂  Upload",        "#1d4ed8", self.upload)
        self.bRun = self._btn("✂️  Remove BG",     "#0f766e", self.process)
        self.bSav = self._btn("💾  Save HD PNG",    "#15803d", self.save)
        self.bClr = self._btn("🗑  Clear",          "#374151", self.clear)
        self.bRun.setEnabled(False); self.bSav.setEnabled(False)
        for b in (self.bUp,self.bRun,self.bSav,self.bClr): br.addWidget(b)
        vl.addLayout(br)

    def _lbl(self,t):
        l=QLabel(t); l.setObjectName("ptitle"); return l

    def _btn(self,t,c,s):
        b=QPushButton(t); b.setFixedHeight(46)
        b.setStyleSheet(f"QPushButton{{background:{c};color:white;border:none;border-radius:11px;font-size:13px;font-weight:700;padding:0 16px}}"
                        f"QPushButton:hover{{background:{c}cc}}QPushButton:pressed{{background:{c}99}}"
                        f"QPushButton:disabled{{background:#1a2235;color:#2d3748}}")
        b.clicked.connect(s); return b

    def _load(self, path):
        self.inp=path; self.out=None
        self.orig.setImg(path)
        self.res.clearImg("✨  Perfect result\nઅહીં આવશે")
        self.bRun.setEnabled(True); self.bSav.setEnabled(False)
        self.pbar.setValue(0)
        img=Image.open(path); W,H=img.size
        mb=os.path.getsize(path)/1024/1024
        self.status.setText(f"Loaded: {os.path.basename(path)}  ·  {W}×{H} px  ·  {mb:.1f} MB")

    def upload(self):
        p,_=QFileDialog.getOpenFileName(self,"Photo Select","","Images (*.jpg *.jpeg *.png *.webp *.bmp *.tiff)")
        if p: self._load(p)

    def process(self):
        if not self.inp: return
        d=os.path.join(os.path.expanduser("~"),"CutPaste_Output")
        os.makedirs(d,exist_ok=True)
        name=os.path.splitext(os.path.basename(self.inp))[0]
        self.out=os.path.join(d,f"{name}_no_bg.png")
        self.bRun.setEnabled(False); self.bUp.setEnabled(False); self.bSav.setEnabled(False)
        self.pbar.setValue(0)
        self.worker=Worker(self.inp,self.out)
        self.worker.prog.connect(lambda v,m:(self.pbar.setValue(v),self.status.setText(f"⏳ {m}")))
        self.worker.done.connect(self._done)
        self.worker.error.connect(self._err)
        self.worker.start()

    def _done(self, path, W, H):
        self.pbar.setValue(100)
        self.res.setImg(path)
        self.bRun.setEnabled(True); self.bUp.setEnabled(True); self.bSav.setEnabled(True)
        mb=os.path.getsize(path)/1024/1024
        self.status.setText(f"✅  Perfect! {W}×{H} px · {mb:.1f} MB  —  Save button click કરો")

    def _err(self, msg):
        self.pbar.setValue(0)
        self.bRun.setEnabled(True); self.bUp.setEnabled(True)
        self.status.setText("❌  Error")
        QMessageBox.critical(self,"Error",msg)

    def save(self):
        if not self.out or not os.path.exists(self.out): return
        d,_=QFileDialog.getSaveFileName(self,"Save","CutPaste.png","PNG (*.png)")
        if d:
            import shutil; shutil.copy2(self.out,d)
            self.status.setText(f"💾  Saved: {d}")
            QMessageBox.information(self,"Saved!",f"File saved:\n{d}")

    def clear(self):
        self.inp=self.out=None
        self.orig.clearImg("📂  Photo drop કરો\nઅથવા Upload button")
        self.res.clearImg("✨  Perfect result\nઅહીં આવશે")
        self.bRun.setEnabled(False); self.bSav.setEnabled(False)
        self.pbar.setValue(0)
        self.status.setText("Photo upload કરો — 100% perfect background remove")

CSS = """
QWidget#root{background:#07080f}
QLabel#title{font-size:20px;font-weight:800;color:#22d3ee;letter-spacing:1px}
QLabel#sub{font-size:11px;color:#2d3748}
QLabel#ptitle{font-size:10px;font-weight:700;color:#4b5563;letter-spacing:2px}
QLabel#prev{background:#0e1117;border:1.5px dashed #1e2535;border-radius:14px;color:#374151;font-size:13px;padding:12px}
QLabel#prev_r{background:#0e1117;border:1.5px dashed #0f3460;border-radius:14px;color:#374151;font-size:13px;padding:12px}
QProgressBar#pbar{background:#1e2535;border:none;border-radius:4px}
QProgressBar#pbar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #22d3ee,stop:1 #22c55e);border-radius:4px}
QLabel#status{font-size:12px;color:#4b5563}
QMainWindow{background:#07080f}
"""

if __name__=="__main__":
    app=QApplication(sys.argv)
    app.setStyle("Fusion")
    p=QPalette()
    p.setColor(QPalette.Window,QColor("#07080f"))
    p.setColor(QPalette.WindowText,QColor("#e2e8f0"))
    p.setColor(QPalette.Base,QColor("#0e1117"))
    p.setColor(QPalette.Text,QColor("#e2e8f0"))
    app.setPalette(p)
    win=App(); win.show()
    sys.exit(app.exec_())
