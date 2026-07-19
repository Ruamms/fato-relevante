# Fontes de dados, APIs e funcionalidades — e por quê

Este documento explica **de onde vem cada dado** do Scout, **como** acessamos
e **por que** escolhemos aquela fonte. É a referência única para entender o
que o projeto consome do mundo externo.

## Princípios que guiam a escolha de fonte

1. **Fonte oficial acima de conveniência.** Preferimos o dado bruto do órgão
   regulador (CVM, B3, Banco Central) a agregadores de terceiros — mais
   confiável, sem termos de uso restritivos e auditável. Foi por isso que o
   Yahoo Finance foi removido (questão de propriedade dos dados) e trocado
   pela Série Histórica oficial da B3.
2. **Todo número sai de código determinístico e testável.** A IA só interpreta
   texto; nenhum indicador, preço ou percentual é "inventado" por modelo.
3. **Toda afirmação tem fonte** — cada red flag carrega a conta que a disparou
   e de onde veio o dado.
4. **Fatos, nunca recomendação de compra ou venda** (Resolução CVM 20 / sem
   CNPI).
5. **Um arquivo cobre a base inteira sempre que possível** — evitamos "uma
   requisição por ativo"; a B3 e a CVM publicam datasets completos.

---

## Fontes de dados

### 1. CVM — Dados Abertos (`dados.cvm.gov.br`)

A espinha dorsal do Scout. Dado público, oficial, sem chave e sem termo
restritivo — a base certa para um projeto aberto.

| Dataset | O que traz | Alimenta |
|---|---|---|
| `FII/DOC/INF_MENSAL` | Informe mensal de FII (2016+): VP/cota, patrimônio líquido, DY do mês, nº de cotas, nº de cotistas, valor do ativo | Indicadores, DY, P/VP, base de cotistas, corte de atividade |
| `FII/DOC/INF_TRIMESTRAL` | Por imóvel: área, % da receita, vacância, inadimplência; e o resultado contábil/financeiro do trimestre | Vacância ponderada, red flag de distribuição exata (rendimento vs resultado), setores de inquilino |
| `FI/CAD/registro_fundo_classe.zip` | Cadastro de fundos: **situação** (Em Funcionamento / Em Liquidação / Cancelado), gestor, administrador | Seções Gestora/Administrador, **red flag de situação (fundo encerrando)** |
| `FI/DOC/CDA/cda_fi_AAAAMM` (membro `cda_fie`) | Carteira mensal dos fundos de índice (ETF): composição por grupo, PL, principais posições | Página de ETF, PL, cota patrimonial, **verificador de classificação**, red flags de ETF |
| `CIA_ABERTA/CAD/cad_cia_aberta.csv` | Cadastro de companhias abertas: setor, situação, **auditor**, CNPJ | Ações (A1): setor, situação, casamento com a B3 |
| `CIA_ABERTA/DOC/DFP` e `/ITR` | Balanços padronizados (DRE, BP, DFC) + **parecer do auditor em CSV** | Indicadores fundamentais de ação (A2) e parecer (A3) — *planejado* |
| `CIA_ABERTA/DOC/FRE` | Formulário de Referência: diretoria/conselho, partes relacionadas, remuneração | FRE por IA (A5) — *planejado* |

**Por quê:** é o dado primário do regulador. A CVM padroniza os informes, então
FIIs ficam comparáveis entre si e um download cobre a base toda.

**Gotchas conhecidos:** dois vocabulários de coluna (pré e pós Resolução CVM
175) normalizados no coletor; no trimestral, vacância/inadimplência são fração
(1.0 = 100%) e % de receita é percentual (0–100); o ticker não vem no dado —
é derivado do **ISIN** (que embute o radical do papel).

### 2. B3 — cotações e listagens

| Fonte | Endpoint | O que traz | Alimenta |
|---|---|---|---|
| **COTAHIST** (Série Histórica) | `bvmf.bmfbovespa.com.br/InstDados/SerHist` | Fechamento nominal oficial. `codbdi` 02 = ação, 12 = FII, 14 = ETF. Anuais (2011+) + mensais + **diários** (mês corrente) | Cotação D-1, volume financeiro, séries ajustadas |
| **fundsListedProxy** | `sistemaswebb3-listados.b3.com.br/fundsListedProxy` | ETFs listados (ETF / ETF-RF / ETF-Cripto): ticker↔CNPJ, id no FNET | Tabela de ETFs, **deslistagem** (quem some da lista sai do site) |
| **indexProxy / indexStatisticsProxy** | `.../indexProxy/.../GetPortfolioDay` | Composição de índice: **IBrX-100** (escopo v1 de ações) e **IFIX** (histórico) | Escopo de empresas, linha do IFIX na rentabilidade |
| **listedCompaniesProxy** | `.../listedCompaniesProxy/CompanyCall/...` | Empresas (codeCVM, CNPJ, setor), papéis (ON/PN/unit com ISIN), **eventos societários** (desdobramento/grupamento/bonificação) e **dividendos/JCP** | Modelo emissor→papéis, ajuste de ação por evento real, retorno total |
| **Cotações mercado** | `cotacao.b3.com.br/mds/api/v1` | Fechamento diário dos **ETFs de renda fixa** (não estão no COTAHIST) | Preço dos ETF-RF |

**Por quê:** é a fonte oficial dos preços e das listagens — pública, sem chave,
sem os problemas de propriedade que tiram o Yahoo do jogo. Preço exibido é o
**fechamento oficial D-1** (tempo real é serviço licenciado da B3).

