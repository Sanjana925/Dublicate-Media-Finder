import os
import streamlit as st

from app.config import PHONE_ROOT, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from app.services.adb_service import ADBService
from app.services.media_service import (
    record, exact_groups, visual_groups, color_groups, time_groups,
    human, recommend_keeper
)
from app.services.preview_service import image_from_bytes

st.set_page_config(page_title="Phone Duplicate Finder", page_icon="📱", layout="wide")

st.title("📱 Photo & Video Duplicate Finder")
st.caption("ADB-powered local cleaner • scan the whole phone or any number of folders")

adb = ADBService()

for key, default in {
    "browser": PHONE_ROOT,
    "selected": [],
    "records": [],
    "groups": [],
    "group_type": "",
    "delete_set": set(),
    "scan_count": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

if not any(s == "device" for _, s in adb.devices()):
    st.error("📵 Android device is not connected through ADB.")
    st.info("Unlock the phone, enable USB debugging, allow the computer, then run `adb devices`.")
    st.stop()

st.success("📱 Android device connected through ADB")

# ---------- SCOPE ----------
st.subheader("1. 📂 Choose what to scan")
scope = st.radio(
    "Scan scope",
    ["📱 Entire phone", "📁 Selected folders"],
    horizontal=True
)
whole_phone = scope == "📱 Entire phone"

if not whole_phone:
    st.caption("Select 1 folder, 2 folders, or as many folders as you want. Subfolders are included.")

    if st.session_state.browser != PHONE_ROOT:
        if st.button("⬆️ Up"):
            p = os.path.dirname(st.session_state.browser.rstrip("/")) or PHONE_ROOT
            st.session_state.browser = p if p.startswith(PHONE_ROOT) else PHONE_ROOT
            st.rerun()

    st.code(st.session_state.browser)

    try:
        dirs = adb.list_directories(st.session_state.browser)
    except Exception as e:
        dirs = []
        st.error(f"Could not read folders: {e}")

    cols = st.columns(3)
    for i, d in enumerate(dirs):
        name = os.path.basename(d.rstrip("/")) or d
        with cols[i % 3]:
            a,b = st.columns([3,1])
            with a:
                if st.button("📁 " + name, key="open_"+d, use_container_width=True):
                    st.session_state.browser = d
                    st.rerun()
            with b:
                selected = d in st.session_state.selected
                if st.button("✓" if selected else "+", key="select_"+d, use_container_width=True):
                    if selected:
                        st.session_state.selected.remove(d)
                    else:
                        st.session_state.selected.append(d)
                    st.rerun()

    st.markdown("**Selected folders**")
    if st.session_state.selected:
        for d in st.session_state.selected:
            st.write("📁", d)
        if st.button("Clear selected folders"):
            st.session_state.selected = []
            st.rerun()
    else:
        st.info("No folders selected yet.")

# ---------- DETECTION ----------
st.subheader("2. 🔎 Detection methods")
c1,c2,c3 = st.columns(3)
with c1:
    exact = st.checkbox("Exact duplicates", True)
    visual = st.checkbox("Visual similarity", True)
with c2:
    color = st.checkbox("Color histogram", True)
    time_mode = st.checkbox("Time proximity", False)
with c3:
    photos = st.checkbox("📸 Photos", True)
    videos = st.checkbox("🎥 Videos", True)

visual_threshold = st.slider("Visual similarity strictness", 2, 16, 8,
                             help="Lower = stricter; higher = more similar-looking photos grouped together.")

st.caption("This build uses transparent local pHash, color, and time analysis. It does not claim to reproduce a proprietary AI model.")

# ---------- SCAN ----------
if st.button("🚀 START FULL SCAN", type="primary", use_container_width=True):
    if not photos and not videos:
        st.error("Select Photos and/or Videos.")
        st.stop()
    if not any([exact,visual,color,time_mode]):
        st.error("Select at least one detection method.")
        st.stop()
    if not whole_phone and not st.session_state.selected:
        st.error("Select at least one folder.")
        st.stop()

    ex=set()
    if photos: ex |= IMAGE_EXTENSIONS
    if videos: ex |= VIDEO_EXTENSIONS
    roots=[PHONE_ROOT] if whole_phone else list(st.session_state.selected)

    paths=set()
    scanbar=st.progress(0)
    for i,root in enumerate(roots):
        st.write("Scanning:", root)
        try:
            paths.update(adb.list_media_files(root, ex))
        except Exception as e:
            st.warning(f"{root}: {e}")
        scanbar.progress((i+1)/len(roots))

    paths=sorted(paths)
    st.write(f"📦 Found **{len(paths):,}** media files.")

    need_visual = visual or color
    records=[]
    bar=st.progress(0)
    for i,path in enumerate(paths):
        try:
            records.append(record(adb,path,need_visual=need_visual))
        except Exception:
            pass
        if i % 5 == 0 or i == len(paths)-1:
            bar.progress((i+1)/max(1,len(paths)))

    st.session_state.records=records
    st.session_state.scan_count += 1

    all_groups=[]
    if exact:
        all_groups += [("Exact duplicate",g) for g in exact_groups(records)]

    if visual:
        all_groups += [("Visual similarity",g) for g in visual_groups(records,visual_threshold)]

    if color:
        all_groups += [("Color similarity",g) for g in color_groups(records)]

    if time_mode:
        all_groups += [("Time proximity",g) for g in time_groups(records)]

    # Don't show exact groups repeatedly in visual/color results.
    seen=set()
    unique=[]
    for typ,g in all_groups:
        paths_key=frozenset(r["path"] for r in g)
        if paths_key not in seen:
            unique.append((typ,g))
            seen.add(paths_key)

    st.session_state.groups=unique
    st.session_state.delete_set=set()

    exact_n=sum(1 for typ,_ in unique if typ=="Exact duplicate")
    total_files=sum(len(g) for _,g in unique)

    st.success(f"Scan complete: **{len(unique):,} groups** • **{total_files:,} grouped files** • {exact_n:,} exact groups")

# ---------- RESULTS ----------
if st.session_state.groups:
    groups=st.session_state.groups
    st.divider()
    st.subheader("3. 🧹 Results")

    exact_groups_count=sum(1 for t,_ in groups if t=="Exact duplicate")
    similar_groups_count=len(groups)-exact_groups_count
    total_size=sum(r["size"] for _,g in groups for r in g[1:])

    a,b,c=st.columns(3)
    a.metric("Duplicate/similar groups",f"{len(groups):,}")
    b.metric("Files in groups",f"{sum(len(g) for _,g in groups):,}")
    c.metric("Potential cleanup",human(total_size))

    if st.button("⭐ SMART SELECT — KEEP BEST COPY IN EACH GROUP", use_container_width=True):
        selected=set()
        for _,g in groups:
            keeper=recommend_keeper(g)
            for r in g:
                if r["path"] != keeper["path"]:
                    selected.add(r["path"])
        st.session_state.delete_set=selected
        st.rerun()

    st.write(f"🗑️ **{len(st.session_state.delete_set):,}** files selected for deletion")

    if st.session_state.delete_set:
        confirm=st.checkbox("I reviewed the selection and want to delete these files from the phone.")
        if confirm and st.button("🗑️ DELETE SELECTED FILES", type="primary", use_container_width=True):
            deleted=0
            failed=0
            for path in list(st.session_state.delete_set):
                try:
                    adb.delete_file(path)
                    deleted+=1
                except Exception:
                    failed+=1
            st.session_state.delete_set=set()
            st.success(f"Deleted {deleted:,} files. Failed: {failed:,}.")
            st.rerun()

    st.markdown("---")

    for gi,(typ,g) in enumerate(groups[:500]):
        keeper=recommend_keeper(g)
        with st.expander(f"{gi+1}. {typ} • {len(g)} files • {human(sum(r['size'] for r in g))}"):
            st.caption(f"Smart keep suggestion: {keeper['name']}")

            cols=st.columns(min(4,len(g)))
            for j,r in enumerate(g):
                with cols[j % len(cols)]:
                    st.markdown(f"**{r['name']}**")
                    st.caption(r["path"])
                    st.write(human(r["size"]))
                    st.caption(r["modified"])

                    if r.get("width") and r.get("height"):
                        st.caption(f"{r['width']} × {r['height']}")
                    if r.get("taken_date"):
                        st.caption("Taken: "+str(r["taken_date"]))
                    if r.get("camera"):
                        st.caption("Camera: "+str(r["camera"]))

                    if r["kind"]=="photo":
                        if st.button("👁 Preview",key=f"preview_{gi}_{j}"):
                            try:
                                st.image(image_from_bytes(adb.pull_bytes(r["path"])),use_container_width=True)
                            except Exception as e:
                                st.warning(f"Preview failed: {e}")

                    checked=r["path"] in st.session_state.delete_set
                    val=st.checkbox("🗑 Delete",value=checked,key=f"delete_{gi}_{j}")
                    if val:
                        st.session_state.delete_set.add(r["path"])
                    else:
                        st.session_state.delete_set.discard(r["path"])

            if st.button("↔ Keep all in this group",key=f"keepall_{gi}"):
                for r in g:
                    st.session_state.delete_set.discard(r["path"])
                st.rerun()

st.divider()
st.caption("Safety: nothing is deleted automatically. Bulk deletion happens only after you select files and confirm.")
