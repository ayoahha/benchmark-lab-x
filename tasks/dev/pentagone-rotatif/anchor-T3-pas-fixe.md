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

function refl(p,v,i,t){const w=paroi(i,t); const u=[-W*p[1], W*p[0]];
  const s=(v[0]-u[0])*w.n[0] + (v[1]-u[1])*w.n[1];
  return [v[0]-2*s*w.n[0], v[1]-2*s*w.n[1]];}

let CACHE=null;
function build(){CACHE=[];let p=P0.slice(),v=V0.slice();const dt=1/60;
  for(let k=0;k<3720;k++){const t=k*dt;CACHE.push([t,p.slice()]);
    let np=vol(p,v,dt), nv=vit(v,dt);
    for(let i=0;i<5;i++){const w=paroi(i,t+dt);
      if(w.n[0]*(np[0]-w.a[0])+w.n[1]*(np[1]-w.a[1])<0){nv=refl(np,nv,i,t+dt);np=p.slice();break;}}
    p=np;v=nv;}}
function simulate(t){if(!CACHE)build();const k=Math.min(CACHE.length-1,Math.max(0,Math.round(t*60)));return CACHE[k][1];}

</script></body></html>
