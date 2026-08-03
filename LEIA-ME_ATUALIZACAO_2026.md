# Atualização — Cenário Eleitoral 2026

Esta entrega acrescenta a rota **7. Cenário Eleitoral 2026** ao painel atual.
As rotas 1 a 6 foram preservadas integralmente. A base histórica `dados.csv`
não foi alterada e não deve ser substituída.

## Arquivos desta atualização

- `painel.py.py`: código completo do painel, com as sete rotas;
- `eleitorado_2026_ac.csv`: uma linha por seção e local de votação;
- `perfil_eleitorado_2026_ac.csv`: perfil agregado por município e zona;
- `perfil_secao_resumo_2026_ac.csv`: totais de perfil por seção;
- `perfil_secao_demografico_2026_ac.csv`: gênero, faixa etária e escolaridade por seção;
- `resumo_municipal_2026_ac.csv`: resumo dos 22 municípios;
- `metadados_2026.json`: fontes, datas, critérios e validações;
- `requirements.txt`: dependências usadas pelo repositório, incluindo `openpyxl`.

## Instalação segura no GitHub

1. Abra o repositório `painel-eleitoral`.
2. Clique no seletor da ramificação `principal`.
3. Escolha **View all branches** e depois **New branch**.
4. Crie a ramificação `cenario-2026`, baseada em `principal`.
5. Confirme que está na ramificação `cenario-2026`.
6. Clique em **Add file > Upload files**.
7. Envie os oito arquivos listados acima para a raiz do repositório.
8. Quando o GitHub perguntar sobre o arquivo já existente, confirme a
   substituição somente de `painel.py.py`.
9. Não apague `dados.csv`, as três planilhas de 2020/2022/2024, imagens,
   bases auxiliares, arquivos de login nem os outros programas do repositório.
10. Faça o commit com a mensagem:
    `Adicionar Cenário Eleitoral 2026 em módulo independente`.
11. Teste a ramificação antes de alterar `principal`.
12. Depois da conferência visual das sete rotas, abra um Pull Request de
    `cenario-2026` para `principal` e faça o merge.

## O que deve aparecer

Na navegação lateral haverá a nova opção:

`🗳️ 7. Cenário Eleitoral 2026`

Ela contém as abas:

1. Visão Geral;
2. Zona Rural;
3. Matriz de Oportunidades;
4. Perfil do Eleitorado;
5. Metodologia e Qualidade.

## Verificação rápida

Com todos os municípios, todos os territórios e todos os locais selecionados,
o módulo deve mostrar:

- 614.375 eleitores no arquivo analisado;
- 661 locais de votação;
- 2.411 seções;
- 91.694 eleitores rurais identificados nos campos públicos;
- 100% das seções com coordenadas válidas.

A aba de metodologia também apresentará a referência pública do TRE-AC:
614.631 eleitores, dos quais 91.571 rurais. A diferença entre os números é
mantida e explicada porque os arquivos foram extraídos em datas diferentes.

## Se aparecer erro de arquivo ausente

Confira se todos os arquivos `.csv` e o `metadados_2026.json` estão na mesma
pasta do `painel.py.py`. Esse erro afeta somente a rota 7; as rotas históricas
continuam disponíveis.

## Atualizações futuras

Quando o TSE publicar uma nova extração, as bases tratadas devem ser geradas
novamente. Não acrescente dados de 2026 diretamente ao `dados.csv`: os arquivos
têm granularidades e significados diferentes.
