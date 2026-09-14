# EUROSTRUCT — image de production de l'interface
#
# CONSTRUITE DEPUIS `eurostruct/`, PAS DEPUIS `web/`
#
#     docker build -f web/Dockerfile -t eurostruct-web:local .
#
# `packages/contracts` vit hors de `web/` — c'est le contrat généré depuis les
# schémas Pydantic — et `tsconfig.json` le résout par `@contracts/*`. Le
# contexte de build doit donc contenir les deux.
#
# AUCUNE URL, AUCUNE CLE N'EST FIGEE DANS CETTE IMAGE
# -----------------------------------------------------
# C'est la contrainte la plus facile à violer sans s'en apercevoir, parce que
# Next **inline les `NEXT_PUBLIC_*` dans le bundle au moment du build**. Une
# image construite avec `NEXT_PUBLIC_SUPABASE_ANON_KEY=…` porte cette clé dans
# son JavaScript, définitivement, y compris après qu'on a « changé la variable
# d'environnement ».
#
# AUCUN `ARG` NEXT_PUBLIC_* N'EXISTE DONC ICI. La configuration est lue à
# chaque requête par le layout — un composant serveur — et déposée dans la
# page. Voir `web/lib/configuration.ts`. La même image sert le développement,
# la recette et la production.
FROM node:22-bookworm-slim AS build

ENV NEXT_TELEMETRY_DISABLED=1 \
    CI=1

WORKDIR /src

# LES MANIFESTES D'ABORD: l'installation reste en cache tant qu'ils ne bougent
# pas, ce qui est la quasi-totalité des reconstructions.
COPY web/package.json web/package-lock.json* /src/web/
RUN cd /src/web && (npm ci || npm install)

COPY packages/ /src/packages/
COPY web/ /src/web/

RUN cd /src/web && npm run build


FROM node:22-bookworm-slim AS runtime

RUN useradd --system --create-home --uid 10001 eurostruct

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

WORKDIR /app

# LE CONTRAT VOYAGE AVEC L'INTERFACE. `outputFileTracingRoot` pointe au-dessus
# de `web/`: sans `packages/`, le serveur démarre puis échoue au premier rendu
# qui touche un type généré.
COPY --from=build --chown=eurostruct:eurostruct /src/packages /packages
COPY --from=build --chown=eurostruct:eurostruct /src/web /app

USER eurostruct

EXPOSE 3000

# `npx` AJOUTERAIT UN PROCESSUS INTERMEDIAIRE, et c'est exactement ce qui a
# laissé un serveur orphelin en écoute pendant le harnais navigateur: le père
# tué, l'enfant survivait. On exécute donc le binaire directement — il devient
# PID 1 et reçoit SIGTERM lui-même.
CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3000"]
