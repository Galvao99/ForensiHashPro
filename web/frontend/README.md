# ForensiHash Web Frontend

Frontend institucional e da plataforma local, desenvolvido com React,
TypeScript e Vite.

## Instalação e desenvolvimento

```text
npm install
npm run dev
```

Por padrão, o Vite encaminha `/api` e `/health` para
`http://127.0.0.1:8000`. Para outro backend, copie `.env.example` para `.env`
e defina `VITE_API_BASE_URL`, sem incluir segredos.

## Validação

```text
npm run build
npm run test
npm run lint
```

## Estrutura

- `src/components`: componentes compartilhados e design system;
- `src/content`: conteúdo institucional e referências estáticas;
- `src/pages`: páginas públicas e da plataforma;
- `src/lib`: cliente HTTP;
- `src/types`: contrato estrutural consumido da API;
- `src/styles`: tokens e estilos globais.

O login e o cadastro são exclusivamente visuais nesta fase. Nenhuma credencial
é persistida. O DDNA é apresentado apenas como tecnologia em desenvolvimento.

O PNG oficial do logo não estava presente no workspace durante a criação desta
fundação. A navegação usa temporariamente um wordmark textual acessível; o asset
oficial deve ser colocado em `public/assets/` quando fornecido, sem alteração.
