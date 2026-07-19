# ETFs — dossiê de entendimento (base do roadmap)

Registrado em 19/07/2026, antes de escrever qualquer código. Princípio do produto
mantido: **fatos com fonte, nunca recomendação** — e para ETF o fato mais valioso
é justamente "as regras do brinquedo", que quase nenhum investidor conhece.

## O que é (e por que confunde)

ETF (Exchange Traded Fund / "Fundo de Índice", tipo `FIIM` no registro CVM) é um
fundo que replica um índice e negocia em bolsa como uma ação. **212 em
funcionamento** no Brasil hoje. A confusão nasce porque o MESMO formato embala
coisas de comportamento completamente diferente:

| Tipo (índice subjacente) | Exemplos | Comportamento |
|---|---|---|
| Ações Brasil | BOVA11, SMAL11, DIVD11 | variação alta, segue a bolsa |
| Ações internacionais | IVVB11, NASD11 | variação da bolsa lá fora + CÂMBIO embutido |
| Renda fixa | IMAB11, IRFM11, LFTS11, B5P211 | variação baixa; rendimento "invisível" (a cota engorda, nada cai na conta) |
| Cripto | HASH11, QBTC11, BITH11 | volatilidade extrema; custódia via fundo |
| FII-índice | XFIX11 | "FII de FIIs" via índice |
| Híbridos/temáticos | ABTC11 (BTC + renda fixa) | regras próprias caso a caso |

## As peculiaridades que MUDAM o produto

**1. Distribuição de rendimentos.** A maioria dos ETFs brasileiros **reinveste
automaticamente** (total return): não existe "dividendo pingando na conta" — a
calculadora "Uma cota por mês" NÃO SE APLICA e exibi-la seria enganoso. Uma
geração nova (2024+) passou a **distribuir renda**; e há casos que fazem os dois.
→ A página precisa DETECTAR e DIZER o regime de cada fundo; calculadoras por regime.

**2. Tributação (informativa, com fonte — nunca conselho).**
- ETF de ações: 15% sobre o ganho na venda e **NÃO tem a isenção de R$ 20 mil/mês
  das ações** — a pegadinha nº 1 do investidor iniciante.
- ETF de renda fixa: IR regressivo pelo **prazo médio da carteira** (25%/20%/15%),
  **sem come-cotas**, cobrado só na venda — o grande diferencial do formato.
- ETF de cripto: 15% sem isenção (cripto direto tem isenção até R$ 35 mil/mês —
  pegadinha nº 2).

**3. Métricas próprias (não existem no mundo FII).**
- **Taxa de administração**: comparável entre ETFs do MESMO índice — taxa alta
  no mesmo índice é fato objetivo.
- **Prêmio/desconto**: preço em bolsa vs cota patrimonial (a CVM publica a cota
  diária no informe de fundos 555) — descolamento persistente é alerta.
- **Tracking difference**: quanto o fundo entrega vs o índice que promete seguir.
- **PL pequeno**: risco real de deslistagem/encerramento.
- **Liquidez/volume** e presença de formador de mercado.

## Fontes mapeadas (investigação de 19/07/2026)

| Dado | Fonte | Status |
|---|---|---|
| Cadastro, gestora, admin | `registro_fundo_classe.zip` (Tipo_Fundo=FIIM) | **JÁ BAIXAMOS** (infra do Scout) |
| Preço em bolsa (ações/cripto/FII-índice) | COTAHIST codbdi **14** | infra pronta (`coleta/b3.py`, só alargar o filtro) |
| Preço de ETF de **renda fixa** | **NÃO está no COTAHIST** (negociação em ambiente próprio da B3) | fonte a investigar — milestone dedicado |
| Cota patrimonial diária, PL, cotistas | informe diário de fundos 555 (CVM `FI/DOC/INF_DIARIO`), ETFs incluídos | validar volumetria no E1 |
| Índice de referência, taxa de adm | cadastro/B3 fundos listados | investigar no E1 |
| Proventos dos ETFs distribuidores | B3 (corporate actions) | investigar no E6 |
| Relatórios para IA | ETF **não usa o FNET** (isso é de estruturados) | fase 2 do ETF |

## Decisões de produto (a validar com o dono do produto)

1. **Página de ETF é DIFERENTE da página de FII** — sem imóveis/vacância/DY
   mensal; com regime de distribuição, tributação do tipo, prêmio/desconto,
   taxa, tracking. O topo ganha a "carteirinha de regras" do tipo: 3-4 linhas
   didáticas dizendo como AQUELE tipo se comporta (distribui? como é tributado?
   onde o rendimento aparece?).
2. **Classificação por tipo é curadoria assistida**: heurística pelo índice/nome
   + revisão manual (212 fundos é revisável) — errar o tipo aqui é errar tudo.
3. **Renda fixa entra desde o início** mesmo sem preço de bolsa: a cota
   patrimonial diária da CVM vira o "valor de referência" com aviso honesto,
   até a fonte de preço ser resolvida.
4. Selo/red flags de ETF têm **regras próprias** (as de FII não fazem sentido).
