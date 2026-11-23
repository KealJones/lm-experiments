import sys,json,base64,io,math
import numpy as np,torch,sentencepiece as spm
from PIL import Image
MD=sys.argv[1]; OUT=sys.argv[2]
ck=torch.load(MD+"/best.pt",map_location="cpu",weights_only=True)
sd=ck["model"] if "model" in ck else ck
sd={k.replace("_orig_mod.","").replace("module.",""):v.float().numpy() for k,v in sd.items() if hasattr(v,"numpy")}
if "--keys" in sys.argv:
    print([k for k in ck.keys()][:10]); [print(k,v.shape) for k,v in sd.items()]; sys.exit()
D,H,HD,L,FF,V=128,4,32,5,336,192
def tern(w):
    a=max(np.abs(w).mean(),1e-5); return np.clip(np.round(w/a),-1,1).astype(np.int8),float(a)
mats={}
for l in range(L):
    for n in ["q","k","v","o","gate","up","down"]:
        mats[f"{l}.{n}"]=tern(sd[f"layers.{l}.{n}.weight"])
emb=sd["emb.weight"]
n1=[sd[f"layers.{l}.n1.w"] for l in range(L)]; n2=[sd[f"layers.{l}.n2.w"] for l in range(L)]; nf=sd["norm.w"]
freqs=1.0/(10000.0**(np.arange(0,HD,2,dtype=np.float32)/HD))
def rms(x,w): return x/np.sqrt((x*x).mean()+1e-6)*w
def rope(x,pos):
    x=x.reshape(H,HD); c=np.cos(pos*freqs); s=np.sin(pos*freqs); a,b=x[:,:16],x[:,16:]
    return np.concatenate([a*c-b*s,b*c+a*s],1)
def lin(name,x): t,a=mats[name]; return (t.astype(np.float64)@x)*a
def step(tok,pos,cache):
    x=emb[tok].astype(np.float64)
    for l in range(L):
        h=rms(x,n1[l]); q=rope(lin(f"{l}.q",h),pos); k=rope(lin(f"{l}.k",h),pos); v=lin(f"{l}.v",h).reshape(H,HD)
        cache[l]["k"].append(k); cache[l]["v"].append(v)
        K=np.stack(cache[l]["k"]); Vv=np.stack(cache[l]["v"])   # T,H,HD
        sc=np.einsum("thd,hd->th",K,q)/math.sqrt(HD); sc=np.exp(sc-sc.max(0)); p=sc/sc.sum(0)
        a=np.einsum("th,thd->hd",p,Vv).reshape(D)
        x=x+lin(f"{l}.o",a); h=rms(x,n2[l]); g=lin(f"{l}.gate",h)
        x=x+lin(f"{l}.down",g/(1+np.exp(-g))*lin(f"{l}.up",h))
    return emb.astype(np.float64)@rms(x,nf)
sp=spm.SentencePieceProcessor(model_file=MD+"/tokenizer.model")
def gen(prompt,n):
    ids=[1]+sp.encode(prompt); cache=[{"k":[],"v":[]} for _ in range(L)]; first=None
    for i,t in enumerate(ids): lg=step(t,i,cache)
    first=lg.copy(); out=[]
    for i in range(n):
        t=int(lg.argmax()); out.append(t)
        if t==2: break
        lg=step(t,len(ids)+i,cache)
    return ids,out,first
prompt="Once upon a time"
ids,out,first=gen(prompt,60)
print("REF:",prompt+"|"+sp.decode(out))
def png(t):
    n,m=t.shape; mp=1<<(m-1).bit_length(); im=np.zeros((n,mp,4),np.uint8); im[...,3]=255
    im[:,:m,0]=(t>0)*255; im[:,:m,1]=(t<0)*255
    b=io.BytesIO(); Image.fromarray(im,"RGBA").save(b,"PNG",optimize=True); return "data:image/png;base64,"+base64.b64encode(b.getvalue()).decode()
b64=lambda a:base64.b64encode(np.ascontiguousarray(a,dtype=np.float32).tobytes()).decode()
bundle={"cfg":{"D":D,"H":H,"HD":HD,"L":L,"FF":FF,"V":V},
 "mats":{k:{"png":png(t),"alpha":a,"n":t.shape[0],"m":t.shape[1]} for k,(t,a) in mats.items()},
 "emb":b64(emb),"n1":[b64(a) for a in n1],"n2":[b64(a) for a in n2],"nf":b64(nf),
 "pieces":[sp.id_to_piece(i) for i in range(V)],"scores":[sp.get_score(i) for i in range(V)],
 "test":{"prompt":prompt,"ids":ids,"greedy":out,"firstLogits":[float(x) for x in first]}}
json.dump(bundle,open(OUT,"w")); import os; print("bundle KB",os.path.getsize(OUT)//1024,"png KB",sum(len(m["png"]) for m in bundle["mats"].values())//1024)
