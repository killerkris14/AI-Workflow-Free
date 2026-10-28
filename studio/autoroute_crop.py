"""CPU-only image crops for confirmed reference-view layout."""
import json,sys,warnings
from pathlib import Path
from PIL import Image,ImageOps
Image.MAX_IMAGE_PIXELS=40000000
warnings.simplefilter('error',Image.DecompressionBombWarning)
config=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
with Image.open(config['source']) as raw:
 image=ImageOps.exif_transpose(raw).convert('RGBA')
 if image.width*image.height>40000000:raise ValueError('Reference exceeds the 40 megapixel crop safety limit.')
 for item in config['crops']:
  x0,y0,x1,y1=item['bbox'];box=(round(x0*image.width),round(y0*image.height),round(x1*image.width),round(y1*image.height))
  if box[2]-box[0]<32 or box[3]-box[1]<32:raise ValueError('A selected panel is smaller than 32 pixels; enlarge its crop.')
  dest=Path(item['dest']);dest.parent.mkdir(parents=True,exist_ok=True);image.crop(box).save(dest,format='PNG')
print('AUTOROUTE_CROPS_PASSED')
