from workers.promax_worker import _selected_liga_entrega_specs


SPECS = (
    ("030805_LIGA", "03.08.05"),
    ("030224_RESUMO_LIGA", "03.02.24/Resumo"),
)


def test_liga_profile_without_explicit_routines_uploads_all_specs():
    assert _selected_liga_entrega_specs({"profile": "liga_entrega"}, SPECS) == list(SPECS)


def test_explicit_routine_selection_stays_restricted():
    assert _selected_liga_entrega_specs(
        {"profile": "liga_entrega", "routines": ["030224_RESUMO_LIGA"]},
        SPECS,
    ) == [SPECS[1]]


def test_unrelated_profile_without_routines_does_not_upload():
    assert _selected_liga_entrega_specs({"profile": "financeiro"}, SPECS) == []
