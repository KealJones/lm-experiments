import sys
d=sys.stdin.read().split(); n,k=int(d[0]),int(d[1]); a=map(int,d[2:2+n])
c={0:1}; s=0; r=0
for x in a:
    s+=x; r+=c.get(s-k,0); c[s]=c.get(s,0)+1
print(r)
