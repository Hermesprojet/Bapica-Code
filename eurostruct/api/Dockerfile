# EUROSTRUCT — image de production de l'API
#
# CONSTRUITE DEPUIS `eurostruct/`, PAS DEPUIS `api/`
#
#     docker build -f api/Dockerfile -t eurostruct-api:local .
#
# Le moteur et l'API sont deux paquets, et l'API dépend du moteur **du même
# arbre**. Construire depuis `api/` obligerait soit à publier le moteur sur un
# index, soit à le copier — deux façons différentes de laisser les deux
# versions diverger sans que rien ne le dise.
#
# DEUX ETAGES, ET LE SECOND NE SAIT PAS COMPILER
# ------------------------------------------------
# L'étage de construction porte les outils de build ; l'étage final ne porte
# que l'interpréteur, les dépendances installées et le code. Un compilateur
# dans une image de production est un outil offert à qui obtient l'exécution.
#
# AUCUNE CONFIGURATION N'EST FIGEE ICI
# -------------------------------------
# Ni DSN, ni URL Supabase, ni clé, ni origine CORS. Rien de tout cela n'est un
# `ENV` de cette image : ce sont des variables de **runtime**, fournies par
# l'orchestration. Une image qui porte l'adresse de sa base ne peut servir
# qu'un environnement, et une image qui porte un secret le porte pour toujours,
# y compris dans les couches qu'on croit avoir écrasées.
FROM python:3.11-slim-bookworm AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /src

# LE MOTEUR D'ABORD. Il change moins souvent que la couche HTTP: le mettre en
# premier garde son étage en cache quand seule l'API bouge.
COPY engine/ /src/engine/
COPY api/ /src/api/

# `--prefix` PLUTOT QU'UN VENV. On copie ensuite l'arbre entier dans l'étage
# final: pas de chemin d'activation à reproduire, pas de venv qui référence un
# préfixe qui n'existe plus.
#
# LES TROIS EN UNE SEULE RESOLUTION, ET C'EST LE CORRECTIF. Trois `pip install`
# successifs échouaient: `--prefix=/opt/eurostruct` installe HORS des chemins
# que pip interroge ensuite, si bien que le second appel ne voyait pas le
# moteur qu'il venait d'installer. Il le cherchait donc sur PyPI, où il n'est
# pas publié — et rendait « No matching distribution found for
# eurostruct-engine>=0.3.0 ». Cette image ne s'était donc JAMAIS construite.
#
# Une seule invocation met les deux chemins locaux dans la même résolution:
# pip satisfait `eurostruct-api -> eurostruct-engine` avec l'arbre présent,
# sans jamais interroger d'index pour un paquet qui n'y sera jamais.
RUN python -m pip install --upgrade pip \
 && python -m pip install --prefix=/opt/eurostruct \
      ./engine ./api "uvicorn[standard]>=0.29"


FROM python:3.11-slim-bookworm AS runtime

# NON-ROOT, ET L'UTILISATEUR EST CREE ICI PLUTOT QUE SUPPOSE. Une image qui
# compte sur l'orchestrateur pour poser `user:` tourne en root partout où on
# oublie de le poser.
RUN useradd --system --create-home --uid 10001 eurostruct

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/eurostruct/bin:${PATH}" \
    PYTHONPATH="/opt/eurostruct/lib/python3.11/site-packages"

COPY --from=build /opt/eurostruct /opt/eurostruct

USER eurostruct
WORKDIR /home/eurostruct

EXPOSE 8000

# PAS DE `HEALTHCHECK` ICI, ET C'EST DELIBERE. `/health` dit que le processus
# vit; `/ready` dit qu'il peut servir. Les deux se sondent différemment — l'un
# pour redémarrer, l'autre pour router — et c'est à l'orchestration de choisir.
# Un `HEALTHCHECK` figé dans l'image imposerait un seul des deux à tout le
# monde.

# `exec` VIA LA FORME JSON: uvicorn devient PID 1 et reçoit SIGTERM
# directement. Passé par un shell, le signal irait au shell et le serveur
# serait tué au bout du délai de grâce, connexions en cours comprises.
CMD ["uvicorn", "eurostruct_api.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--no-server-header", "--proxy-headers", \
     "--timeout-graceful-shutdown", "20"]
