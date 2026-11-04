"""Operator-facing translations; does not change the proprietary game client UI."""
import os

MESSAGES = {
    "en": {"start": "Creative Destruction Reborn server starting", "http": "HTTP service on port {port}", "listen": "{kind} listening on port {port}", "remote": "WARNING: remote binding is experimental, unencrypted and NOT multiplayer-ready", "full": "Connection refused: server is at capacity"},
    "fr": {"start": "Démarrage du serveur Creative Destruction Reborn", "http": "Service HTTP sur le port {port}", "listen": "{kind} à l'écoute sur le port {port}", "remote": "ATTENTION : accès distant expérimental, non chiffré et pas prêt pour le multijoueur", "full": "Connexion refusée : serveur saturé"},
    "de": {"start": "Creative Destruction Reborn Server startet", "http": "HTTP-Dienst auf Port {port}", "listen": "{kind} lauscht auf Port {port}", "remote": "WARNUNG: Fernzugriff ist experimentell, unverschlüsselt und nicht multiplayerfähig", "full": "Verbindung abgelehnt: Server ausgelastet"},
    "es": {"start": "Iniciando servidor Creative Destruction Reborn", "http": "Servicio HTTP en puerto {port}", "listen": "{kind} escucha en puerto {port}", "remote": "AVISO: acceso remoto experimental, sin cifrado y no apto para multijugador", "full": "Conexión rechazada: servidor lleno"},
    "pt": {"start": "Iniciando servidor Creative Destruction Reborn", "http": "Serviço HTTP na porta {port}", "listen": "{kind} escutando na porta {port}", "remote": "AVISO: acesso remoto experimental, sem criptografia e não pronto para multijogador", "full": "Conexão recusada: servidor lotado"},
}

def language():
    code = os.getenv("CDR_LANGUAGE", "en").strip().lower().replace("_", "-").split("-", 1)[0]
    return code if code in MESSAGES else "en"

def tr(key, **kwargs):
    return MESSAGES[language()].get(key, MESSAGES["en"][key]).format(**kwargs)