**Gotchas:** o COTAHIST **mensal só sai depois do mês fechar** — o mês corrente
vem dos arquivos diários (senão o preço fica parado); o `factor` dos eventos
societários tem semântica dupla (desdobramento/bonificação = % de ações novas;
grupamento = razão direta); ETF de renda fixa **não** aparece no COTAHIST.

### 3. FNET — documentos regulatórios (`fnet.bmfbovespa.com.br`)

O repositório onde FIIs **e** ETFs publicam os documentos que quase ninguém lê:
relatório gerencial, fatos relevantes, comunicados ao mercado, assembleias,
demonstrações financeiras e **proventos de ETF** (aviso aos cotistas em XML
estruturado).

**Alimenta:** a leitura por IA (fatos/comunicados/assembleias), o parecer do
auditor e os proventos distribuídos por ETF.

**Por quê:** é exatamente o diferencial do Scout — "lemos os documentos oficiais
que assustam" e transformamos em fato com fonte. Cada documento tem link para
o original.

### 4. Banco Central — SGS (`api.bcb.gov.br`)

Séries temporais oficiais: **CDI** (código 4391) e **IPCA** (código 433).

**Alimenta:** a rentabilidade acumulada comparada ao CDI e ao IPCA (o custo de
oportunidade e a inflação).

**Por quê:** fonte oficial do "contra o que comparar" — um retorno só significa
algo ao lado do CDI e da inflação.

### 5. Ollama — modelo de linguagem **local** (`qwen2.5:14b`)

Roda **na sua máquina**, via Ollama. Lê o texto extraído dos PDFs do FNET e
devolve **apenas** fatos com citação do trecho.

**Regras duras:** nunca produz número novo (todos vêm da CVM/B3), nunca
recomenda, sempre cita a origem. `num_ctx` 16k para caber no contexto sem
estourar a GPU.

**Por quê:** privacidade (nenhum dado sai da máquina, nenhuma API paga) e
separação de responsabilidades — o modelo interpreta linguagem, o código
determinístico calcula.

### 6. GoatCounter — analytics sem cookie (opcional)

Contagem de páginas vistas e **termos de busca** (anônimos e agregados),
**sem cookie e sem banner de consentimento**. Ligado só quando há um código
configurado (`SCOUT_ANALYTICS`); sem ele, o site não rastreia nada.

**Por quê:** entender o que é útil e o que as pessoas procuram sem achar
(demanda ainda não coberta = combustível do roadmap), respeitando a postura de
privacidade. A busca é sanitizada a `[A-Z0-9]` — texto livre/pessoal é
descartado.

### 7. GitHub API — status da publicação

Consulta o último run do workflow `site.yml` para mostrar, na home, quando o
site foi atualizado e um botão de "atualizar agora".

**Por quê:** transparência de build-in-public direto na página.

---

## Funcionalidades determinísticas (o "como" vira fato)

Estas transformam a fonte bruta em informação — tudo em código testável:

- **Ajuste por desdobramento.** FII/ETF: pelo salto do VP/cota (mesmo algoritmo
  do preço). Ação: por **eventos societários reais** da B3 (nunca por salto de
  preço — queda forte não pode virar "split" falso).
- **Retorno total.** Série de preço + proventos reinvestidos, ancorada no preço
  atual — o número que responde "quanto eu teria hoje".
- **Red flags.** FII: 10 regras (distribuição vs patrimônio, diluição, VP em
  queda, vacância, cotistas, P/VP fora da faixa, rendimentos irregulares, fundo
  novo, situação cadastral…). ETF: 6 verificações (PL inviável, liquidez,
  histórico curto, carteira fechada, classe divergente, situação). Cada uma com
  severidade, evidência numérica e fonte; sem dado vira "não avaliada", **nunca
  aprovação silenciosa**.
- **Parecer do auditor.** Classificação determinística (regex sobre as fórmulas
  normatizadas NBC TA) do parecer na DF — **sem IA**: sem ressalva / com
  ressalva / adversa / abstenção + alerta de continuidade operacional.
- **Verificador de classificação de ETF.** Compara a carteira real (CDA) com a
  **sua** curadoria (`classificacao_etfs.csv`) e **escreve um relatório**
  (`etf_divergencias.csv`) para você revisar. **Nunca sobrescreve a curadoria** —
  a classificação é decisão humana (ver seção abaixo).
- **Selo-síntese.** Resumo mecânico de 5 níveis (grave / atenção / histórico
  insuficiente / leves / sem alertas), com critério público — nunca veredito.

---

## O verificador NÃO altera a sua classificação

Ponto importante, porque é fácil confundir: quando o `atualizar` mostra algo
como *"1 divergência e 24 pontos de atenção — revisar"*, **isso não é erro** —
é o verificador fazendo o trabalho dele.

O que ele faz, exatamente:

1. **Lê** a sua curadoria em `dados/classificacao_etfs.csv` (só leitura).
2. **Compara** com a carteira real do mês (CDA da CVM) e com o segmento da B3.
3. **Escreve um relatório** em `~/.scout/etf_divergencias.csv` listando o que
   destoa — para **você** decidir.

Ele **nunca** reescreve `classificacao_etfs.csv`. A classificação Scout é sua
curadoria; o sistema aponta, você decide. "Divergência" = a carteira não bate
com a classe declarada (rever a classe ou é realocação em curso); "ponto de
atenção" = caso conhecido e explicável (fundo novo ~100% em renda fixa durante
a captação, exposição via cotas de outro fundo). Revisar o CSV é opcional e
manual.
