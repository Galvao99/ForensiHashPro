# Guia de remoção de segredos do histórico Git

## Segredo identificado

Foi identificada uma chave IP2Location de 32 caracteres em `config/settings.json`, introduzida pelo commit `6d7fe566` (`ip api implementation`). O valor não é reproduzido neste documento. O arquivo corrente foi removido do conjunto versionado e substituído por `config/settings.example.json`, sem segredo.

A remoção do arquivo atual **não elimina a chave dos objetos Git anteriores**. A chave deve ser revogada/rotacionada no painel do provedor pelo responsável, mesmo que o histórico seja posteriormente limpo.

## Procedimento recomendado

Não execute estes comandos sem combinar uma janela de manutenção com todos os colaboradores, preservar backup e confirmar quem pode atualizar branches protegidas.

1. Revogue a credencial antiga e crie outra somente quando necessário.
2. Faça um mirror clone descartável do repositório remoto:

   ```bash
   git clone --mirror <URL_DO_REPOSITORIO> forensihash-cleanup.git
   cd forensihash-cleanup.git
   ```

3. Instale e valide `git-filter-repo` a partir de fonte confiável.
4. Remova o antigo arquivo de configuração de todas as referências:

   ```bash
   git filter-repo --sensitive-data-removal --path config/settings.json --invert-paths
   ```

   Em versões que não reconheçam `--sensitive-data-removal`, consulte a documentação da versão instalada antes de prosseguir. Não improvise substituições contendo a chave em shell history.

5. Inspecione branches, tags e objetos antes de publicar. O push de histórico reescrito deve ser executado manualmente por responsável autorizado e não faz parte desta tarefa.

## Alternativa BFG

O BFG Repo-Cleaner também reescreve objetos, mas a opção de remoção por nome pode atingir qualquer `settings.json`, não apenas o caminho pretendido. Para este caso, `git filter-repo` com caminho exato é mais controlável. Nenhuma das ferramentas revoga a credencial no provedor.

## Impactos e riscos

- hashes de commits, tags e branches afetados mudarão;
- pull/merge de clones antigos pode reintroduzir o segredo;
- pull requests abertos e referências externas podem ficar obsoletos;
- tags assinadas perdem validade e precisam de tratamento explícito;
- reflogs, caches de CI, forks, backups e clones de terceiros podem continuar contendo a chave;
- force-push pode sobrescrever trabalho remoto se a coordenação falhar.

Após a publicação autorizada, colaboradores devem arquivar mudanças locais necessárias e realizar **novo clone**, em vez de fazer merge de históricos incompatíveis. Branches e tags não devem ser removidos; devem ser reescritos de forma coordenada somente se contiverem o objeto sensível.

## Verificação final

Execute em um clone novo, sem imprimir o valor da chave:

```bash
git log --all --oneline -- config/settings.json
git log --all -G 'ip_api_key' -- config/settings.json
git rev-list --objects --all
```

Os dois primeiros comandos não devem encontrar o arquivo histórico. Faça também uma varredura com scanner de segredos apropriado em todas as referências e confirme que `config/settings.json` e `.env` permanecem ignorados. Verifique caches de CI, releases e artefatos separadamente.

## Ações que esta tarefa não executou

- revogação ou rotação no provedor;
- `git filter-repo`, BFG ou outra reescrita;
- `push --force`;
- remoção de branch/tag;
- alteração de repositório remoto.

