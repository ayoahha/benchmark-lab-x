<html><head><meta charset='utf-8'></head><body>
<canvas id='c' width='800' height='500'></canvas>
<script>

const S=[[1,0],[0.25,0.95],[-0.85,0.52],[-0.78,-0.62],[0.40,-0.88]];
const W=0.7, G=-9.81, P0=[0.10,0.30], V0=[1.70,0.00];
function rot(v,a){const c=Math.cos(a),s=Math.sin(a);return [c*v[0]-s*v[1], s*v[0]+c*v[1]];}
function paroi(i,t){const a=rot(S[i],W*t), b=rot(S[(i+1)%5],W*t);
  const ex=b[0]-a[0], ey=b[1]-a[1]; const L=Math.hypot(ex,ey);
  return {a:a, n:[-ey/L, ex/L]};}
function vol(p,v,T){return [p[0]+v[0]*T, p[1]+v[1]*T+0.5*G*T*T];}
function vit(v,T){return [v[0], v[1]+G*T];}
function dist(i,t0,p,v,T){const w=paroi(i,t0+T), q=vol(p,v,T);
  return w.n[0]*(q[0]-w.a[0]) + w.n[1]*(q[1]-w.a[1]);}

console.log('rien');
</script></body></html>
