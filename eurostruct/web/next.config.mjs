/** @type {import('next').NextConfig} */
const nextConfig = {
  // LE CONTRAT VIT HORS DE CE PAQUET, ET C'EST VOULU. `packages/contracts`
  // est genere depuis les schemas Pydantic du moteur: le recopier ici
  // creerait une seconde definition, qui deriverait au premier changement.
  outputFileTracingRoot: new URL("..", import.meta.url).pathname,
};
export default nextConfig;
