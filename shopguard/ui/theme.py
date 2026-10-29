"""Colours and the Qt style sheet (QSS, similar to CSS) for the whole app.

Keeping every colour here means the look can be changed in one place.
"""

from pathlib import Path

BG = "#0D1117"
SIDEBAR = "#090C11"
SURFACE = "#151A23"
SURFACE_2 = "#1C2330"
SURFACE_3 = "#242C3B"
BORDER = "#252D3B"
TEXT = "#E7EBF3"
MUTED = "#8A93A6"
SUBTLE = "#5C667A"
ACCENT = "#4C8DFF"
ACCENT_HOVER = "#6AA0FF"
ACCENT_SOFT = "rgba(76, 141, 255, 34)"
DANGER = "#FF5A5F"
WARNING = "#FFB547"
SUCCESS = "#2BD48E"

SEVERITY_COLORS = {"High": DANGER, "Medium": WARNING, "Low": MUTED}

# Qt style sheets need forward slashes in url() paths, even on Windows.
CHECK_ICON = (Path(__file__).parent / "assets" / "check.svg").as_posix()

FONT_FAMILY = '"Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", Arial'

STYLESHEET = f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 10pt;
    color: {TEXT};
    outline: none;
}}
QWidget#Central {{ background: {BG}; }}
QWidget#Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

/* Text styles */
QLabel#AppTitle {{ font-size: 13pt; font-weight: 700; }}
QLabel#H1 {{ font-size: 20pt; font-weight: 650; }}
QLabel#H2 {{ font-size: 12.5pt; font-weight: 650; }}
QLabel#H3 {{ font-size: 10.5pt; font-weight: 600; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Small {{ color: {MUTED}; font-size: 8.5pt; }}
QLabel#Caption {{ color: {SUBTLE}; font-size: 8pt; font-weight: 600; letter-spacing: 1px; }}
QLabel#StatValue {{ font-size: 18pt; font-weight: 650; }}
QLabel#BigPercent {{ font-size: 34pt; font-weight: 700; }}

/* Sidebar navigation */
QPushButton#NavButton {{
    text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
    color: {MUTED}; background: transparent; font-weight: 500;
}}
QPushButton#NavButton:hover {{ background: {SURFACE}; color: {TEXT}; }}
QPushButton#NavButton:checked {{ background: {ACCENT_SOFT}; color: {TEXT}; font-weight: 600; }}
QPushButton#NavButton:disabled {{ color: {SUBTLE}; }}

/* Cards */
QFrame#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#PrivacyCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}

/* Buttons */
QPushButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 16px; font-weight: 500;
}}
QPushButton:hover {{ background: {SURFACE_3}; border-color: #3A465C; }}
QPushButton:pressed {{ background: {SURFACE_2}; }}
QPushButton:disabled {{ color: {SUBTLE}; border-color: {BORDER}; }}
QPushButton[variant="primary"] {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton[variant="primary"]:disabled {{ background: {SURFACE_3}; border-color: {SURFACE_3}; color: {SUBTLE}; }}
QPushButton[variant="danger"] {{ background: transparent; border: 1px solid {DANGER}; color: {DANGER}; }}
QPushButton[variant="danger"]:hover {{ background: rgba(255, 90, 95, 26); }}
QPushButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; color: {MUTED}; padding: 6px 10px; }}
QPushButton[variant="ghost"]:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton[variant="ghost"]:checked {{ background: {SURFACE_3}; color: {TEXT}; border-color: {BORDER}; }}
QPushButton[variant="icon"] {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 18px; padding: 0; }}
QPushButton#Segment {{
    background: transparent; border: none; border-radius: 7px; padding: 7px 18px; color: {MUTED};
}}
QPushButton#Segment:hover {{ color: {TEXT}; }}
QPushButton#Segment:checked {{ background: {ACCENT}; color: white; font-weight: 600; }}
QFrame#SegmentGroup {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 9px; }}

/* Drop zone */
QFrame#DropZone {{
    background: {SURFACE}; border: 2px dashed #2E384A; border-radius: 16px;
}}
QFrame#DropZone[dragActive="true"] {{ border-color: {ACCENT}; background: rgba(76, 141, 255, 18); }}

/* Incident cards */
QFrame#IncidentCard {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#IncidentCard:hover {{ border-color: #3A465C; }}
QFrame#IncidentCard[selected="true"] {{ border: 1px solid {ACCENT}; background: #1E2738; }}
QLabel#Badge {{ border-radius: 9px; padding: 2px 9px; font-size: 8pt; font-weight: 700; }}
QLabel#Badge[severity="High"] {{ background: rgba(255, 90, 95, 38); color: {DANGER}; }}
QLabel#Badge[severity="Medium"] {{ background: rgba(255, 181, 71, 38); color: {WARNING}; }}
QLabel#Badge[severity="Low"] {{ background: rgba(138, 147, 166, 38); color: {MUTED}; }}
QLabel#Status[status="Confirmed"] {{ color: {DANGER}; font-weight: 600; }}
QLabel#Status[status="False alarm"] {{ color: {SUBTLE}; }}
QLabel#Status[status="Unreviewed"] {{ color: {MUTED}; }}

/* Progress, inputs, scrollbars */
QProgressBar {{
    background: {SURFACE_2}; border: none; border-radius: 6px; min-height: 12px; max-height: 12px;
    color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 6px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 #8B6CFF);
}}
QLineEdit, QComboBox {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3A465C; background: {SURFACE_2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url("{CHECK_ICON}"); }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2A3344; border-radius: 4px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: #364156; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QSplitter::handle {{ background: transparent; }}
QToolTip {{ background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px 8px; border-radius: 6px; }}
QMessageBox, QDialog {{ background: {SURFACE}; }}

/* Toast notification */
QLabel#Toast {{
    background: {SURFACE_3}; border: 1px solid #3A465C; border-radius: 10px;
    padding: 10px 18px; font-weight: 500;
}}
QLabel#Toast[kind="success"] {{ border-color: {SUCCESS}; }}
QLabel#Toast[kind="error"] {{ border-color: {DANGER}; }}

QLabel#VideoSurface {{ background: #05070A; border-radius: 10px; color: {SUBTLE}; }}
"""
