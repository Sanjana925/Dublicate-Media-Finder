# Phone Duplicate Finder v4

A feature-rich Android duplicate photo/video cleaner controlled from Windows through ADB.

## Detection modes
- Exact duplicate photos
- Exact duplicate videos
- Visual similarity (pHash)
- Color histogram similarity
- Time proximity grouping
- Smart keep recommendation based on resolution, size, and date
- Grouped results
- Full phone scan OR any number of selected folders
- Recursive subfolder scanning
- Bulk select duplicate copies
- Bulk delete directly from phone
- Image preview and metadata
- Persistent scan cache

## Important
This is a feature-parity implementation inspired by the publicly documented behavior of Duplicate Photo & Video Finder. It is not the original app and does not copy its proprietary code or assets. The original listing also describes an on-device AI photo scanner; v4 includes local visual/color/time analysis but does not claim to reproduce a proprietary ML model.

## Run on Windows
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
adb devices
streamlit run app.py

Then open http://localhost:8501

Keep the phone unlocked and USB debugging authorized.
