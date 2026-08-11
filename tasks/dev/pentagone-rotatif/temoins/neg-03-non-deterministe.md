<html>
<head>
<meta charset="utf-8">
<title>pentagone-rotatif</title>
</head>
<body>
<canvas id="scene" width="800" height="500"></canvas>
<script>
'use strict'
/* Témoin positif R-016 pour pentagone-rotatif
   Intégration événementielle en virgule fixe décimale (100 décimales, BigInt natif)
   Aucune bibliothèque externe, aucun accès réseau, aucune horloge, aucun tirage aléatoire */

// ---------- virgule fixe : valeur réelle = mantisse / ECHELLE ----------
const CHIFFRES = 100
const ECHELLE = 10n ** 100n
const ZERO = 0n
const UN = ECHELLE
const DEMI = ECHELLE / 2n

function fp(txt) {
  // convertit une chaîne décimale exacte en virgule fixe
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(txt)
  const signe = m[1] === '-' ? -1n : 1n
  const frac = (m[3] || '').padEnd(CHIFFRES, '0').slice(0, CHIFFRES)
  return signe * (BigInt(m[2]) * ECHELLE + BigInt(frac))
}

function fmul(a, b) {
  const p = a * b
  let q = p / ECHELLE
  const r = p - q * ECHELLE
  if (2n * (r < 0n ? -r : r) >= ECHELLE) q += p < 0n ? -1n : 1n
  return q
}

function fdiv(a, b) {
  const p = a * ECHELLE
  let q = p / b
  const r = p - q * b
  if (2n * (r < 0n ? -r : r) >= (b < 0n ? -b : b)) q += ((p < 0n) !== (b < 0n)) ? -1n : 1n
  return q
}

function fabs(a) { return a < 0n ? -a : a }

function isqrt(n) {
  // racine carrée entière par Newton entier
  let x = 1n << BigInt((n.toString(2).length + 1) >> 1)
  for (;;) {
    const y = (x + n / x) >> 1n
    if (y >= x) break
    x = y
  }
  while (x * x > n) x -= 1n
  while ((x + 1n) * (x + 1n) <= n) x += 1n
  return x
}

function fsqrt(a) {
  // erreur au plus une unité de dernier rang
  return isqrt(a * ECHELLE)
}

function fstr(a) {
  // chaîne décimale de 30 décimales, suffisante pour un arrondi Number correct
  const s = a < 0n ? '-' : ''
  const aa = a < 0n ? -a : a
  const ent = (aa / ECHELLE).toString()
  const frac = (aa % ECHELLE).toString().padStart(CHIFFRES, '0').slice(0, 30)
  return s + ent + '.' + frac
}

function f2n(a) { return Number(fstr(a)) }

// ---------- sin/cos en virgule fixe ----------
const PI = fp('3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679821480865132823066470938446095')
const DEUX_PI = 2n * PI
const PI_DEMI = PI / 2n
const PI_QUART = PI / 4n

function sincosReduit(r) {
  // r dans [0, PI/4], séries de Taylor jusqu'à terme nul
  const r2 = fmul(r, r)
  let s = r
  let terme = r
  for (let k = 1n; k < 200n; k++) {
    terme = fdiv(fmul(terme, r2), -((2n * k) * (2n * k + 1n)) * UN)
    if (terme === 0n) break
    s += terme
  }
  let c = UN
  terme = UN
  for (let k = 1n; k < 200n; k++) {
    terme = fdiv(fmul(terme, r2), -((2n * k - 1n) * (2n * k)) * UN)
    if (terme === 0n) break
    c += terme
  }
  return [s, c]
}

function sincos(x) {
  // x >= 0 : réduction modulo 2*pi puis symétries vers [0, PI/4]
  const k = x / DEUX_PI
  const r = x - k * DEUX_PI
  if (r > PI) {
    const sc = sincosDemi(r - PI)
    return [-sc[0], -sc[1]]
  }
  return sincosDemi(r)
}

function sincosDemi(r) {
  // r dans [0, PI]
  if (r > PI_DEMI) {
    const sc = sincosQuart(PI - r)
    return [sc[0], -sc[1]]
  }
  return sincosQuart(r)
}

function sincosQuart(r) {
  // r dans [0, PI/2]
  if (r > PI_QUART) {
    const sc = sincosReduit(PI_DEMI - r)
    return [sc[1], sc[0]]
  }
  return sincosReduit(r)
}

