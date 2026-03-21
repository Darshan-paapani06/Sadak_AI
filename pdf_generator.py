"""
SADAK AI v3 — PDF Generator
Pure Python, zero dependencies. Generates a proper PDF complaint letter.
Falls back to fpdf2 if installed, otherwise uses built-in PDF writer.
"""
import os, struct, zlib, textwrap
from datetime import datetime


# ──────────────────────────────────────────────────────────
#  PURE PYTHON PDF WRITER  (no external deps)
# ──────────────────────────────────────────────────────────
class MiniPDF:
    """Minimal but complete PDF 1.4 writer."""

    def __init__(self, w=595, h=842):  # A4 at 72dpi points
        self.w = w; self.h = h
        self._objs = []   # list of (obj_id, content_bytes)
        self._pages = []  # page object ids
        self._cur_page_stream = []
        self._resources = {}
        self._next_id = 1

    # ── low-level ─────────────────────────────────────────
    def _alloc(self, content: bytes) -> int:
        oid = self._next_id; self._next_id += 1
        self._objs.append((oid, content))
        return oid

    def _str(self, s: str) -> bytes:
        return s.encode('latin-1', errors='replace')

    # ── page control ──────────────────────────────────────
    def add_page(self):
        if self._cur_page_stream:
            self._flush_page()
        self._cur_page_stream = []

    def _flush_page(self):
        stream = self._str('\n'.join(self._cur_page_stream) + '\n')
        cs = self._alloc(
            f'<< /Length {len(stream)} >>\nstream\n'.encode() +
            stream + b'\nendstream'
        )
        pg = self._alloc(
            f'<< /Type /Page /Parent 2 /MediaBox [0 0 {self.w} {self.h}] '
            f'/Contents {cs} 0 R '
            f'/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> >>'
            .encode()
        )
        self._pages.append(pg)
        self._cur_page_stream = []

    # ── drawing commands ──────────────────────────────────
    def _y(self, y): return self.h - y  # flip Y

    def set_fill_rgb(self, r, g, b):
        self._cur_page_stream.append(f'{r/255:.3f} {g/255:.3f} {b/255:.3f} rg')

    def set_stroke_rgb(self, r, g, b):
        self._cur_page_stream.append(f'{r/255:.3f} {g/255:.3f} {b/255:.3f} RG')

    def rect_fill(self, x, y, w, h):
        self._cur_page_stream.append(f'{x:.1f} {self._y(y+h):.1f} {w:.1f} {h:.1f} re f')

    def line(self, x1, y1, x2, y2, width=0.5):
        self._cur_page_stream.append(
            f'{width:.1f} w {x1:.1f} {self._y(y1):.1f} m {x2:.1f} {self._y(y2):.1f} l S')

    def text(self, x, y, txt, size=10, bold=False, italic=False, color=(0,0,0)):
        r,g,b = color
        font = 'F2' if bold else ('F3' if italic else 'F1')
        safe = str(txt).replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        self._cur_page_stream.append(
            f'{r/255:.3f} {g/255:.3f} {b/255:.3f} rg '
            f'BT /{font} {size:.1f} Tf {x:.1f} {self._y(y):.1f} Td ({safe}) Tj ET'
        )
        # Reset fill to black
        self._cur_page_stream.append('0 0 0 rg')

    def multiline_text(self, x, y, txt, size=9, width=80, color=(0,0,0), bold=False, line_h=13):
        lines = []
        for para in str(txt).split('\n'):
            if not para.strip():
                lines.append('')
                continue
            wrapped = textwrap.wrap(para, width=width) or ['']
            lines.extend(wrapped)
        for line in lines:
            self.text(x, y, line, size=size, bold=bold, color=color)
            y += line_h
        return y

    # ── output ────────────────────────────────────────────
    def save(self, path: str):
        # Flush last page
        if self._cur_page_stream:
            self._flush_page()

        # Pre-allocate catalog(1), pages(2), fonts(3,4,5)
        # We need to insert them at the right IDs
        # Build font objects first as IDs 3,4,5
        font_objs = {
            3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
            4: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>',
            5: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>',
        }

        page_refs = ' '.join(f'{p} 0 R' for p in self._pages)
        pages_obj = f'<< /Type /Pages /Kids [{page_refs}] /Count {len(self._pages)} >>'.encode()
        catalog   = b'<< /Type /Catalog /Pages 2 0 R >>'

        # Collect all objects in ID order
        all_objs = {}
        all_objs[1] = catalog
        all_objs[2] = pages_obj
        all_objs[3] = font_objs[3]
        all_objs[4] = font_objs[4]
        all_objs[5] = font_objs[5]
        for oid, content in self._objs:
            all_objs[oid + 4] = content  # shift by 4 to make room for 1-5

        # Fix page /Parent references (they ref id 2 which is correct)
        # But page /Contents and font refs shifted by 4 — fix them
        for oid in sorted(all_objs.keys()):
            if oid > 5:
                raw = all_objs[oid]
                if isinstance(raw, bytes):
                    # Shift all N 0 R references where N >= 1 by +4
                    import re
                    def shift_ref(m):
                        n = int(m.group(1))
                        new_n = n + 4 if n >= 1 else n
                        return f'{new_n} 0 R'.encode()
                    all_objs[oid] = re.sub(rb'(\d+) 0 R', lambda m: (
                        (int(m.group(1))+4).to_bytes(4,'big').lstrip(b'\x00') or b'1'
                    ).decode().encode() + b' 0 R', raw)

        # Simplest approach: just rewrite correctly
        # Reset and rebuild properly
        buf = b'%PDF-1.4\n'
        offsets = {}
        all_ids_sorted = sorted(all_objs.keys())
        for oid in all_ids_sorted:
            offsets[oid] = len(buf)
            content = all_objs[oid]
            if not isinstance(content, bytes):
                content = str(content).encode()
            buf += f'{oid} 0 obj\n'.encode() + content + b'\nendobj\n'

        xref_pos = len(buf)
        buf += b'xref\n'
        buf += f'0 {max(all_ids_sorted)+1}\n'.encode()
        buf += b'0000000000 65535 f \n'
        for i in range(1, max(all_ids_sorted)+1):
            if i in offsets:
                buf += f'{offsets[i]:010d} 00000 n \n'.encode()
            else:
                buf += b'0000000000 65535 f \n'
        buf += b'trailer\n'
        buf += f'<< /Size {max(all_ids_sorted)+1} /Root 1 0 R >>\n'.encode()
        buf += b'startxref\n'
        buf += f'{xref_pos}\n'.encode()
        buf += b'%%EOF\n'

        with open(path, 'wb') as f:
            f.write(buf)


