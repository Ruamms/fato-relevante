from scout import parecer


def test_classifica_sem_ressalva():
    resultado = parecer.classificar(
        "Em nossa opinião, as demonstrações financeiras acima referidas apresentam "
        "adequadamente, em todos os aspectos relevantes, a posição patrimonial e "
        "financeira do Fundo."
    )
    assert resultado["tipo"] == "sem_ressalva"
    assert resultado["grave"] is False
    assert resultado["continuidade"] is False
    assert "opinião" in resultado["trecho"]


def test_classifica_ressalva_e_adversa_e_abstencao():
    ressalva = parecer.classificar(
        "Opinião com ressalva. Exceto pelo assunto descrito na seção a seguir, as "
        "demonstrações apresentam adequadamente a posição do Fundo."
    )
    assert ressalva["tipo"] == "ressalva" and ressalva["grave"] is True

    adversa = parecer.classificar(
        "Opinião adversa. Devido à relevância do assunto, as demonstrações não "
        "apresentam adequadamente a posição patrimonial."
    )
    assert adversa["tipo"] == "adversa" and adversa["grave"] is True

    abstencao = parecer.classificar(
        "Abstenção de opinião. Não expressamos opinião sobre as demonstrações "
        "financeiras do Fundo."
    )
    assert abstencao["tipo"] == "abstencao" and abstencao["grave"] is True


def test_detecta_incerteza_de_continuidade():
    resultado = parecer.classificar(
        "Em nossa opinião, as demonstrações apresentam adequadamente, em todos os "
        "aspectos relevantes, a posição do Fundo. Chamamos a atenção para a nota 1, "
        "que indica incerteza relevante relacionada à continuidade operacional."
    )
    assert resultado["tipo"] == "sem_ressalva"
    assert resultado["continuidade"] is True


def test_texto_sem_parecer():
    resultado = parecer.classificar("Balanço patrimonial e notas explicativas do exercício.")
    assert resultado["tipo"] == "nao_identificado"
    assert resultado["grave"] is False
    assert resultado["trecho"] == ""
