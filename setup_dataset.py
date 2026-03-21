"""
SADAK AI — Dataset Setup Script
Fixed for: chitholian/annotated-potholes-dataset
Structure: annotated-images/ contains BOTH .jpg and .xml files together

Usage:
  1. Copy the entire  annotated-images/  folder into  sadak_ai/dataset/raw/
  2. Run:  python setup_dataset.py
"""

import os, glob, shutil, random, xml.etree.ElementTree as ET

BASE     = os.path.dirname(os.path.abspath(__file__))
RAW_DIR  = os.path.join(BASE, "dataset", "raw")   # search everything inside here

OUT_TRAIN_IMG = os.path.join(BASE, "dataset", "images", "train")
OUT_VAL_IMG   = os.path.join(BASE, "dataset", "images", "val")
OUT_TRAIN_LBL = os.path.join(BASE, "dataset", "labels", "train")
OUT_VAL_LBL   = os.path.join(BASE, "dataset", "labels", "val")

for d in [OUT_TRAIN_IMG, OUT_VAL_IMG, OUT_TRAIN_LBL, OUT_VAL_LBL]:
    os.makedirs(d, exist_ok=True)

def xml_to_yolo(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        size = root.find("size")
        W = int(size.find("width").text)
        H = int(size.find("height").text)
        if W == 0 or H == 0:
            return []
        lines = []
        for obj in root.findall("object"):
            name = obj.find("name").text.lower().strip()
            bb = obj.find("bndbox")
            xmin = float(bb.find("xmin").text)
            ymin = float(bb.find("ymin").text)
            xmax = float(bb.find("xmax").text)
            ymax = float(bb.find("ymax").text)
            cx = ((xmin + xmax) / 2) / W
            cy = ((ymin + ymax) / 2) / H
            bw = (xmax - xmin) / W
            bh = (ymax - ymin) / H
            cx,cy,bw,bh = [max(0.0, min(1.0, v)) for v in [cx,cy,bw,bh]]
            if bw > 0 and bh > 0:
                lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        return lines
    except Exception as e:
        return []

print("\n" + "="*52)
print("  SADAK AI — Dataset Setup")
print("="*52)
print(f"\n  Searching in: {RAW_DIR}")

# Find ALL xml files recursively under dataset/raw/
xml_files = glob.glob(os.path.join(RAW_DIR, "**", "*.xml"), recursive=True)

# Also try common Kaggle unzip locations just in case
if not xml_files:
    extra = os.path.join(BASE, "dataset", "annotated-images")
    xml_files = glob.glob(os.path.join(extra, "*.xml"))
    if xml_files:
        RAW_DIR = extra

if not xml_files:
    print("\n❌  No XML files found!")
    print("\n  Please do this:")
    print(f"  1. Open your downloaded ZIP / archive")
    print(f"  2. Find the  annotated-images  folder")
    print(f"  3. Copy that entire folder into:")
    print(f"     {RAW_DIR}\\")
    print(f"\n  So the path looks like:")
    print(f"     {RAW_DIR}\\annotated-images\\img-8.jpg")
    print(f"     {RAW_DIR}\\annotated-images\\img-8.xml")
    print(f"\n  Then run this script again.")
    input("\nPress Enter to exit...")
    exit(1)

print(f"\n  Found {len(xml_files)} XML files")

valid_pairs = []
skipped = 0

for xml_path in xml_files:
    lines = xml_to_yolo(xml_path)
    if not lines:
        skipped += 1
        continue

    stem    = os.path.splitext(os.path.basename(xml_path))[0]
    xml_dir = os.path.dirname(xml_path)

    # Look for matching image in SAME folder as XML (chitholian dataset keeps them together)
    img_path = None
    for ext in [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]:
        c = os.path.join(xml_dir, stem + ext)
        if os.path.exists(c):
            img_path = c
            break

    if img_path:
        valid_pairs.append((img_path, lines))
    else:
        skipped += 1

print(f"  Valid image+annotation pairs: {len(valid_pairs)}")
if skipped:
    print(f"  Skipped (no match or empty): {skipped}")

if not valid_pairs:
    print("\n❌  No valid pairs found.")
    input("Press Enter to exit...")
    exit(1)

# 80/20 split
random.seed(42)
random.shuffle(valid_pairs)
split       = int(len(valid_pairs) * 0.80)
train_pairs = valid_pairs[:split]
val_pairs   = valid_pairs[split:]

print(f"\n  Splitting: {len(train_pairs)} train / {len(val_pairs)} val")
print(f"  Copying files...", end="", flush=True)

def copy_pair(img_path, lines, img_dir, lbl_dir):
    stem = os.path.splitext(os.path.basename(img_path))[0]
    ext  = os.path.splitext(img_path)[1].lower()
    shutil.copy2(img_path, os.path.join(img_dir, stem + ext))
    with open(os.path.join(lbl_dir, stem + ".txt"), "w") as f:
        f.write("\n".join(lines))

for p in train_pairs: copy_pair(*p, OUT_TRAIN_IMG, OUT_TRAIN_LBL)
for p in val_pairs:   copy_pair(*p, OUT_VAL_IMG,   OUT_VAL_LBL)

print(" done!")
print("\n" + "="*52)
print("  DATASET READY!")
print("="*52)
print(f"\n  Train: {len(train_pairs)} images + labels")
print(f"  Val:   {len(val_pairs)} images + labels")
print(f"\n  Next — run these commands:")
print(f"\n  pip install ultralytics")
print(f"  yolo detect train data=dataset/pothole.yaml model=yolov8n.pt epochs=50 imgsz=640")
print(f"\n  After training completes:")
print(f"  copy runs\\detect\\train\\weights\\best.pt  models\\best.pt")
print(f"\n  Then:  python app.py")
print("="*52)
input("\nPress Enter to exit...")