# ──────────────────────────────────────────────────────────
#  PROPER HTML→PDF VIA REPORTLAB (if available)
# ──────────────────────────────────────────────────────────

def _generate_with_fpdf(complaint: dict, output_path: str):
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_fill_color(11, 61, 145)
            self.rect(0, 0, 210, 30, 'F')
            self.set_fill_color(255, 103, 31)
            self.rect(0, 0, 3, 30, 'F')
            # SADAK in orange
            self.set_font('Helvetica', 'B', 20)
            sadak_w = self.get_string_width('SADAK')
            self.set_text_color(255, 103, 31)
            self.set_xy(8, 6)
            self.cell(sadak_w, 8, 'SADAK', 0, 0)
            # AI in white — positioned right after SADAK
            self.set_text_color(255, 255, 255)
            self.set_font('Helvetica', 'B', 20)
            self.set_xy(8 + sadak_w, 6)
            self.cell(20, 8, 'AI', 0, 1)
            # Subtitle
            self.set_text_color(200, 200, 200)
            self.set_font('Helvetica', '', 8)
            self.set_xy(8, 16)
            self.cell(0, 6, 'National Road Intelligence System  |  Government of India  |  Ministry of Road Transport & Highways', 0, 1)
            self.ln(6)

        def footer(self):
            self.set_y(-14)
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.3)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(1)
            self.set_text_color(160, 160, 160)
            self.set_font('Helvetica', 'I', 7.5)
            self.cell(0, 8,
                'SADAK AI  |  Generated: ' + datetime.now().strftime('%d %b %Y, %H:%M IST') +
                '  |  Page ' + str(self.page_no()) +
                '  |  This is a system-generated official complaint letter.',
                0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    cid   = complaint.get('complaint_id','UNKNOWN')
    sev   = complaint.get('severity','MEDIUM')
    state = complaint.get('state','')
    dist  = complaint.get('district','')
    desc  = complaint.get('description','Pothole / Road Damage')
    auth  = complaint.get('authority_name','PWD')
    hl    = complaint.get('helpline','1033')
    stat  = complaint.get('status','FILED')
    filed = str(complaint.get('filed_at',''))[:10]
    dead  = str(complaint.get('response_deadline',''))[:10]
    lat   = complaint.get('latitude','')
    lng   = complaint.get('longitude','')
    ai    = complaint.get('ai_detected', False)
    conf  = complaint.get('ai_confidence', 0)
    cnt   = complaint.get('ai_pothole_count', 1)
    user  = complaint.get('user_name','Citizen')
    email = complaint.get('user_email','')
    phone = complaint.get('user_phone','')

    SEV_COLOR = {'CRITICAL':(220,38,38),'HIGH':(249,115,22),'MEDIUM':(202,138,4),'LOW':(22,163,74)}
    sv_col = SEV_COLOR.get(sev, (11,61,145))

    # ── OFFICIAL NOTICE HEADER ─────────────────────────────
    pdf.set_fill_color(248,249,250)
    pdf.rect(10, pdf.get_y(), 190, 22, 'F')
    pdf.set_draw_color(11,61,145)
    pdf.set_line_width(0.4)
    pdf.rect(10, pdf.get_y(), 190, 22)
    y0 = pdf.get_y() + 3
    pdf.set_text_color(11,61,145)
    pdf.set_font('Helvetica','B',10)
    pdf.set_xy(15, y0)
    pdf.cell(100, 6, 'OFFICIAL ROAD DAMAGE COMPLAINT LETTER', 0, 0)
    pdf.set_text_color(100,100,100)
    pdf.set_font('Helvetica','',8)
    pdf.set_xy(130, y0)
    pdf.cell(65, 6, 'Ref: ' + cid, 0, 1)
    pdf.set_text_color(80,80,80)
    pdf.set_font('Helvetica','',8)
    pdf.set_xy(15, y0+7)
    pdf.cell(0, 6, 'Filed on: ' + filed + '   |   Status: ' + stat + '   |   Response due: ' + (dead or 'TBD'), 0, 1)
    pdf.ln(6)

    # ── TO ADDRESS ────────────────────────────────────────
    pdf.set_font('Helvetica','B',9)
    pdf.set_text_color(80,80,80)
    pdf.cell(0, 5, 'TO:', 0, 1)
    pdf.set_font('Helvetica','B',11)
    pdf.set_text_color(11,61,145)
    pdf.cell(0, 6, auth, 0, 1)
    pdf.set_font('Helvetica','',9)
    pdf.set_text_color(80,80,80)
    pdf.cell(0, 5, 'Location: ' + dist + ', ' + state + ', India', 0, 1)
    if hl:
        pdf.cell(0, 5, 'Helpline: ' + str(hl), 0, 1)
    pdf.ln(4)

    # ── SUBJECT ───────────────────────────────────────────
    pdf.set_fill_color(*sv_col)
    pdf.rect(10, pdf.get_y(), 3, 8, 'F')
    pdf.set_xy(16, pdf.get_y())
    pdf.set_font('Helvetica','B',10)
    pdf.set_text_color(30,30,30)
    pdf.cell(0, 8, 'SUBJECT: Road Damage Report — ' + sev + ' Severity', 0, 1)
    pdf.ln(3)

    # ── BODY ──────────────────────────────────────────────
    pdf.set_font('Helvetica','',9.5)
    pdf.set_text_color(50,50,50)
    date_str = datetime.now().strftime('%d %B %Y')
    body = (
        f'Sir/Madam,\n\n'
        f'I, {user}, am writing to formally report a case of road damage detected at the location '
        f'specified below. This complaint has been filed through SADAK AI — the National Road '
        f'Intelligence System of the Government of India, powered by AI detection technology.\n\n'
        f'The damage was identified on {filed} and requires immediate attention from the '
        f'concerned authority. I request that the necessary repairs be carried out at the earliest '
        f'convenience, ideally within the stipulated response deadline of {dead or "15 working days"}.\n\n'
        f'Description of Damage:\n{desc}\n'
    )
    y_after = pdf.get_y()
    for para in body.split('\n'):
        if para.strip():
            pdf.set_x(15)
            pdf.multi_cell(180, 5.5, para)
        else:
            pdf.ln(3)
    pdf.ln(3)

    # ── DETAILS TABLE ────────────────────────────────────
    pdf.set_fill_color(11,61,145)
    pdf.rect(10, pdf.get_y(), 190, 8, 'F')
    pdf.set_text_color(255,255,255)
    pdf.set_font('Helvetica','B',9)
    pdf.set_xy(15, pdf.get_y()+1.5)
    pdf.cell(0, 5, 'COMPLAINT DETAILS', 0, 1)
    pdf.ln(0)

    rows = [
        ('Complaint ID',     cid),
        ('Severity Level',   sev),
        ('Location',         f'{dist}, {state}, India'),
        ('GPS Coordinates',  f'{lat}°N, {lng}°E' if lat and lng else 'Not available'),
        ('AI Detected',      'Yes — ' + str(round(float(conf)*100 if conf else 0)) + '% confidence, ' + str(cnt) + ' pothole(s) detected' if ai else 'Manual Report'),
        ('Responsible Auth', auth),
        ('Helpline',         str(hl)),
        ('Filed Date',       filed),
        ('Response Due',     dead or 'TBD'),
        ('Current Status',   stat),
        ('Filed By',         user + (' (' + email + ')' if email else '')),
    ]
    fill = False
    for label, val in rows:
        bg = (245,247,250) if fill else (255,255,255)
        pdf.set_fill_color(*bg)
        pdf.rect(10, pdf.get_y(), 190, 7, 'F')
        pdf.set_draw_color(220,220,220)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y()+7, 200, pdf.get_y()+7)
        pdf.set_text_color(80,80,80)
        pdf.set_font('Helvetica','B',8.5)
        pdf.set_xy(15, pdf.get_y()+1)
        pdf.cell(55, 5, label, 0, 0)
        pdf.set_font('Helvetica','',8.5)
        pdf.set_text_color(30,30,30)
        pdf.cell(130, 5, str(val)[:80], 0, 1)
        fill = not fill
    pdf.ln(5)

    # ── SIGNATURE ────────────────────────────────────────
    pdf.set_font('Helvetica','',9)
    pdf.set_text_color(50,50,50)
    pdf.cell(0,5,'Yours faithfully,',0,1)
    pdf.ln(2)
    pdf.set_font('Helvetica','B',10)
    pdf.set_text_color(11,61,145)
    pdf.cell(0,6,user,0,1)
    pdf.set_font('Helvetica','',8.5)
    pdf.set_text_color(100,100,100)
    if email: pdf.cell(0,5,email,0,1)
    if phone: pdf.cell(0,5,'Mobile: '+str(phone),0,1)
    pdf.cell(0,5,'Filed via SADAK AI — National Road Intelligence System',0,1)
    pdf.ln(5)

    # ── DISCLAIMER ───────────────────────────────────────
    pdf.set_fill_color(255,251,235)
    pdf.set_draw_color(202,138,4)
    pdf.set_line_width(0.4)
    y_d = pdf.get_y()
    pdf.rect(10, y_d, 190, 14)
    pdf.set_xy(15, y_d+2)
    pdf.set_font('Helvetica','B',8)
    pdf.set_text_color(146,64,14)
    pdf.cell(0,5,'IMPORTANT NOTICE',0,1)
    pdf.set_xy(15, y_d+8)
    pdf.set_font('Helvetica','',7.5)
    pdf.cell(0,5,'This is a system-generated official complaint letter under the Right to Public Services Act. Complaint ID is unique and traceable.',0,1)

    pdf.output(output_path)


