"""Grupos de papéis por capacidade (RBAC do CONTEXTO.md).

`admin` é aceito implicitamente por `require_roles`, por isso não aparece aqui.
"""

from collections.abc import Iterable

from app.models.enums import Role

ALL_ROLES = tuple(Role)


def has_role(role: Role, allowed: Iterable[Role]) -> bool:
    """Checagem fina dentro de services (admin sempre pode)."""
    return role == Role.ADMIN or role in set(allowed)


# Registrar entrada/retirada/transferência, inventário, ocorrência, cadastrar dormente.
FIELD_ROLES = (Role.OPERATOR, Role.TECHNICIAN, Role.SPECIALIST)

# Registrar inspeções; mudar status manualmente (descarte, em via).
INSPECTION_ROLES = (Role.TECHNICIAN, Role.SPECIALIST)

# Classificar/revisar espécie; manter o catálogo de espécies.
SPECIES_ROLES = (Role.SPECIALIST,)

# Indicadores, logs de auditoria, manter locais, listar usuários.
MANAGEMENT_ROLES = (Role.SUPERVISOR,)

# Só admin (lista vazia = apenas o admin implícito).
ADMIN_ONLY: tuple[Role, ...] = ()
