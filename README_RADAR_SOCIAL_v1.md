# RADAR SOCIAL SAMIR v1 — implantação aditiva

## O que esta versão faz

Esta versão NÃO substitui o `radar_politico_v8.py` e NÃO altera a aba `Radar_Politico`.

Ela cria cinco abas novas na MESMA planilha:

- `Social_Perfis`
- `Social_Metricas`
- `Social_Eventos`
- `Social_Termometro`
- `Social_Status`

### 1. TSE como cadastro oficial

O script baixa os arquivos oficiais de candidaturas e redes sociais de 2026, filtra o Acre e deputado estadual, e usa o `SQ_CANDIDATO` para ligar candidato às URLs informadas ao TSE.

Não precisamos manter uma lista manual de candidatos.

### 2. Instagram do Samir

Quando os secrets da Meta estiverem configurados:

- lê seguidores e quantidade de mídias;
- lê até 30 publicações recentes;
- calcula presença, engajamento, discussão e momento;
- lê comentários das publicações recentes;
- remove nome/username/ID do comentarista;
- guarda somente texto público + hash técnico de deduplicação;
- classifica sentimento/tema com Gemini, se a chave já usada pelo Radar estiver disponível.

### 3. Concorrentes

Para contas profissionais acessíveis pelo Business Discovery:

- seguidores;
- número de publicações;
- publicações recentes;
- curtidas e comentários públicos;
- engajamento proporcional;
- velocidade/momento.

Contas pessoais ou não acessíveis ficam simplesmente indisponíveis; o workflow não quebra.

### 4. Termômetro Digital v1

0–100, comparável entre os candidatos que têm dados suficientes:

- Presença: 25%
- Engajamento proporcional: 30%
- Discussão: 20%
- Momento: 15%
- Escala da audiência: 10%

**Não é pesquisa eleitoral. Não mede intenção de voto.**

Sentimento ainda NÃO entra no termômetro comparativo, porque temos comentários completos do próprio Samir, mas não cobertura equivalente de texto dos concorrentes. Isso evita um índice metodologicamente injusto.

## Secrets novos necessários

Os secrets Google/Gemini já usados pelo Radar permanecem os mesmos.

Adicionar no GitHub:

- `META_IG_USER_ID`
- `META_PAGE_ACCESS_TOKEN`
- `SOCIAL_SAMIR_USERNAME` (opcional, mas recomendado)
- `THREADS_ACCESS_TOKEN` (opcional; Threads ficará desativado sem ele)

## Meta

A conta do Instagram precisa ser profissional (Business/Creator) e estar ligada a uma Página para o caminho de Facebook Login usado nesta v1.

Permissões esperadas para leitura/gestão da conta própria e Business Discovery dependem da configuração do App Meta. A integração deve ser testada no modo padrão antes de qualquer ampliação.

## Ordem segura de implantação

1. Subir `radar_social_v1.py`;
2. Subir `social_runtime_snapshot_v1.py`;
3. Subir o workflow em `.github/workflows/radar-social-v1.yml`;
4. Rodar manualmente sem secrets Meta:
   - deve criar/atualizar `Social_Perfis` usando apenas TSE;
   - deve registrar `AGUARDANDO_CONFIG` para Instagram;
5. Configurar os secrets Meta;
6. Rodar manualmente novamente;
7. Validar `Social_Metricas`, `Social_Eventos`, `Social_Termometro`;
8. Só depois integrar `social_runtime.json` à Central visual.

## O que deliberadamente ficou para a v2

- webhook de comentário em tempo real;
- Facebook Pages;
- YouTube;
- TikTok;
- X;
- ligação do runtime social à interface da Central;
- Pressão Eleitoral (digital + sobreposição territorial TSE);
- histórico de tendência de 7/30 dias na interface.

A v1 foi desenhada para validar a coleta sem mexer no que já funciona.
