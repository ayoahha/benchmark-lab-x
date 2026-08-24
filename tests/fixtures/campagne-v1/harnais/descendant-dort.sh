#!/bin/sh
# Fixture XS-04 : consigne le PID d'un descendant durable puis bloque le parent.
# Usage : descendant-dort.sh <fichier-pid>
sleep 300 &
echo "$!" > "$1"
wait
