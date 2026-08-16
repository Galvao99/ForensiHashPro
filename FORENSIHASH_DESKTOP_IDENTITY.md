# ForensiHash Desktop — identidade visual e ícone

## Ícone em runtime

O Desktop utiliza o asset oficial compacto `web/frontend/public/assets/forensihash_icon.png`. Ele é diferente dos logos horizontais usados na sidebar. `ApplicationPaths` resolve o recurso a partir da raiz do projeto em desenvolvimento e de `sys._MEIPASS` em um bundle PyInstaller, sem depender do diretório de trabalho.

Antes de criar o `QApplication`, o Windows recebe o Application User Model ID estável `ForensiHash.Pro.Desktop`. Depois, `QApplication.setWindowIcon()` configura o ícone padrão da aplicação, usado por janelas, Alt+Tab e taskbar conforme as regras do shell. A janela principal também recebe explicitamente `app.windowIcon()`.

O PNG deve ser incluído no bundle mantendo o caminho relativo `web/frontend/public/assets/forensihash_icon.png`.

## Ícone do executável

O ícone de runtime e o ícone embutido no arquivo `.exe` são configurações distintas. O repositório não possui atualmente arquivo `.spec` nem um `.ico` oficial. O PNG não foi convertido silenciosamente nesta etapa.

Para um futuro build Windows, é necessário obter ou aprovar um `.ico` multirresolução oficial — recomendados 16, 24, 32, 48, 64, 128 e 256 px — e passá-lo à opção `icon` do PyInstaller. O PNG de runtime deve continuar incluído como `datas`. O build precisa então ser validado em instalação limpa e com atalhos/taskbar do Windows.

## Paleta

As superfícies dark usam `ThemeTokens`: background `#0B0D0F`, surface `#111417`, surface secondary `#15191D`, surface elevated `#191E23` e border `#2A3036`. O carregador normaliza superfícies azuladas do QSS legado para esses tokens; azuis claros permanecem como accent funcional para seleção, foco, links e diferenças.
