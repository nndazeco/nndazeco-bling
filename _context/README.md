# `_context/` — contexto local (não versionado)

Pasta para **arquivos de apoio temporários/locais** usados como contexto pela IA ou por
você, mas que **não devem ir para o git**: PDFs, políticas, planilhas, prints, rascunhos,
documentos de terceiros etc.

- **Nada aqui é fonte de verdade** do projeto. As fontes canônicas são [`specs/`](../specs/)
  e o código em `scripts/`, `bling/` e `tools/`.
- Todo o conteúdo é **ignorado pelo git** (ver `.gitignore`), **exceto este `README.md`**.
- Para usar como contexto, cite o arquivo pelo caminho. Ex.:
  `_context/Politica de Comissionamento Vendedores_v04052026.pdf`.
- Pode adicionar/apagar/renomear à vontade — não afeta os scripts.

## Exemplos de uso

- políticas e tabelas de comissionamento;
- contratos e modelos recebidos;
- exportações e documentos de apoio.

> Snapshot de dados reais da conta fica em `data/` (também ignorado); este diretório é só
> para material de leitura/contexto.
