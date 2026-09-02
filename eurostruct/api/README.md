# eurostruct-api

Couche HTTP d'EUROSTRUCT. **Le moteur deterministe reste sans dependance
HTTP, IA ou reseau** : tout ce qui parle au monde exterieur — signature de
jeton, pilote PostgreSQL, routes — vit ici.

## Demarrage local — une commande

    pip install -e eurostruct/engine -e eurostruct/api
    (cd eurostruct/web && npm install)
    cp eurostruct/api/.env.example .env      # puis renseigner les valeurs
    ./eurostruct/dev.sh                      # --build pour servir le build

`dev.sh` demarre l'API (8000) et l'interface (3000), **attend qu'elles
repondent vraiment** — un processus lance n'est pas un service disponible —
et rend la main. Ctrl-C arrete les deux. Sans `.env`, il demarre quand meme
et affiche ce que `/ready` reproche: le CALCUL fonctionne sans base ni
Supabase, ce sont les DECISIONS d'autorite qui exigent une identite.

Pour lancer l'API seule:

    uvicorn eurostruct_api.app:app --reload --port 8000

`/docs` sert le schema OpenAPI.

## Les deux sondes ne repondent pas a la meme question

| sonde     | question                                            | touche la base |
|-----------|-----------------------------------------------------|----------------|
| `/health` | le processus est-il vivant ?                        | non            |
| `/ready`  | puis-je servir une requete d'autorite maintenant ?  | oui            |

Un `/health` qui interroge PostgreSQL fait redemarrer un processus sain
parce qu'une base est lente : c'est une panne fabriquee par la sonde.

`/ready` verifie pour de vrai — JWKS joignable, base ouvrable, provider
constructible via `creer_provider_de_production` — et rend **503** sinon.
Il ne revele aucune valeur : uniquement des booleens et des noms.

## Ce que l'API refuse, et comment

Les refus du domaine sont rendus en **422** comme des `EngineErrorDTO`,
jamais comme des resultats partiels. C'est ce que le contrat annonce deja,
dans le schema JSON comme dans le TypeScript genere.

**En mode strict — le defaut — le calcul refuse aujourd'hui pour tous les
pays**, parce qu'aucun parametre national n'est au statut `confirmed`. Le
422 porte la liste complete des parametres a faire relever, avec leur
clause et leur annexe. Ce n'est pas une panne : c'est l'interdiction n°3 du
projet appliquee — jamais d'Eurocode sans son Annexe Nationale.

`strict_ndp=false` rend des nombres, et la reponse porte alors
`signable: false` et la mention **PROJET — NON SIGNABLE**.

## Tests

    pytest eurostruct/api/tests -q                       # sans base
    EUROSTRUCT_TEST_DATABASE_URL=... pytest eurostruct/api/tests -q -m postgres
