"""
SADAK AI v2 — Pothole Detection Engine
AUTO-SELECTS best available engine:
  • If  models/best.pt  exists  → YOLOv8 (trained on Kaggle dataset) ← BEST
  • Otherwise                   → 7-Stage OpenCV pipeline             ← FALLBACK

Train YOLOv8:
  1. Put images in  dataset/images/train/  and labels in  dataset/labels/train/
  2. pip install ultralytics
  3. yolo detect train data=dataset/pothole.yaml model=yolov8n.pt epochs=50 imgsz=640
  4. copy runs/detect/train/weights/best.pt  →  models/best.pt
  5. Restart app — YOLOv8 activates automatically ✅
"""
import cv2, numpy as np, logging, time, os
from dataclasses import dataclass, asdict

logger     = logging.getLogger(__name__)
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "best.pt")


@dataclass
class DetectionResult:
    detected:        bool
    severity:        str
    confidence:      float
    pothole_count:   int
    total_area_px2:  float
    max_depth_score: float
    processing_ms:   float
    bounding_boxes:  list
    stage_results:   dict
    engine:          str = "opencv"
    error:           str | None = None

    def to_dict(self):
        return asdict(self)


# ════════════════════════════════════════════════════════════
#  YOLO ENGINE  (used when models/best.pt is present)
# ════════════════════════════════════════════════════════════
class YOLODetector:
    CONF_THRESHOLD = 0.55   # raised: reduces false positives (was 0.40)
    MIN_BOX_AREA   = 1200   # px² — rejects tiny noise detections (was 600)
    MAX_ASPECT     = 5.0    # reject very thin/wide boxes (not potholes)
    SEV_TABLE = [            # (min boxes, min avg conf) → severity
        (3, 0.85, "CRITICAL"),
        (2, 0.72, "HIGH"),
        (1, 0.60, "MEDIUM"),
        (1, 0.00, "LOW"),
    ]

    def __init__(self, model_path: str):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.model.fuse()   # faster inference
        logger.info("YOLOv8 model loaded from %s", model_path)

    def detect(self, source, scanner_mode=False) -> DetectionResult:
        t0 = time.perf_counter()
        try:
            img = self._load(source)
            if img is None:
                return self._err("Cannot decode image")

            h, w = img.shape[:2]

            results = self.model.predict(
                source   = img,
                conf     = self.CONF_THRESHOLD,
                iou      = 0.50,
                imgsz    = 640,
                verbose  = False,
                device   = "cpu",
            )

            boxes      = results[0].boxes
            # ── PRECISION FILTERS: reject non-pothole detections ──
            if boxes is not None and len(boxes):
                valid_idx = []
                for i, box in enumerate(boxes.xyxy.tolist()):
                    x1, y1, x2, y2 = box
                    bw, bh   = max(1, x2-x1), max(1, y2-y1)
                    area     = bw * bh
                    aspect   = max(bw/bh, bh/bw)
                    # Reject: too small (noise) OR too thin/elongated (road lines, shadows)
                    if area >= self.MIN_BOX_AREA and aspect <= self.MAX_ASPECT:
                        valid_idx.append(i)
                if valid_idx and len(valid_idx) < len(boxes):
                    import torch
                    keep = torch.tensor(valid_idx)
                    boxes = boxes[keep]
            n          = len(boxes) if boxes is not None else 0
            confs      = boxes.conf.tolist() if boxes is not None and len(boxes) else []
            xyxy_list  = boxes.xyxy.tolist() if boxes is not None and len(boxes) else []

            detected   = n > 0
            avg_conf   = float(np.mean(confs)) if confs else 0.0
            max_conf   = float(max(confs))     if confs else 0.0
            severity   = self._classify(n, avg_conf)
            total_area = 0.0

            bboxes = []
            for i, xyxy in enumerate(xyxy_list):
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                bw = x2 - x1; bh = y2 - y1
                total_area += bw * bh
                bboxes.append({"x":x1,"y":y1,"w":bw,"h":bh,"depth":round(confs[i],3)})

            ms = (time.perf_counter()-t0)*1000
            return DetectionResult(
                detected       = detected,
                severity       = severity,
                confidence     = round(max_conf, 3),
                pothole_count  = n,
                total_area_px2 = round(total_area, 1),
                max_depth_score= round(avg_conf, 3),
                processing_ms  = round(ms, 1),
                bounding_boxes = bboxes,
                stage_results  = {"engine":"yolov8","boxes":n,"avg_conf":round(avg_conf,3)},
                engine         = "yolov8",
            )
        except Exception as e:
            logger.exception("YOLOv8 detection failed: %s", e)
            return self._err(str(e))

    def _classify(self, n, conf):
        for min_n, min_c, label in self.SEV_TABLE:
            if n >= min_n and conf >= min_c:
                return label
        return "LOW"

    def _load(self, source):
        if isinstance(source, (bytes, bytearray)):
            arr = np.frombuffer(source, np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return cv2.imread(str(source))

    def _err(self, msg):
        return DetectionResult(False,"UNKNOWN",0.0,0,0.0,0.0,0.0,[],{},engine="yolov8",error=msg)


# ════════════════════════════════════════════════════════════
#  OPENCV ENGINE  (7-stage fallback, no model file needed)
# ════════════════════════════════════════════════════════════
class OpenCVDetector:
    MIN_AREA     = 600
    MAX_AREA     = 120000
    MIN_SOLIDITY = 0.30
    MORPH_K      = np.ones((5,5), np.uint8)
    SCANNER_THRESHOLD = 0.52
    IMAGE_THRESHOLD   = 0.60

    SEV_TABLE = [
        (22000, 0.68, "CRITICAL"),
        (10000, 0.52, "HIGH"),
        (3500,  0.32, "MEDIUM"),
        (0,     0.0,  "LOW"),
    ]

    def detect(self, source, scanner_mode=False) -> DetectionResult:
        t0 = time.perf_counter()
        stages = {}
        try:
            img = self._load(source)
            if img is None: return self._err("Cannot decode image")
            h, w = img.shape[:2]
            if h < 40 or w < 40: return self._err("Image too small")

            scale = min(1.0, 640/max(h,w))
            if scale < 1.0:
                img = cv2.resize(img, None, fx=scale, fy=scale)
                h, w = img.shape[:2]

            # Stage 1: CLAHE
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l,a,b = cv2.split(lab)
            l2 = cv2.createCLAHE(clipLimit=3.0,tileGridSize=(8,8)).apply(l)
            enhanced = cv2.cvtColor(cv2.merge([l2,a,b]),cv2.COLOR_LAB2BGR)
            gray = cv2.cvtColor(enhanced,cv2.COLOR_BGR2GRAY)

            # Stage 2: Segmentation
            blurred = cv2.GaussianBlur(gray,(5,5),0)
            _,otsu  = cv2.threshold(blurred,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
            adapt   = cv2.adaptiveThreshold(blurred,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,15,3)
            combined = cv2.morphologyEx(cv2.bitwise_and(otsu,adapt),cv2.MORPH_CLOSE,self.MORPH_K,iterations=2)
            combined = cv2.morphologyEx(combined,cv2.MORPH_OPEN,self.MORPH_K,iterations=1)

            # Stage 3: Edges
            e1 = cv2.Canny(blurred,35,110)
            e2 = cv2.Canny(cv2.GaussianBlur(gray,(9,9),0),20,55)
            mask = cv2.bitwise_or(combined,cv2.dilate(cv2.bitwise_or(e1,e2),np.ones((3,3),np.uint8)))

            # Stage 4: Contours
            cnts,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            valid = []
            for cnt in cnts:
                area = cv2.contourArea(cnt)
                if area < self.MIN_AREA or area > self.MAX_AREA: continue
                hull_area = cv2.contourArea(cv2.convexHull(cnt))
                if (hull_area and area/hull_area < self.MIN_SOLIDITY): continue
                x,y,cw,ch = cv2.boundingRect(cnt)
                aspect = cw/ch if ch else 0
                if aspect > 7 or aspect < 0.12: continue
                valid.append({"contour":cnt,"area":area,"bbox":(x,y,cw,ch)})

            # Stage 5: Depth
            depth_scores = []
            for v in valid:
                x,y,cw,ch = v["bbox"]
                roi = gray[y:y+ch, x:x+cw]
                if roi.size == 0: continue
                darkness = (255-float(np.mean(roi)))/255
                texture  = float(np.std(roi))/128
                sx = cv2.Sobel(roi,cv2.CV_64F,1,0,ksize=3)
                sy = cv2.Sobel(roi,cv2.CV_64F,0,1,ksize=3)
                grad = float(np.mean(np.sqrt(sx**2+sy**2)))/255
                ds = min(1.0, 0.45*darkness+0.30*texture+0.25*grad)
                v["depth"] = ds; depth_scores.append(ds)

            max_depth  = max(depth_scores) if depth_scores else 0.0
            total_area = sum(v["area"] for v in valid)

            # Stage 6: Road verify
            hsv = cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
            road_ratio = float(np.sum((hsv[:,:,1]<65)&(hsv[:,:,2]>25)&(hsv[:,:,2]<210)))/(h*w)

            # Stage 7: Classify
            detected = len(valid)>0 and max_depth>0.15 and road_ratio>0.04
            severity = "LOW"
            if detected:
                severity = self._classify(total_area, max_depth, len(valid))
            conf = min(0.97,
                0.32*min(1.0,total_area/18000)+0.28*max_depth+
                0.22*min(1.0,road_ratio*2)+0.18*min(1.0,len(valid)/3)
            ) if detected else max(0.0, road_ratio*0.45)
            if severity=="CRITICAL": conf = min(0.98,conf+0.07)

            threshold = self.SCANNER_THRESHOLD if scanner_mode else self.IMAGE_THRESHOLD
            final_detected = detected and conf >= threshold
            bboxes = [{"x":round(v["bbox"][0]/scale),"y":round(v["bbox"][1]/scale),
                       "w":round(v["bbox"][2]/scale),"h":round(v["bbox"][3]/scale),
                       "depth":round(v.get("depth",0),3)} for v in valid[:5]] if final_detected else []

            ms = (time.perf_counter()-t0)*1000
            return DetectionResult(
                detected=final_detected, severity=severity,
                confidence=round(float(conf),3), pothole_count=len(valid),
                total_area_px2=round(float(total_area),1),
                max_depth_score=round(float(max_depth),3),
                processing_ms=round(ms,1), bounding_boxes=bboxes,
                stage_results={"road_ratio":round(road_ratio,3),"valid":len(valid)},
                engine="opencv",
            )
        except Exception as e:
            logger.exception("OpenCV detection error: %s", e)
            return self._err(str(e))

    def _classify(self, area, depth, count):
        eff = area*(1+0.08*(count-1))
        for min_a,min_d,label in self.SEV_TABLE:
            if eff>=min_a and depth>=min_d: return label
        return "LOW"

    def _load(self, source):
        if isinstance(source,(bytes,bytearray)):
            return cv2.imdecode(np.frombuffer(source,np.uint8),cv2.IMREAD_COLOR)
        return cv2.imread(str(source))

    def _err(self, msg):
        return DetectionResult(False,"UNKNOWN",0.0,0,0.0,0.0,0.0,[],{},engine="opencv",error=msg)


# ════════════════════════════════════════════════════════════
#  AUTO-SELECT ENGINE
# ════════════════════════════════════════════════════════════
class PotholeDetector:
    """Auto-selects YOLOv8 if model exists, else falls back to OpenCV."""

    def __init__(self):
        if os.path.exists(MODEL_PATH):
            try:
                self._engine = YOLODetector(MODEL_PATH)
                logger.info("✅ Engine: YOLOv8 (models/best.pt)")
            except ImportError:
                logger.warning("ultralytics not installed — pip install ultralytics")
                self._engine = OpenCVDetector()
                logger.info("✅ Engine: OpenCV 7-stage (fallback)")
            except Exception as e:
                logger.warning("YOLOv8 load failed (%s) — falling back to OpenCV", e)
                self._engine = OpenCVDetector()
        else:
            self._engine = OpenCVDetector()
            logger.info("✅ Engine: OpenCV 7-stage (models/best.pt not found)")

    def detect(self, source, scanner_mode=False) -> DetectionResult:
        return self._engine.detect(source, scanner_mode=scanner_mode)

    @property
    def engine_name(self):
        return getattr(self._engine, '__class__', type(self._engine)).__name__


_detector = None
def get_detector() -> PotholeDetector:
    global _detector
    if _detector is None:
        _detector = PotholeDetector()
    return _detector