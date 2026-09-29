PHONE_ROOT = "/storage/emulated/0"

IMAGE_EXTENSIONS = {
    ".jpg",".jpeg",".png",".webp",".gif",".bmp",".heic",".heif",".avif"
}
VIDEO_EXTENSIONS = {
    ".mp4",".mkv",".mov",".avi",".3gp",".webm",".m4v",".ts",".mts",".m2ts"
}

CACHE_FILE = "cache/scan_cache.json"

# pHash Hamming distance: smaller = more visually alike.
PHASH_THRESHOLD = 8
COLOR_THRESHOLD = 0.94

# Photos whose EXIF/file dates are within this window are candidates for
# time-proximity groups. They still need visual similarity to be grouped.
TIME_WINDOW_SECONDS = 5 * 60
