import io
from PIL import Image

def image_from_bytes(data):
    return Image.open(io.BytesIO(data))
