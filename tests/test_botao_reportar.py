"""Botão flutuante de reportar bug: snippet + injeção em todas as páginas."""

from scout.relatorio import html as relatorio_html
from scout.relatorio import site as modulo_site


def test_sem_url_nao_gera_botao():
    assert relatorio_html.botao_reportar_html("") == ""
    assert relatorio_html.botao_reportar_html(None) == ""


def test_botao_carrega_url_e_tokens():
    url = "https://tally.so/r/abc123?pagina={URL}&fundo={TICKER}"
    html = relatorio_html.botao_reportar_html(url)
    assert 'id="scout-reportar"' in html
    # a URL vai no data-url; & é escapado p/ &amp; (o browser decodifica ao ler
    # dataset.url), mas os tokens {URL}/{TICKER} são preservados p/ substituição
    assert "tally.so/r/abc123" in html
    assert "{URL}" in html and "{TICKER}" in html
    assert "window.open" in html and "'_blank'" in html
    # nada de terceiro é carregado no HTML (só abre no clique)
    assert "http" in html  # a URL do form está no data-url, não num <script src>
    assert "<script src" not in html.replace(" ", "")


def test_injecao_idempotente_e_so_com_url(tmp_path):
    pagina = tmp_path / "x.html"
    pagina.write_text("<html><body><h1>KNCR11</h1></body></html>", encoding="utf-8")

    # sem URL: nada é injetado
    assert modulo_site._injetar_reportar(tmp_path, "") == 0
    assert "scout-reportar" not in pagina.read_text(encoding="utf-8")

    # com URL: injeta uma vez
    url = "https://forms.gle/exemplo?u={URL}"
    assert modulo_site._injetar_reportar(tmp_path, url) == 1
    conteudo = pagina.read_text(encoding="utf-8")
    assert conteudo.count('id="scout-reportar"') == 1
    assert conteudo.index("scout-reportar") < conteudo.index("</body>")

    # rodar de novo não duplica (idempotente)
    assert modulo_site._injetar_reportar(tmp_path, url) == 0
    assert pagina.read_text(encoding="utf-8").count('id="scout-reportar"') == 1
