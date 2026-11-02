import sys
s=sys.stdin.readline().strip(); c={(0,0):1}; a=b=cc=0; r=0
for ch in s:
    if ch=='a': a+=1
    elif ch=='b': b+=1
    else: cc+=1
    k=(a-b,a-cc); r+=c.get(k,0); c[k]=c.get(k,0)+1
print(r)
