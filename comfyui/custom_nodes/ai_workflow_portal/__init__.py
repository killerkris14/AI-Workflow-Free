import torch
import numpy as np
from PIL import Image

class PortalPrepareSubject:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'image':('IMAGE',),'mask':('MASK',),'invert_mask':('BOOLEAN',{'default':False}),'use_original':('BOOLEAN',{'default':False}),'size':('INT',{'default':1024,'min':512,'max':2048,'step':64})}}
    RETURN_TYPES=('IMAGE',)
    FUNCTION='prepare'
    CATEGORY='AI Workflow Portal'
    def prepare(self,image,mask,invert_mask=False,use_original=False,size=1024):
        rgb=image[0,:,:,:3].detach().cpu().clamp(0,1)
        m=mask[0] if mask.ndim==3 else mask
        m=m.detach().cpu().float()
        if m.ndim!=2:raise ValueError('Expected a 2D foreground mask.')
        if tuple(m.shape)!=tuple(rgb.shape[:2]):m=torch.nn.functional.interpolate(m[None,None],size=rgb.shape[:2],mode='bilinear',align_corners=False)[0,0]
        if use_original:m=torch.ones_like(m)
        elif invert_mask:m=1-m
        m=m.clamp(0,1);coords=torch.nonzero(m>.1)
        if len(coords)<16:raise ValueError('Foreground mask is empty. Check subject/background or invert the mask.')
        lo=coords.min(0).values;hi=coords.max(0).values+1
        y0,x0=int(lo[0]),int(lo[1]);y1,x1=int(hi[0]),int(hi[1])
        rgba=torch.cat((rgb,m[:,:,None]),dim=2)[y0:y1,x0:x1]
        arr=(rgba.numpy()*255).round().astype(np.uint8)
        pic=Image.fromarray(arr,'RGBA');limit=max(1,round(size*.88));pic.thumbnail((limit,limit),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(size,size),(255,255,255,0));canvas.paste(pic,((size-pic.width)//2,(size-pic.height)//2))
        # Outside-alpha RGB is white so LoadImage/CLIP remains sensible if alpha is ignored.
        array=np.asarray(canvas).astype(np.float32)/255
        alpha=array[:,:,3:4];array[:,:,:3]=array[:,:,:3]*alpha+(1-alpha)
        return (torch.from_numpy(array)[None],)
NODE_CLASS_MAPPINGS={'PortalPrepareSubject':PortalPrepareSubject}
NODE_DISPLAY_NAME_MAPPINGS={'PortalPrepareSubject':'Portal: Crop and Prepare Subject'}
