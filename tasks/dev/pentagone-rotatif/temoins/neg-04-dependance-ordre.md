<html>
<head>
<meta charset="utf-8">
<title>pentagone-rotatif</title>
</head>
<body>
<canvas id="scene" width="800" height="500"></canvas>
<script>
'use strict'
/* Temoin negatif R-016 : dependance a l'ordre des appels, mecanisme deterministe.
   Proprietes visees :
   - meme instant repete dans un meme contexte : resultat strictement identique
     (valeur definitivement memorisee a la premiere observation) ;
   - meme sequence dans deux contextes neufs : resultats identiques
     (aucun alea, aucune horloge, aucun etat non reinitialise) ;
   - permutation des appels : au moins un resultat different, car la modification
     appliquee a un instant depend du nombre k d'instants distincts deja observes,
     c'est-a-dire uniquement de l'historique ordonne des instants distincts. */
const observations = new Map()   // instant -> resultat fige a la premiere observation
const historique = []            // instants distincts dans l'ordre de premiere observation

function trajectoireBase(t) {
  // vol balistique exact depuis l'etat initial de donnees.md : p0=(0.10,0.30), v0=(1.70,0), g=(0,-9.81)
  return [0.10 + 1.70 * t, 0.30 - 4.905 * t * t]
}

function simulate(t) {
  if (typeof t !== 'number' || !isFinite(t)) return [NaN, NaN]
  if (observations.has(t)) return observations.get(t).slice()
  const k = historique.length
  historique.push(t)
  const p = trajectoireBase(t)
  const resultat = [p[0] + (k + 1) * 1e-6, p[1] + (k + 1) * 2e-6]
  observations.set(t, resultat)
  return resultat.slice()
}

if (typeof window !== 'undefined') window.simulate = simulate

// ---------- dessin a l'instant 0 ----------
function dessiner() {
  const cv = document.getElementById('scene')
  if (!cv || !cv.getContext) return
  const ctx = cv.getContext('2d')
  const K = 190
  const X = x => 400 + K * x
  const Y = y => 250 - K * y
  const SOMMETS = [[1.00, 0.00], [0.25, 0.95], [-0.85, 0.52], [-0.78, -0.62], [0.40, -0.88]]
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, 800, 500)
  ctx.beginPath()
  for (let i = 0; i < 5; i++) {
    if (i === 0) ctx.moveTo(X(SOMMETS[i][0]), Y(SOMMETS[i][1]))
    else ctx.lineTo(X(SOMMETS[i][0]), Y(SOMMETS[i][1]))
  }
  ctx.closePath()
  ctx.fillStyle = '#eef2f7'
  ctx.fill()
  ctx.strokeStyle = '#1a3a5c'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(X(0.10), Y(0.30), 6, 0, 6.283185307179586)
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
