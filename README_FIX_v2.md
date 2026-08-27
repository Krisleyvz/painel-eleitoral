# FIX v2 — Cadastro local prioritário

O GitHub Actions recebeu HTTP 403 tanto do CDN do TSE quanto do DivulgaCandContas.
Esta correção remove o TSE do caminho crítico de execução.

Arquivos:
- social_perfis_seed_2026.json → cadastro prioritário versionado
- radar_social_seed_adapter_v2.py → injeta o cadastro no motor existente
- radar-social-v1.yml → workflow atualizado

Suba os dois primeiros na raiz do repositório.
Substitua `.github/workflows/radar-social-v1.yml` pelo terceiro.

O commit dispara o workflow e força a atualização da aba Social_Perfis.
