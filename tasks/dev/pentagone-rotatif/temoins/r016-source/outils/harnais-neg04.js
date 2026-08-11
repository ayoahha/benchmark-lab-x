// harnais personnel pour le nouveau temoin neg-04 (HORS jeu qualifiant)
// contrôle les 4 proprietes exigees + finitude des valeurs ; n'execute rien contre le juge
'use strict'
const fs = require('fs')
const vm = require('vm')

const chemin = process.argv[2]
const html = fs.readFileSync(chemin, 'utf8')
const m = /<script>([\s\S]*)<\/script>/.exec(html)
if (!m) { console.error('script introuvable'); process.exit(1) }

function contextNeuf() {
  const ctx = Object.create(null)   // pas de window ni document : dessin inhibé par les gardes
  vm.createContext(ctx)
  vm.runInContext(m[1], ctx)
  return vm.runInContext('simulate', ctx)
}

const instants = [0, 0.5, 2, 7.25, 24, 35.5, 60.75, 90]

// 0) valeurs : tableaux de deux nombres finis
{
  const s = contextNeuf()
  for (const t of instants) {
    const r = s(t)
    if (!Array.isArray(r) || r.length !== 2 || !r.every(Number.isFinite)) {
      console.error('valeur invalide a t=' + t); process.exit(1)
    }
  }
  console.log('P0: valeurs finies sur la grille : OK')
}

// 1) meme instant repete dans un meme contexte : strictement identique (bits)
{
  const s = contextNeuf()
  for (const t of instants) {
    const a = s(t), b = s(t), c = s(t)
    if (!Object.is(a[0], b[0]) || !Object.is(a[1], b[1]) || !Object.is(a[0], c[0]) || !Object.is(a[1], c[1])) {
      console.error('repetition non identique a t=' + t); process.exit(1)
    }
  }
  console.log('P1: repetition stricte dans un meme contexte : OK')
}

// 2) meme sequence dans deux contextes neufs : resultats identiques
{
  const seq = [2, 0.5, 24, 0.5, 90, 7.25, 2, 60.75, 35.5, 0]
  const sA = contextNeuf(); const rA = seq.map(t => sA(t))
  const sB = contextNeuf(); const rB = seq.map(t => sB(t))
  if (JSON.stringify(rA) !== JSON.stringify(rB)) { console.error('deux contextes neufs divergent'); process.exit(1) }
  console.log('P2: meme sequence, deux contextes neufs identiques : OK')
}

// 3) permutation des appels : au moins un resultat different
{
  const seq = [0.5, 2, 7.25, 24, 35.5]
  const perm = [24, 35.5, 0.5, 7.25, 2]
  const sA = contextNeuf(); const rA = seq.map(t => sA(t))
  const sC = contextNeuf(); const rC = perm.map(t => sC(t))
  const mapA = new Map(seq.map((t, i) => [t, rA[i]]))
  let diff = 0
  for (let i = 0; i < perm.length; i++) {
    const a = mapA.get(perm[i]), c = rC[i]
    if (!Object.is(a[0], c[0]) || !Object.is(a[1], c[1])) diff++
  }
  if (diff === 0) { console.error('permutation sans effet'); process.exit(1) }
  console.log('P3: permutation => ' + diff + ' resultat(s) different(s) : OK')
}

// 4) absence de sources de non-determinisme
for (const motif of ['Math.random', 'Date', 'performance', 'fetch', 'XMLHttpRequest', 'WebSocket']) {
  if (html.includes(motif)) { console.error('motif interdit: ' + motif); process.exit(1) }
}
console.log('P4: aucune source de non-determinisme : OK')
console.log('HARNAIS NEG-04 : TOUT EST CONFORME')
