"""Mensajes FIPA-ACL.

Solo se modela lo que el escenario necesita: performativa, participantes,
contenido, protocolo y correlación de conversación. El transporte es
intercambiable (en proceso hoy, XMPP mañana) sin tocar a los agentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Performativas FIPA-ACL usadas en el escenario
INFORM = "inform"
REQUEST = "request"
AGREE = "agree"
REFUSE = "refuse"
FAILURE = "failure"
QUERY_REF = "query-ref"
QUERY_IF = "query-if"

# Protocolos FIPA
FIPA_REQUEST = "fipa-request"
FIPA_QUERY = "fipa-query"
FIPA_QUERY_IF = "fipa-query-if"


@dataclass
class MensajeACL:
    performativa: str
    emisor: str
    receptor: str
    contenido: dict[str, Any] = field(default_factory=dict)
    protocolo: str = FIPA_REQUEST
    conversation_id: str = ""
    reply_with: str = ""
    in_reply_to: str = ""
    ronda: int = 0
    seq: int = 0

    def resumen(self, maximo: int = 90) -> str:
        partes = []
        for clave, valor in self.contenido.items():
            texto = str(valor).replace("\n", " ")
            if len(texto) > 40:
                texto = texto[:37] + "..."
            partes.append(f"{clave}={texto}")
        texto = ", ".join(partes)
        if len(texto) > maximo:
            texto = texto[: maximo - 3] + "..."
        return texto

    def a_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ronda": self.ronda,
            "tipo": "mensaje",
            "performativa": self.performativa,
            "emisor": self.emisor,
            "receptor": self.receptor,
            "contenido": self.contenido,
            "protocolo": self.protocolo,
            "conversation_id": self.conversation_id,
            "reply_with": self.reply_with,
            "in_reply_to": self.in_reply_to,
        }
