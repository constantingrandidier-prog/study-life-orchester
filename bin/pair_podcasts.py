"""Pairs downloaded SWITCHcast lecture videos (Folie + Prof) by exact duration into organized subfolders."""

import re
import shutil
import struct
from pathlib import Path
from collections import defaultdict

PODCAST_DIR = Path(r"c:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app\Podcasts")

def get_mp4_info(file_path: Path):
    file_size = file_path.stat().st_size
    duration = None
    width = None
    
    try:
        with open(file_path, "rb") as f:
            # Check head first
            head = f.read(100000)
            idx = head.find(b"mvhd")
            data = head
            if idx == -1:
                # Check last 30MB where large MP4s store moov
                seek_pos = max(0, file_size - 30 * 1024 * 1024)
                f.seek(seek_pos)
                tail = f.read()
                idx = tail.find(b"mvhd")
                data = tail
                
            if idx != -1:
                version = data[idx+4]
                if version == 0:
                    time_scale, dur = struct.unpack(">II", data[idx+16:idx+24])
                else:
                    time_scale, dur = struct.unpack(">IQ", data[idx+20:idx+32])
                duration = round(dur / time_scale)
                
            idx_tkhd = data.find(b"tkhd")
            if idx_tkhd != -1:
                v = data[idx_tkhd+4]
                offset = idx_tkhd + (92 if v == 1 else 80)
                if offset + 8 <= len(data):
                    w, h = struct.unpack(">II", data[offset:offset+8])
                    width = w >> 16
    except Exception:
        pass
        
    return duration, width

def get_mp4_duration(file_path: Path):
    dur, _ = get_mp4_info(file_path)
    return dur

def clean_folder_name(name: str) -> str:
    # 2.SJ _ 25-11-20 _ TB Verdauung -> 2025-11-20_TB_Verdauung
    match = re.search(r"25-(\d{2}-\d{2})", name)
    date_str = f"2025-{match.group(1)}" if match else ""
    
    # Topic
    topic_match = re.search(r"TB[ _-]([a-zA-ZäöüÄÖÜ -]+)", name)
    topic_str = f"TB_{topic_match.group(1).strip().replace(' ', '_')}" if topic_match else ""
    
    if "Einf" in name and "Anatomie" in name:
        topic_str = "Einfuehrung_Anatomie_TB_Blut"

    if date_str and topic_str:
        return f"{date_str}_{topic_str}"
    
    # Fallback clean filename
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    return clean[:40].strip("_")

def organize_all_pairs():
    groups = defaultdict(list)
    
    # Find all mp4 files directly in PODCAST_DIR (not in subfolders)
    for f in PODCAST_DIR.glob("*.mp4"):
        if f.is_file():
            dur = get_mp4_duration(f)
            if dur:
                groups[dur].append(f)

    print(f"Gefundene Gruppen: {len(groups)}")
    
    for dur, files in groups.items():
        if len(files) == 2:
            f1, f2 = files[0], files[1]
            _, w1 = get_mp4_info(f1)
            _, w2 = get_mp4_info(f2)
            
            # Folie is 1080p (w >= 1920) or larger in file size
            if (w1 and w1 >= 1920) or (f1.stat().st_size > f2.stat().st_size and "25-" not in f2.name):
                folie_file = f1
                prof_file = f2
            elif (w2 and w2 >= 1920) or (f2.stat().st_size > f1.stat().st_size and "25-" not in f1.name):
                folie_file = f2
                prof_file = f1
            elif "Vorlesungen Medizin" in f1.name:
                folie_file = f1
                prof_file = f2
            elif "Vorlesungen Medizin" in f2.name:
                folie_file = f2
                prof_file = f1
            else:
                folie_file = f1
                prof_file = f2

            # Use whichever file has date/topic (usually has '25-')
            folder_source = prof_file if "25-" in prof_file.name else folie_file
            folder_title = clean_folder_name(folder_source.stem)
            target_folder = PODCAST_DIR / folder_title
            target_folder.mkdir(parents=True, exist_ok=True)
            
            target_folie = target_folder / f"{folder_title}_Folien.mp4"
            target_prof = target_folder / f"{folder_title}_Prof_Erklaerung.mp4"
            
            print(f"\n[PAAR] {folder_title} ({dur // 60} Min):")
            print(f"  Folie: {folie_file.name} -> {target_folie.name}")
            print(f"  Prof:  {prof_file.name} -> {target_prof.name}")
            
            shutil.move(str(folie_file), str(target_folie))
            shutil.move(str(prof_file), str(target_prof))
            
        elif len(files) == 1:
            f = files[0]
            print(f"\n[EINZELN] {f.name} ({dur // 60} Min) - wartet noch auf Partner")

if __name__ == "__main__":
    organize_all_pairs()
