# eurostruct-web

Interface minimale. Elle **consomme le contrat TypeScript genere**
(`packages/contracts/src/generated/engine.ts`, produit depuis les schemas
Pydantic du moteur) et ne redefinit aucune forme a la main : une seconde
definition deriverait au premier changement du moteur, et l'interface
afficherait des champs qui n'existent plus.

Elle **ne calcule rien**. Pas une formule, pas un arrondi. Elle montre ce que
le moteur a decide, et le refuse tel quel quand le moteur refuse.

## Demarrage

    cd eurostruct/web && npm install
    npm run dev                     # http://localhost:3000

L'API doit tourner en parallele (voir `eurostruct/api/README.md`).
`NEXT_PUBLIC_EUROSTRUCT_API_URL` dit ou la joindre.

## Ce que l'ecran rend lisible

En mode strict — le defaut — le moteur REFUSE aujourd'hui pour tous les pays,
parce qu'aucun parametre national n'est au statut `confirmed`.

**Ce refus n'est pas une panne, et l'ecran ne doit pas le montrer comme une
erreur technique : c'est une liste de travail.** L'ingenieur recoit les huit
parametres a faire relever dans l'Annexe Nationale publiee, chacun avec sa
clause et sa reference.

Decoche, le mode strict rend des nombres, et le resultat porte la mention
**PROJET — NON SIGNABLE** — visible, en tete de resultat.

## Verification

    npm run typecheck               # tsc --noEmit
    npm run build