# ──────────────────────────────────────────────────────────
#  FALLBACK: pure-python minimal PDF
# ──────────────────────────────────────────────────────────
def _generate_minimal_pdf(complaint: dict, output_path: str):
    """Pure stdlib PDF writer — no dependencies required."""
    cid   = complaint.get('complaint_id','UNKNOWN')
    sev   = complaint.get('severity','MEDIUM')
    state = complaint.get('state','')
    dist  = complaint.get('district','')
    desc  = complaint.get('description','Pothole reported')
    auth  = complaint.get('authority_name','PWD')
    hl    = complaint.get('helpline','1033')
    stat  = complaint.get('status','FILED')
    filed = str(complaint.get('filed_at',''))[:10]
    dead  = str(complaint.get('response_deadline',''))[:10]
    lat   = complaint.get('latitude','')
    lng   = complaint.get('longitude','')
    user  = complaint.get('user_name','Citizen')
    email = complaint.get('user_email','')
    ai    = complaint.get('ai_detected', False)
    conf  = complaint.get('ai_confidence', 0)
    cnt   = complaint.get('ai_pothole_count', 1)
    now   = datetime.now().strftime('%d %b %Y %H:%M IST')

    def _str(s): return str(s).replace('(','[').replace(')','[]').replace('\\','/')

    # Build page content stream
    cmds = []

    # Navy header bar
    cmds.append('0.043 0.239 0.565 rg')
    cmds.append('0 792 612 50 re f')
    # Orange accent bar
    cmds.append('1.0 0.416 0.122 rg')
    cmds.append('0 792 4 50 re f')

    # Header text
    cmds.append('1.0 0.416 0.122 rg')
    cmds.append('BT /F2 22 Tf 12 818 Td (SADAK) Tj ET')
    cmds.append('1 1 1 rg')
    cmds.append('BT /F2 22 Tf 80 818 Td (AI) Tj ET')
    cmds.append('0.8 0.8 0.8 rg')
    cmds.append('BT /F1 8 Tf 12 808 Td (National Road Intelligence System | Government of India) Tj ET')

    # Reference number top right
    cmds.append('0.8 0.8 0.8 rg')
    cmds.append(f'BT /F1 8 Tf 430 818 Td (Ref: {_str(cid)}) Tj ET')

    # Title
    cmds.append('0.043 0.239 0.565 rg')
    cmds.append(f'BT /F2 13 Tf 40 755 Td (OFFICIAL ROAD DAMAGE COMPLAINT LETTER) Tj ET')

    # Horizontal rule
    cmds.append('0.8 0.8 0.8 RG 0.5 w')
    cmds.append('40 748 m 572 748 l S')

    # Filed info line
    cmds.append('0.4 0.4 0.4 rg')
    cmds.append(f'BT /F1 8.5 Tf 40 736 Td (Filed: {_str(filed)}   Status: {_str(stat)}   Due: {_str(dead or "TBD")}   Severity: {_str(sev)}) Tj ET')

    # To section
    cmds.append('0.3 0.3 0.3 rg')
    cmds.append('BT /F2 9 Tf 40 718 Td (TO:) Tj ET')
    cmds.append('0.043 0.239 0.565 rg')
    cmds.append(f'BT /F2 12 Tf 40 705 Td ({_str(auth)}) Tj ET')
    cmds.append('0.35 0.35 0.35 rg')
    cmds.append(f'BT /F1 9 Tf 40 693 Td ({_str(dist)}, {_str(state)}, India) Tj ET')
    cmds.append(f'BT /F1 9 Tf 40 682 Td (Helpline: {_str(hl)}) Tj ET')

    # Subject
    cmds.append('1.0 0.416 0.122 rg')
    cmds.append('40 668 3 10 re f')
    cmds.append('0.1 0.1 0.1 rg')
    cmds.append(f'BT /F2 10 Tf 48 670 Td (SUBJECT: Road Damage — {_str(sev)} Severity at {_str(dist)}) Tj ET')

    # Body
    cmds.append('0.2 0.2 0.2 rg')
    lines = [
        f'Dear Sir/Madam,',
        '',
        f'I, {_str(user)}, hereby formally report a case of road damage',
        f'at the location described below, filed via SADAK AI.',
        '',
        f'Damage Description: {_str(desc[:70])}',
        f'I request urgent inspection and repair within the deadline.',
        '',
        f'Yours faithfully,',
        f'{_str(user)}',
        f'{_str(email)}',
    ]
    y = 645
    for line in lines:
        if line:
            cmds.append(f'BT /F1 9.5 Tf 40 {y} Td ({_str(line)}) Tj ET')
        y -= 14

    # Details table header
    y -= 6
    cmds.append('0.043 0.239 0.565 rg')
    cmds.append(f'40 {y} 532 14 re f')
    cmds.append('1 1 1 rg')
    cmds.append(f'BT /F2 9 Tf 46 {y+3} Td (COMPLAINT DETAILS) Tj ET')

    rows = [
        ('Complaint ID',    cid),
        ('Severity',        sev),
        ('Location',        f'{dist}, {state}'),
        ('GPS',             f'{lat}N, {lng}E' if lat and lng else 'N/A'),
        ('AI Detection',    f'Yes - {int(float(conf)*100 if conf else 0)}% conf, {cnt} potholes' if ai else 'Manual'),
        ('Authority',       auth),
        ('Filed Date',      filed),
        ('Response Due',    dead or 'TBD'),
        ('Status',          stat),
        ('Filed By',        f'{user} | {email}'),
    ]
    y -= 2
    fill = False
    for lbl, val in rows:
        y -= 13
        if y < 60: break
        bg = '0.957 0.961 0.969' if fill else '1 1 1'
        cmds.append(f'{bg} rg')
        cmds.append(f'40 {y} 532 13 re f')
        cmds.append('0.85 0.85 0.85 RG 0.2 w')
        cmds.append(f'40 {y} m 572 {y} l S')
        cmds.append('0.35 0.35 0.35 rg')
        cmds.append(f'BT /F2 8 Tf 46 {y+3} Td ({_str(lbl)}) Tj ET')
        cmds.append('0.1 0.1 0.1 rg')
        cmds.append(f'BT /F1 8 Tf 200 {y+3} Td ({_str(str(val)[:60])}) Tj ET')
        fill = not fill

    # Footer bar
    cmds.append('0.9 0.9 0.9 RG 0.3 w')
    cmds.append('40 30 m 572 30 l S')
    cmds.append('0.55 0.55 0.55 rg')
    cmds.append(f'BT /F3 7 Tf 40 18 Td (SADAK AI  |  Generated: {_str(now)}  |  Official Complaint Document) Tj ET')

    stream = '\n'.join(cmds).encode('latin-1','replace')

    # Build PDF objects
    objs = {}
    objs[1] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objs[2] = b'<< /Type /Pages /Kids [4 0 R] /Count 1 >>'
    objs[3] = f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream'
    objs[4] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] '
               b'/Contents 3 0 R '
               b'/Resources << /Font << '
               b'/F1 5 0 R /F2 6 0 R /F3 7 0 R '
               b'>> >> >>')
    objs[5] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
    objs[6] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>'
    objs[7] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>'

    buf = b'%PDF-1.4\n'
    xref = {}
    for oid in sorted(objs.keys()):
        xref[oid] = len(buf)
        buf += f'{oid} 0 obj\n'.encode() + objs[oid] + b'\nendobj\n'

    xref_pos = len(buf)
    buf += b'xref\n'
    buf += f'0 {max(objs)+1}\n'.encode()
    buf += b'0000000000 65535 f \n'
    for i in range(1, max(objs)+1):
        off = xref.get(i, 0)
        buf += f'{off:010d} 00000 n \n'.encode()
    buf += b'trailer\n'
    buf += f'<< /Size {max(objs)+1} /Root 1 0 R >>\n'.encode()
    buf += b'startxref\n'
    buf += f'{xref_pos}\n'.encode()
    buf += b'%%EOF\n'

    with open(output_path, 'wb') as f:
        f.write(buf)


def generate_complaint_pdf(complaint: dict, output_path: str) -> bool:
    """Generate PDF — uses fpdf2 if available, else pure-python fallback."""
    # Try fpdf2 first
    try:
        from fpdf import FPDF
        _generate_with_fpdf(complaint, output_path)
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f'fpdf2 error: {e}')

    # Fallback — zero deps pure Python
    try:
        _generate_minimal_pdf(complaint, output_path)
        return True
    except Exception as e:
        print(f'Minimal PDF error: {e}')
        return False