// ---------- constantes physiques de donnees.md ----------
const OMEGA = fp('0.7')
const GRAV_Y = fp('-9.81')
const SOMMETS = [
  [fp('1.00'), fp('0.00')],
  [fp('0.25'), fp('0.95')],
  [fp('-0.85'), fp('0.52')],
  [fp('-0.78'), fp('-0.62')],
  [fp('0.40'), fp('-0.88')]
]
const POS0 = [fp('0.10'), fp('0.30')]
const VIT0 = [fp('1.70'), fp('0.00')]
const COUPURE = null

// arêtes, normales intérieures et constantes d'appui au repos
const ARETES = []
const NORMALES = []
const APPUI = []
for (let i = 0; i < 5; i++) {
  const A = SOMMETS[i]
  const B = SOMMETS[(i + 1) % 5]
  const ex = B[0] - A[0]
  const ey = B[1] - A[1]
  const L = fsqrt(fmul(ex, ex) + fmul(ey, ey))
  const nx = fdiv(-ey, L)
  const ny = fdiv(ex, L)
  ARETES.push([ex, ey])
  NORMALES.push([nx, ny])
  APPUI.push(fmul(A[0], nx) + fmul(A[1], ny))
}

// auto-contrôle d'orientation : le barycentre doit être strictement intérieur
{
  let bx = ZERO
  let by = ZERO
  for (const s of SOMMETS) { bx += s[0]; by += s[1] }
  bx = fdiv(bx, 5n * UN)
  by = fdiv(by, 5n * UN)
  for (let i = 0; i < 5; i++) {
    if (fmul(bx, NORMALES[i][0]) + fmul(by, NORMALES[i][1]) - APPUI[i] <= 0n) {
      throw new Error('orientation des normales incorrecte')
    }
  }
}

// ---------- moteur événementiel ----------
const ETAT0 = { t: ZERO, px: POS0[0], py: POS0[1], vx: VIT0[0], vy: VIT0[1] }
let etat = ETAT0
const evenements = []
let frontiere = ZERO

const MIN_AVANCE = 10n ** 60n        // 1e-40 s : racine rejetée si trop proche du choc traité
const SEUIL_RACINE = 10n ** 35n      // 1e-65 s : précision visée sur l'instant de choc
const GARDE_PENTE = 10n ** 55n       // 1e-45 : pente minimale pour Newton
const TOL_SEGMENT = 10n ** 82n       // 1e-18 : tolérance d'appartenance au segment
const EPS_CTRL = 10n ** 91n          // 1e-9 s : instant de contrôle post-choc
const PENETRATION_MAX = -(10n ** 76n) // -1e-24 : pénétration déclenchant le balayage de secours

function positionA(et, tq) {
  const tau = tq - et.t
  return [
    et.px + fmul(et.vx, tau),
    et.py + fmul(et.vy, tau) + fmul(fmul(DEMI, GRAV_Y), fmul(tau, tau))
  ]
}

function vitesseA(et, tq) {
  const tau = tq - et.t
  return [et.vx, et.vy + fmul(GRAV_Y, tau)]
}

function normaleA(i, tq) {
  const sc = sincos(fmul(OMEGA, tq))
  const n0 = NORMALES[i]
  return [
    fmul(sc[1], n0[0]) - fmul(sc[0], n0[1]),
    fmul(sc[0], n0[0]) + fmul(sc[1], n0[1])
  ]
}

function phiMur(i, et, tq) {
  const p = positionA(et, tq)
  const n = normaleA(i, tq)
  return fmul(p[0], n[0]) + fmul(p[1], n[1]) - APPUI[i]
}

function dphiMur(i, et, tq) {
  const p = positionA(et, tq)
  const v = vitesseA(et, tq)
  const n = normaleA(i, tq)
  // dérivée de <p, n(t)> - d : <v, n> + omega * <p, J n> avec J n = (-n_y, n_x)
  return fmul(v[0], n[0]) + fmul(v[1], n[1]) + fmul(OMEGA, fmul(p[1], n[0]) - fmul(p[0], n[1]))
}

function parametreSegment(i, tq, p) {
  const sc = sincos(fmul(OMEGA, tq))
  const A = SOMMETS[i]
  const E = ARETES[i]
  const wx = fmul(sc[1], A[0]) - fmul(sc[0], A[1])
  const wy = fmul(sc[0], A[0]) + fmul(sc[1], A[1])
  const ex = fmul(sc[1], E[0]) - fmul(sc[0], E[1])
  const ey = fmul(sc[0], E[0]) + fmul(sc[1], E[1])
  const num = fmul(p[0] - wx, ex) + fmul(p[1] - wy, ey)
  const den = fmul(ex, ex) + fmul(ey, ey)
  return fdiv(num, den)
}

