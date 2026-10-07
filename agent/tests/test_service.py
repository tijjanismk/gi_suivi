from gisuivi_agent.service import sessions_a_pourvoir


def test_session_sans_agent_est_pourvue():
    assert sessions_a_pourvoir([1, 2], [1]) == [2]


def test_session_0_des_services_jamais_pourvue():
    assert sessions_a_pourvoir([0, 1], []) == [1]


def test_agent_present_partout_rien_a_faire():
    assert sessions_a_pourvoir([1, 3], [3, 1, 1]) == []


def test_agent_dans_une_session_deconnectee_ne_compte_pas_pour_une_autre():
    # l'agent de la session 5 (déconnectée, donc absente des actives) ne couvre pas la session 2
    assert sessions_a_pourvoir([2], [5]) == [2]
