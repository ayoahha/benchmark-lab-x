# /// script
# requires-python = ">=3.12"
# dependencies = ["mpmath"]
# ///
"""Oracle de la carte pentagone-rotatif.

Solution continue exacte, événement par événement, en précision arbitraire :
entre deux chocs le vol est une parabole fermée ; l'instant de choc est la
racine de la distance signée à une paroi qui tourne, isolée par balayage puis
bissection. Aucune intégration à pas fixe nulle part.

Sans traînée, délibérément : avec traînée il n'existe plus de forme fermée
entre deux chocs, l'oracle deviendrait lui-même un intégrateur approché, donc
contestable. On perd du réalisme, on garde l'auditabilité
"""

import json
import sys

from mpmath import mp, mpf, cos, sin, sqrt

mp.dps = 50

# --- instance figée ---
OMEGA = mpf("0.7")          # rad/s, rotation du pentagone autour de l'origine
G = mpf("-9.81")            # m/s², selon y
P0 = (mpf("0.10"), mpf("0.30"))
V0 = (mpf("1.70"), mpf("0.00"))
# pentagone convexe irrégulier au repos, rayon ~1 m, sommets en sens direct
SOMMETS = [
    (mpf("1.00"), mpf("0.00")),
    (mpf("0.25"), mpf("0.95")),
    (mpf("-0.85"), mpf("0.52")),
    (mpf("-0.78"), mpf("-0.62")),
    (mpf("0.40"), mpf("-0.88")),
]
EPS_SORTIE = mpf("1e-9")    # marge pour quitter la paroi qu'on vient de heurter


def rot(v, a):
    c, s = cos(a), sin(a)
    return (c * v[0] - s * v[1], s * v[0] + c * v[1])


def paroi(i, t):
    """Sommet de départ et normale intérieure unitaire de la paroi i à l'instant t"""
    a = rot(SOMMETS[i], OMEGA * t)
    b = rot(SOMMETS[(i + 1) % len(SOMMETS)], OMEGA * t)
    ex, ey = b[0] - a[0], b[1] - a[1]
    n = (-ey, ex)  # sens direct : la normale intérieure est le quart de tour à gauche
    ln = sqrt(n[0] ** 2 + n[1] ** 2)
    return a, (n[0] / ln, n[1] / ln)


def vol(p, v, tau):
    return (p[0] + v[0] * tau, p[1] + v[1] * tau + mpf("0.5") * G * tau ** 2)


def vitesse(v, tau):
    return (v[0], v[1] + G * tau)


def distance(i, t0, p, v, tau):
    """Distance signée à la paroi i, positive à l'intérieur"""
    a, n = paroi(i, t0 + tau)
    q = vol(p, v, tau)
    return n[0] * (q[0] - a[0]) + n[1] * (q[1] - a[1])


def prochain_choc(t0, p, v, pas=mpf("0.002"), horizon=mpf("5.0")):
    """Balayage grossier pour encadrer la racine, puis bissection à 1e-30"""
    meilleur = None
    for i in range(len(SOMMETS)):
        tau, d_prec = mpf("0"), distance(i, t0, p, v, mpf("0"))
        if d_prec <= 0:
            tau = EPS_SORTIE
            d_prec = distance(i, t0, p, v, tau)
        while tau < horizon:
            tau2 = tau + pas
            d2 = distance(i, t0, p, v, tau2)
            if d_prec > 0 >= d2:
                lo, hi = tau, tau2
                for _ in range(200):
                    mid = (lo + hi) / 2
                    if distance(i, t0, p, v, mid) > 0:
                        lo = mid
                    else:
                        hi = mid
                    if hi - lo < mpf("1e-30"):
                        break
                cand = (lo + hi) / 2
                if meilleur is None or cand < meilleur[0]:
                    meilleur = (cand, i)
                break
            tau, d_prec = tau2, d2
    return meilleur


def reflechir(p, v, i, t):
    """Réflexion élastique sur une paroi mobile : v' = v - 2((v-u)·n)n,
    où u est la vitesse d'entraînement du point de contact, u = omega x r"""
    _, n = paroi(i, t)
    u = (-OMEGA * p[1], OMEGA * p[0])
    w = (v[0] - u[0], v[1] - u[1])
    s = w[0] * n[0] + w[1] * n[1]
    return (v[0] - 2 * s * n[0], v[1] - 2 * s * n[1])


def trajectoire(t_max):
    """Liste des états (t, p, v) à chaque choc, du départ à t_max"""
    t, p, v = mpf("0"), P0, V0
    etats = [(t, p, v)]
    while t < t_max:
        nxt = prochain_choc(t, p, v)
        if nxt is None:
            break
        tau, i = nxt
        if t + tau > t_max:
            break
        p, v = vol(p, v, tau), vitesse(v, tau)
        t = t + tau
        v = reflechir(p, v, i, t)
        etats.append((t, p, v))
    return etats


def position(t_cible, etats):
    e = [x for x in etats if x[0] <= t_cible][-1]
    return vol(e[1], e[2], t_cible - e[0])


def dedans(q, t, marge=mpf("0")):
    for i in range(len(SOMMETS)):
        a, n = paroi(i, t)
        if n[0] * (q[0] - a[0]) + n[1] * (q[1] - a[1]) < marge:
            return False
    return True


if __name__ == "__main__":
    t_max = mpf(sys.argv[1]) if len(sys.argv) > 1 else mpf("45")
    et = trajectoire(t_max)
    sortie = {"chocs": len(et) - 1, "positions": {}}
    for t in ("2", "8", "20", "45"):
        if mpf(t) <= t_max:
            q = position(mpf(t), et)
            sortie["positions"][t] = [str(q[0]), str(q[1])]
            sortie.setdefault("dedans", {})[t] = dedans(q, mpf(t))
    print(json.dumps(sortie, indent=2))