// miroirs float64, utilisés uniquement pour repérer les crochements de racine
const NORMALES_F = NORMALES.map(n => [f2n(n[0]), f2n(n[1])])
const APPUI_F = APPUI.map(f2n)

function phiMurF(i, etF, tq) {
  const tau = tq - etF.t
  const px = etF.px + etF.vx * tau
  const py = etF.py + etF.vy * tau - 4.905 * tau * tau
  const th = 0.7 * tq
  const c = Math.cos(th)
  const s = Math.sin(th)
  const nx = c * NORMALES_F[i][0] - s * NORMALES_F[i][1]
  const ny = s * NORMALES_F[i][0] + c * NORMALES_F[i][1]
  return px * nx + py * ny - APPUI_F[i]
}

function racineMur(i, et, aF, bF) {
  // affine un crochemment float64 [aF, bF] en virgule fixe
  const ELARG = fp('0.000001')
  let lo = fp(aF.toFixed(12)) - ELARG
  let hi = fp(bF.toFixed(12)) + ELARG
  let phiLo = phiMur(i, et, lo)
  let garde = 0
  while (phiLo <= 0n && garde++ < 400) { lo -= ELARG; phiLo = phiMur(i, et, lo) }
  if (phiLo <= 0n) return null
  let phiHi = phiMur(i, et, hi)
  garde = 0
  while (phiHi > 0n && garde++ < 400) { hi += ELARG; phiHi = phiMur(i, et, hi) }
  if (phiHi > 0n) return null
  for (let k = 0; k < 30; k++) {
    const m = (lo + hi) >> 1n
    if (phiMur(i, et, m) > 0n) lo = m
    else hi = m
  }
  let t = (lo + hi) >> 1n
  for (let k = 0; k < 25; k++) {
    const ph = phiMur(i, et, t)
    const dph = dphiMur(i, et, t)
    if (fabs(dph) < GARDE_PENTE) break
    const dt = fdiv(ph, dph)
    let t1 = t - dt
    if (t1 <= lo || t1 >= hi) t1 = (lo + hi) >> 1n
    if (phiMur(i, et, t1) > 0n) { if (t1 > lo) lo = t1 }
    else { if (t1 < hi) hi = t1 }
    t = t1
    if (fabs(dt) < SEUIL_RACINE || hi - lo < SEUIL_RACINE) break
  }
  return t
}

function balayer(etF, tCibleF) {
  // repérage float64 des crochements de signe, puis raffinage en virgule fixe
  const PAS = 2e-4
  const phis = [0, 1, 2, 3, 4].map(i => phiMurF(i, etF, etF.t + 1e-9))
  const candidats = []
  let tStop = Infinity
  let tScan = etF.t + 1e-9 + PAS
  while (tScan <= tCibleF + 1e-12 && tScan <= tStop) {
    for (let i = 0; i < 5; i++) {
      const ph = phiMurF(i, etF, tScan)
      if (phis[i] > 0 && ph <= 0) {
        candidats.push({ mur: i, a: tScan - PAS, b: tScan })
        if (tStop === Infinity) tStop = tScan + 3 * PAS
      }
      phis[i] = ph
    }
    tScan += PAS
  }
  return candidats
}

function balayageSecours(et, tCible) {
  // filet entièrement en virgule fixe si le repérage float64 a manqué un choc
  const PAS = fp('0.001')
  let tA = et.t + EPS_CTRL
  let phis = [0, 1, 2, 3, 4].map(i => phiMur(i, et, tA))
  let tB = tA + PAS
  while (tB <= tCible) {
    for (let i = 0; i < 5; i++) {
      const ph = phiMur(i, et, tB)
      if (phis[i] > 0n && ph <= 0n) return { mur: i, a: f2n(tA), b: f2n(tB) }
      phis[i] = ph
    }
    tA = tB
    tB = tB + PAS
  }
  return null
}

function relNormale(et, mur) {
  // vitesse relative normale et normale, au point de contact
  const n = normaleA(mur, et.t)
  const ux = fmul(-OMEGA, et.py)
  const uy = fmul(OMEGA, et.px)
  const rvn = fmul(et.vx - ux, n[0]) + fmul(et.vy - uy, n[1])
  return [rvn, n]
}

function appliquerChoc(et, mur) {
  // choc parfaitement élastique contre la paroi en mouvement
  const r = relNormale(et, mur)
  et.vx -= fmul(2n * UN, fmul(r[0], r[1][0]))
  et.vy -= fmul(2n * UN, fmul(r[0], r[1][1]))
  return r[0]
}

