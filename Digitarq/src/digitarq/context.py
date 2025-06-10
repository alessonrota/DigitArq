# contexto.py
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class FormContext:
    """Estado global com os metadados iniciais do Nobrad."""
    campos: Dict[str, str] = field(default_factory=dict)

# instância única, importável por todos os módulos
FORM_CONTEXT = FormContext()


#
#from contexto import FORM_CONTEXT
# Exemplo de acesso
#codigo_pais = FORM_CONTEXT.campos.get("BR", "")