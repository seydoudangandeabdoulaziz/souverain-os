"""Tests unitaires (sans base) de DiagnosticAudit et d'AuditNonProvisionne."""

from __future__ import annotations

from dataclasses import replace

from brique_08_audit_human_loop.diagnostic import DiagnosticAudit
from brique_08_audit_human_loop.modeles import AuditNonProvisionne, RaisonAudit

_CONFORME = DiagnosticAudit(
    role_existe=True,
    schema_existe=True,
    audit_log_existe=True,
    alertes_existe=True,
    usage_schema=True,
    audit_log_insert=True,
    audit_log_select=True,
    audit_log_update=False,
    audit_log_delete=False,
    audit_log_truncate=False,
    alertes_select=True,
    alertes_update=True,
)


def test_etat_conforme_n_a_aucun_element_manquant() -> None:
    assert _CONFORME.elements_manquants == []
    assert _CONFORME.anomalie_audit_log is False


def test_tenant_neuf_manque_usage_table_et_privileges() -> None:
    neuf = replace(
        _CONFORME,
        audit_log_existe=False,
        alertes_existe=False,
        usage_schema=False,
        audit_log_insert=False,
        audit_log_select=False,
        alertes_select=False,
        alertes_update=False,
    )
    assert neuf.elements_manquants == ["usage_schema", "audit_log", "audit_log_privileges"]


def test_alertes_absente_n_est_jamais_un_element_manquant() -> None:
    # B8 ne crée jamais `alertes` : son absence n'est pas à réparer ici.
    sans_alertes = replace(_CONFORME, alertes_existe=False, alertes_select=False)
    assert "alertes_privileges" not in sans_alertes.elements_manquants


def test_privilege_alertes_manquant_seulement_si_la_table_existe() -> None:
    sans_droit = replace(_CONFORME, alertes_update=False)
    assert sans_droit.elements_manquants == ["alertes_privileges"]


def test_update_ou_delete_ou_truncate_sur_audit_log_est_une_anomalie() -> None:
    for champ in ("audit_log_update", "audit_log_delete", "audit_log_truncate"):
        assert replace(_CONFORME, **{champ: True}).anomalie_audit_log is True


def test_audit_non_provisionne_ne_contient_que_le_code_de_raison() -> None:
    exc = AuditNonProvisionne(RaisonAudit.NON_PROVISIONNE)
    assert exc.raison is RaisonAudit.NON_PROVISIONNE
    assert str(exc) == "audit B8 indisponible : NON_PROVISIONNE"
