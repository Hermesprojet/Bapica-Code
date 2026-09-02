/**
 * LA SEULE TRADUCTION D'UNE PANNE EN PHRASE LISIBLE.
 *
 * CE QU'ON AFFICHAIT AVANT, ET POURQUOI C'ETAIT UN DEFAUT
 * --------------------------------------------------------
 * Vingt-quatre endroits de l'interface rendaient `String(cause)` a l'ecran —
 * pour l'essentiel des `catch`. Ce que la personne lisait alors, mot pour mot :
 *
 *     AppelRefuse: l'API a refuse (422).
 *     ApiInjoignable: l'API n'a pas repondu (TypeError: Failed to fetch).
 *
 * Le nom de la classe JavaScript, le nom du constructeur d'erreur du
 * navigateur, et pas un mot sur ce qu'il faut faire. Un ingenieur en bureau
 * d'etudes n'a aucune raison de savoir ce qu'est un `TypeError`, et le motif
 * du serveur — celui qui, lui, est utile — restait dans `cause.corps`, jamais
 * affiche.
 *
 * CE MODULE NE COMPOSE AUCUN MOTIF QU'IL N'A PAS RECU
 * ----------------------------------------------------
 * Quand le serveur donne un motif, il est repris TEL QUEL, encadre par la
 * phrase qui dit d'ou il vient. Ce module ne le reformule pas, ne le resume
 * pas, et n'en invente pas un quand il n'y en a pas : un refus normatif est
 * une liste de travail pour l'ingenieur, et la seconde formulation qu'on
 * ecrirait ici serait celle que personne ne corrigerait ensuite.
 *
 * Ce qu'il remplace, c'est uniquement l'enveloppe technique : le nom de la
 * classe, la trace, et le libelle interne du navigateur.
 */
import { ConfigurationAbsente } from "@/lib/configuration";
import { ApiInjoignable, AppelRefuse, SessionExpiree } from "@/lib/transport";

/**
 * Ce qu'on montre a l'ecran pour une cause quelconque.
 *
 * L'ORDRE DES CAS EST L'ORDRE DE PRECISION, du diagnostic le plus precis au
 * plus general. `ConfigurationAbsente` avant `Error` parce que son message
 * nomme la variable d'environnement manquante ; `AppelRefuse` avant `Error`
 * parce que son motif vient du serveur et pas de nous.
 */
export function enClair(cause: unknown): string {
  if (cause instanceof SessionExpiree) {
    return "Votre session a expire. Reconnectez-vous, puis reprenez : la "
      + "demande n'est pas partie.";
  }
  //: LES DEUX PORTENT DEJA UNE PHRASE ECRITE POUR ETRE LUE, et elle nomme ce
  //: qui manque — la variable d'environnement, ou l'adresse appelee. La
  //: reecrire ici en donnerait une seconde version, moins precise.
  if (cause instanceof ConfigurationAbsente) return cause.message;
  if (cause instanceof ApiInjoignable) return cause.message;
  if (cause instanceof AppelRefuse) {
    return `Le serveur a refuse la demande (code ${cause.statut}) : `
      + `${cause.detail}`;
  }
  //: NOS PROPRES ERREURS PORTENT UNE PHRASE FRANCAISE; on la rend telle
  //: quelle. Celles du navigateur n'arrivent pas ici : le transport les
  //: enveloppe dans `ApiInjoignable` avant qu'elles ne remontent.
  if (cause instanceof Error && cause.message.trim()) return cause.message;
  return "Une erreur imprevue s'est produite, et rien de plus n'est connu "
    + "d'elle. Reessayez ; si cela recommence, signalez-le avec l'heure.";
}
