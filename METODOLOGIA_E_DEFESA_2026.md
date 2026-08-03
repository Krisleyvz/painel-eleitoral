# Metodologia e defesa técnica — Cenário Eleitoral 2026

## 1. O que o módulo mede

O módulo mede o **eleitorado cadastrado para 2026**, sua distribuição por
município, zona, seção e local de votação, além de características demográficas
agregadas. Ele não mede intenção de voto e não transforma pessoas aptas em
“votos disponíveis”.

## 2. Fontes

- Portal de Dados Abertos do TSE — Eleitorado 2026:
  https://dadosabertos.tse.jus.br/dataset/eleitorado-2026
- TRE-AC — referência pública apresentada em 21/07/2026:
  https://www.tre-ac.jus.br/comunicacao/noticias/2026/Julho/acre-tem-614-631-eleitoras-e-eleitores-aptos-a-votar-nas-eleicoes-2026

Arquivos analisados:

- `eleitorado_local_votacao_2026_AC.csv`, gerado em 03/08/2026;
- `perfil_eleitorado_2026_AC.csv`, gerado em 14/07/2026;
- `perfil_eleitor_secao_2026_AC.csv`, gerado em 14/07/2026.

## 3. Validações realizadas

| Verificação | Resultado |
|---|---:|
| Municípios | 22 |
| Zonas município/zona | 23 |
| Seções únicas | 2.411 |
| Locais únicos | 661 |
| Coordenadas válidas | 100% |
| Duplicidade da chave município + zona + seção | 0 |
| Total na base de locais | 614.375 |
| Total na base de perfil municipal | 614.375 |
| Total reconstruído no perfil por seção | 614.375 |

Os três totais independentes foram reconciliados. Isso demonstra que o painel
não repete o eleitorado ao consolidar locais ou seções.

## 4. Diferença em relação à divulgação do TRE-AC

| Indicador | Arquivo analisado | TRE-AC | Diferença |
|---|---:|---:|---:|
| Eleitorado total | 614.375 | 614.631 | -256 |
| Eleitorado rural | 91.694 | 91.571 | +123 |

Os arquivos possuem datas e finalidades operacionais diferentes. Por isso, o
painel não força os números a coincidirem. Ele registra a data de cada extração
e conserva a diferença, permitindo auditoria e atualização posterior.

## 5. Reconstrução da zona rural

O arquivo público por local não possui uma coluna binária pronta chamada
“urbano/rural”. A classificação confirmada foi reconstruída de forma
reproduzível:

1. Normalização de acentos e maiúsculas;
2. busca do termo `RURAL` em `NM_BAIRRO` ou `NM_LOCAL_VOTACAO`;
3. marcação desses registros como `RURAL IDENTIFICADA`;
4. indícios como ramal, seringal, comunidade ou assentamento ficam em
   `REVISAR CLASSIFICAÇÃO`;
5. registros em revisão não entram no total rural.

Esse critério identificou 91.694 eleitores rurais, diferença de apenas 123
eleitores — aproximadamente 0,13% — em relação à referência do TRE-AC.

## 6. Cruzamento com 2022

Para a matriz territorial, o cruzamento utiliza:

`município normalizado + número da zona + número da seção`

Os votos são consolidados por seção antes da união, evitando multiplicação de
linhas. Em seguida, as seções são agregadas ao local de votação vigente em
2026.

Fórmula apresentada:

`Penetração histórica (%) = votos de Samir em 2022 / eleitorado de 2026 × 100`

Essa razão é uma **referência histórica**, não uma taxa de conversão ou uma
previsão. Em 2022 Samir concorreu a deputado federal; em 2026 o contexto e o
cargo pretendido são diferentes.

## 7. Por que 2020 e 2024 não são extrapolados

Em 2020 e 2024 Samir concorreu a vereador de Rio Branco. Esses resultados são
válidos para análises internas do município, mas não permitem inferência direta
para os outros 21 municípios. Para a comparação estadual, o módulo utiliza
2022, mantendo a ressalva de mudança de cargo.

## 8. Leitura da matriz de oportunidades

Os locais são organizados por dois eixos descritivos:

- escala do eleitorado de 2026;
- penetração histórica observada em 2022.

As medianas do filtro atual separam quatro quadrantes. Isso ajuda a localizar
territórios de alta escala e baixa penetração histórica, mas não cria uma
ordem automática de campanha. Logística, alianças locais, presença de equipe,
agenda e informações qualitativas devem complementar a decisão.

## 9. Uso responsável do perfil do eleitorado

Gênero, idade, escolaridade, biometria e deficiência são exibidos apenas em
forma agregada. O uso recomendado é planejamento de acessibilidade, logística
e comunicação pública inclusiva. O módulo não identifica indivíduos e não deve
ser usado para perfilamento político pessoal.

## 10. Resposta curta para apresentação à equipe

> O módulo utiliza três bases oficiais do TSE, tratadas separadamente da série
> histórica. Cada seção é contada uma única vez e os três caminhos de cálculo
> reconciliam 614.375 eleitores. A zona rural foi reconstruída por marcadores
> explícitos nos campos oficiais, chegando a 91.694 eleitores, apenas 123 acima
> da referência divulgada pelo TRE-AC. Os votos de 2022 entram somente como
> referência territorial, porque cargo e contexto mudaram. Portanto, o painel
> serve para comparar escala, presença histórica e cobertura territorial — não
> para prometer votos.
