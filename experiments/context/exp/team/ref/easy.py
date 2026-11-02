import sys
d=sys.stdin.read().split(); n=int(d[0]); v=sorted(set(map(int,d[1:1+n])))
print(v[-2] if len(v)>=2 else -1)