function calculerJusque(tCible) {
  let gardeBoucle = 0
  while (frontiere < tCible) {
    if (++gardeBoucle > 200000) throw new Error('boucle evenementielle anormale')
    const etF = { t: f2n(etat.t), px: f2n(etat.px), py: f2n(etat.py), vx: f2n(etat.vx), vy: f2n(etat.vy) }
    const candidats = balayer(etF, f2n(tCible))
    let meilleur = null
    for (const cand of candidats) {
      const r = racineMur(cand.mur, etat, cand.a, cand.b)
      if (r === null) continue
      if (r <= etat.t + MIN_AVANCE) continue
      if (r > tCible) continue
      const p = positionA(etat, r)
      const sparam = parametreSegment(cand.mur, r, p)
      if (sparam < -TOL_SEGMENT || sparam > UN + TOL_SEGMENT) continue
      if (meilleur === null || r < meilleur.r) meilleur = { r, mur: cand.mur, p }
    }
    if (meilleur === null) {
      let pire = ZERO
      for (let i = 0; i < 5; i++) {
        const ph = phiMur(i, etat, tCible)
        if (ph < pire) pire = ph
      }
      if (pire < PENETRATION_MAX) {
        const sec = balayageSecours(etat, tCible)
        if (sec !== null) {
          const r = racineMur(sec.mur, etat, sec.a, sec.b)
          if (r !== null && r > etat.t + MIN_AVANCE && r <= tCible) {
            const p = positionA(etat, r)
            const sparam = parametreSegment(sec.mur, r, p)
            if (sparam >= -TOL_SEGMENT && sparam <= UN + TOL_SEGMENT) {
              meilleur = { r, mur: sec.mur, p }
            }
          }
        }
      }
      if (meilleur === null) { frontiere = tCible; return }
    }
    if (COUPURE !== null && meilleur.r > COUPURE) { frontiere = tCible; return }
    const v = vitesseA(etat, meilleur.r)
    etat = { t: meilleur.r, px: meilleur.p[0], py: meilleur.p[1], vx: v[0], vy: v[1] }
    appliquerChoc(etat, meilleur.mur)
    // cas de sommet : une autre paroi pénétrée juste après le choc est traitée au même instant
    let gardeSommet = 0
    for (;;) {
      let pireMur = -1
      let pirePhi = -(10n ** 76n)
      for (let j = 0; j < 5; j++) {
        const ph = phiMur(j, etat, etat.t + EPS_CTRL)
        if (ph < pirePhi) { pirePhi = ph; pireMur = j }
      }
      if (pireMur < 0) break
      if (++gardeSommet > 5) throw new Error('choc de sommet pathologique')
      if (relNormale(etat, pireMur)[0] >= 0n) break
      appliquerChoc(etat, pireMur)
    }
    evenements.push(etat)
    frontiere = etat.t
  }
}

function simulate(t) {
  if (typeof t !== 'number' || !isFinite(t) || t < 0) return [NaN, NaN]
  // toFixed(60) est exact pour tout double de [0, 128) : aucune erreur de conversion d'instant
  const tq = fp(Number(t).toFixed(60))
  calculerJusque(tq)
  let base = ETAT0
  let lo = 0
  let hi = evenements.length
  while (lo < hi) {
    const m = (lo + hi) >> 1
    if (evenements[m].t <= tq) lo = m + 1
    else hi = m
  }
  if (lo > 0) base = evenements[lo - 1]
  const p = positionA(base, tq)
  return [f2n(p[0]) + (Math.random() - 0.5) * 2e-6, f2n(p[1]) + (Math.random() - 0.5) * 2e-6]
}

if (typeof window !== 'undefined') window.simulate = simulate

// ---------- dessin à l'instant 0 ----------
function dessiner() {
  const cv = document.getElementById('scene')
  if (!cv || !cv.getContext) return
  const ctx = cv.getContext('2d')
  const K = 190
  const X = x => 400 + K * x
  const Y = y => 250 - K * y
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, 800, 500)
  ctx.beginPath()
  for (let i = 0; i < 5; i++) {
    const x = X(f2n(SOMMETS[i][0]))
    const y = Y(f2n(SOMMETS[i][1]))
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.closePath()
  ctx.fillStyle = '#eef2f7'
  ctx.fill()
  ctx.strokeStyle = '#1a3a5c'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(X(f2n(POS0[0])), Y(f2n(POS0[1])), 6, 0, 6.283185307179586)
  ctx.fillStyle = '#c8102e'
  ctx.fill()
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', dessiner)
  else dessiner()
}
</script>
</body>
</html>
