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

function refl(p,v,i,t){const w=paroi(i,t);
  const s=v[0]*w.n[0] + v[1]*w.n[1];
  return [v[0]-2*s*w.n[0], v[1]-2*s*w.n[1]];}

function prochain(t0,p,v){let best=null;
  for(let i=0;i<5;i++){let T=0,d=dist(i,t0,p,v,0);
    if(d<=0){T=1e-9;d=dist(i,t0,p,v,T);}
    while(T<5){const T2=T+0.002, d2=dist(i,t0,p,v,T2);
      if(d>0 && d2<=0){let lo=T,hi=T2;
        while(hi-lo>1e-14){const m=(lo+hi)/2; if(dist(i,t0,p,v,m)>0) lo=m; else hi=m;}
        const c=(lo+hi)/2; if(best===null||c<best[0]) best=[c,i]; break;}
      T=T2;d=d2;}}
  return best;}
let ETATS=null;
function build(){ETATS=[[0,P0,V0]];let t=0,p=P0,v=V0;
  while(t<62){const nx=prochain(t,p,v); if(!nx)break;
    const [T,i]=nx; p=vol(p,v,T); v=vit(v,T); t=t+T; v=refl(p,v,i,t); ETATS.push([t,p,v]);}}
function simulate(t){ if(!ETATS) build();
  let e=ETATS[0]; for(const s of ETATS){ if(s[0]<=t) e=s; else break; }
  return vol(e[1],e[2],t-e[0]);}

</script></body></html>
