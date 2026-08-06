# Estabilização do ForensiHash — Parte 1 de 5

Data da execução: 05/08/2026.

## Escopo e arquivos analisados

Foram relidos integralmente os seis documentos Markdown existentes no início da etapa, incluindo os quatro relatórios da auditoria, README e AGENTS. Também foram analisados `requirements.txt`, configurações, manifesto Rust, entrypoint, factory, settings, integração IP, ExifTool, OCR e testes consumidores desses componentes.

Não foram alterados parser PDF, regras forenses, score, contrato central de análise, interface funcional, histórico Git, API ou qualquer recurso web/multiusuário.

## Segredos encontrados

No working tree atual não foi encontrada credencial real preenchida. Os valores usados nos testes novos são marcadores locais artificiais. `config/settings.json` ainda constava no índice Git por fazer parte do histórico atual, mas foi removido do conteúdo versionável desta mudança e passou a ser ignorado.

A pesquisa histórica identificou uma chave IP2Location de 32 caracteres em `config/settings.json`, introduzida pelo commit `6d7fe566`. O valor não foi reproduzido em saída ou documentação. Revogação e limpeza coordenada do histórico permanecem ações manuais; consulte `GUIA_REMOCAO_SEGREDOS_GIT.md`.

## Mudanças realizadas

- A chave IP2Location agora é lida somente de `IP2LOCATION_API_KEY`.
- `IP2LOCATION_ENABLED` controla explicitamente a integração; sem chave o recurso permanece desabilitado e o restante do desktop funciona.
- Configurações persistidas excluem o segredo; `AppSettings.__repr__` também o omite.
- Configuração inválida gera `InvalidConfigurationError` com mensagem específica.
- `config/settings.example.json` contém apenas opções não secretas.
- `.env.example` documenta variáveis sem valores reais e não é carregado automaticamente.
- `.env`, variantes e `config/settings.json` foram adicionados ao `.gitignore`.
- `ApplicationPaths` resolve aplicação, recursos, configuração e temporários sem depender do CWD e reconhece `_MEIPASS`.
- `ToolDetector` diferencia `available`, `not_installed`, `invalid_path` e `disabled`.
- MetadataEngine, OCR, factory e stylesheet usam caminhos resolvidos.
- Imports Python de OCR passaram a ser tardios, permitindo diagnóstico claro quando dependências opcionais faltam.
- Foi adicionado `pyproject.toml` raiz, com Python `>=3.12,<3.13` e alvo Ruff `py312`.

## Estratégia de configuração

Prioridade e responsabilidade:

1. Segredo: somente ambiente do processo (`IP2LOCATION_API_KEY`).
2. Flags de ambiente: sobrescrevem opções relacionadas quando definidas.
3. `config/settings.json`: opções locais não secretas, ignoradas pelo Git.
4. Valores padrão seguros: consulta externa de IP desabilitada sem credencial.

Em desenvolvimento, a configuração local fica em `<raiz>/config`. Em build empacotado, fica em `%LOCALAPPDATA%/ForensiHashPro` (ou fallback `~/.config/ForensiHashPro`). `FORENSIHASH_CONFIG_DIR` permite destino explícito.

## Estratégia de caminhos

Recursos são relativos ao diretório do projeto durante desenvolvimento e ao `_MEIPASS` em PyInstaller. Caminhos absolutos e traversal em `resource()` são rejeitados. Temporários usam diretório do sistema sob `ForensiHashPro`, ou `FORENSIHASH_TEMP_DIR`. A abstração não cria temporários nem altera o fluxo forense nesta etapa.

## Dependências e Python

Python 3.12 é a versão principal suportada. Não foram encontrados recursos de sintaxe exclusivos de Python posterior a 3.12 nos arquivos alterados. A validação local foi executada em Python 3.14.6 apenas por ser o venv disponível; essa versão não é garantida.

`requirements.txt` contém dependências diretas e muitas transitivas fixadas. `pytesseract` e `pdf2image` estão declarados. PySide6, PyMuPDF, pyHanko, requests, Pillow e bindings relacionados estão presentes no ambiente. Não houve remoção automática de dependências.

O `pip check` no venv Python 3.14 reportou sete distribuições como não suportadas: charset-normalizer, forensihash-core, ijson, jiter, lxml, pydantic_core e PyYAML. Isso reforça a necessidade de recriar um venv Python 3.12. Instalação limpa offline não foi executada, pois exigiria baixar pacotes; os comandos estão no README.

## Ferramentas externas

Estado detectado nesta máquina:

| Ferramenta | Estado | Observação |
|---|---|---|
| ExifTool | disponível | executável incluído em `tools/exiftool` |
| Tesseract | não instalado/localizado | existe somente o instalador no repositório, não `tesseract.exe` |
| Poppler | não instalado/localizado | `pdftoppm` ausente |
| `forensihash_core` | disponível | extensão presente no venv atual |

Tesseract, Poppler e ExifTool não são instalados pelo pip. Caminhos explícitos usam `FORENSIHASH_TESSERACT_PATH`, `FORENSIHASH_POPPLER_PATH` e `FORENSIHASH_EXIFTOOL_PATH`. Um caminho configurado que não existe é classificado como inválido, não como ferramenta ausente.

## Testes criados

Foi criado `tests/test_settings_and_environment.py`, com 13 testes para:

- configuração sem chave;
- chave via ambiente e precedência;
- ausência do segredo em `repr` e JSON;
- timeout inválido e integração habilitada sem chave;
- resolução fora da raiz/CWD;
- recursos empacotados;
- proteção contra traversal;
- quatro estados de ferramentas;
- ExifTool resolvido fora do CWD;
- dependência Python opcional de OCR ausente.

## Testes e verificações

- pytest: **262 aprovados**, 0 falhos, 0 ignorados, 8,74 s;
- `python -m compileall -q app`: aprovado;
- `git diff --check`: aprovado;
- Ruff nos arquivos criados/alterados desta etapa: aprovado;
- Ruff no repositório completo: 19 ocorrências legadas, sem novas ocorrências desta etapa.

O cache plugin do pytest foi desativado porque o diretório `.pytest_cache` preexistente está inacessível no ambiente. Isso evita warnings de cache e não altera a execução dos testes.

## Pendências manuais

1. Revogar/rotacionar a chave IP2Location exposta.
2. Autorizar e coordenar, em tarefa separada, a limpeza do histórico Git.
3. Criar um novo venv Python 3.12 e executar instalação limpa com acesso ao índice.
4. Instalar/configurar Tesseract e Poppler se OCR for desejado.
5. Definir como ExifTool/Tesseract/Poppler serão licenciados, verificados e incluídos no PyInstaller.

## Riscos restantes

- segredo continua recuperável do histórico até reescrita coordenada;
- `.env` não é um secret store e não deve ser distribuído;
- instalação limpa e build PyInstaller ainda precisam ser validados em máquina limpa;
- OCR ainda possui tratamento geral de erros legado, reservado para a Parte 3;
- dependências transitivas estão excessivamente fixadas e ainda não há lock específico por plataforma;
- o instalador Tesseract versionado aumenta o tamanho e exige revisão de origem/checksum/licença;
- Python 3.14 permanece fora da garantia apesar de a suíte rodar no venv atual.
