#!/bin/bash
set -e

echo "==> Cambiando a main"
git checkout main

echo "==> Mergeando wip"
git merge wip

echo "==> Pushing a origin main"
git push origin main

echo "==> Volviendo a wip"
git checkout wip

echo ""
echo "✓ Deploy iniciado. Monitorea en:"
echo "  https://dash.cloudflare.com → Pages → leyes"
echo ""
echo "  Sitio: https://leyes.pages.dev"
