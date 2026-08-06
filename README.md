# 🔍 ForensiHash Pro

> **Digital Forensics Analysis Platform**

Uma plataforma de apoio à perícia digital desenvolvida para auxiliar peritos, advogados e profissionais da computação forense na análise técnica de documentos eletrônicos, assinaturas digitais, metadados e evidências computacionais.

---

<p align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue)
![PySide6](https://img.shields.io/badge/PySide6-Qt-green)
![Status](https://img.shields.io/badge/Status-In_Development-yellow)
![License](https://img.shields.io/badge/License-MIT-orange)

</p>

---

# 📖 Sobre

O **ForensiHash Pro** nasceu da necessidade de reunir, em um único ambiente, diversas ferramentas utilizadas diariamente durante perícias digitais.

Ao invés de alternar entre múltiplos softwares para calcular hashes, extrair metadados, verificar assinaturas digitais e interpretar vestígios, o ForensiHash centraliza essas análises em uma interface moderna, organizada e voltada ao raciocínio técnico-pericial.

---

# 🎯 Objetivos

- Automatizar análises repetitivas realizadas durante perícias digitais;
- Centralizar informações técnicas em uma única plataforma;
- Facilitar a elaboração de laudos periciais;
- Organizar evidências digitais;
- Auxiliar a identificação de inconsistências em documentos eletrônicos.

---

# 🚀 Funcionalidades

## ✅ Implementadas

### 📄 Análise Geral

- Informações básicas do arquivo
- Nome
- Extensão
- Caminho
- Tamanho
- Datas do sistema

---

### 🔐 Hashes

- MD5
- SHA-1
- SHA-224
- SHA-256
- SHA-384
- SHA-512

---

### 📑 Metadados

Extração dos principais metadados do arquivo.

---

### ⚠ Vestígios Técnicos

Motor responsável pela identificação automática de possíveis inconsistências técnicas encontradas durante a análise.

---

### 🧬 Magic Number (Assinatura Binária)

- Identificação do formato real do arquivo
- Comparação entre extensão e assinatura binária
- Detecção inicial de incompatibilidades

---

### 🔏 Assinatura Digital (PDF)

Integração com **pyHanko**.

Atualmente é possível extrair:

- Quantidade de assinaturas
- Assinante
- Emissor
- Número de Série
- Algoritmo de Hash
- Data da Assinatura
- Vigência do Certificado
- Status Técnico

---

### 🕒 Timeline

Estrutura inicial para organização temporal das evidências.

---

# 🏗 Arquitetura

O projeto foi desenvolvido seguindo uma arquitetura modular baseada em Engines.

```text
                    UI

                     │

              Analysis Tabs

                     │

              Analysis Service

                     │

              File Analyzer

──────────────────────────────────────────────

Hash Engine

Metadata Engine

Magic Number Engine

Digital Signature Engine

Findings Engine

──────────────────────────────────────────────

                  Models
```

---

# 📂 Estrutura do Projeto

```text
app/

├── digital_signature/
│   └── parsers/
│
├── engines/
│
├── factory/
│
├── models/
│
├── pages/
│
├── rules/
│
├── services/
│
├── ui/
│
├── widgets/
│
└── tests/
```

---

# 🖥 Interface

O sistema possui uma interface organizada por módulos independentes.

Atualmente estão disponíveis:

- 📄 Geral
- 🔐 Hashes
- 📑 Metadados
- ⚠ Vestígios
- 🕒 Timeline
- 🧬 Magic Number
- 🔏 Assinatura Digital

---

# 🧪 Tecnologias

- Python 3.12
- PySide6
- pyHanko
- pytest

## Ambiente suportado

- Versão principal e garantida nesta fase: **Python 3.12**.
- Python 3.14 foi usado em uma execução de auditoria, mas não é suportado nem
  garantido porque parte das wheels instaladas não declarou compatibilidade.
- O núcleo Rust opcional requer Rust/Cargo e maturin para desenvolvimento.

## Instalação e configuração local

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Copie `config/settings.example.json` para `config/settings.json` somente se
precisar alterar opções locais. O arquivo local é ignorado pelo Git. A chave da
IP2Location deve ser fornecida exclusivamente pelo ambiente:

```powershell
$env:IP2LOCATION_ENABLED = "true"
$env:IP2LOCATION_API_KEY = "<valor-fornecido-localmente>"
```

O ForensiHash não carrega `.env` automaticamente. `.env.example` serve apenas
como catálogo de variáveis e nunca deve conter valores reais.

Ferramentas externas:

- ExifTool: autodetectado no bundle ou no `PATH`; caminho configurável por
  `FORENSIHASH_EXIFTOOL_PATH`.
- Tesseract: não é instalado pelo pip; caminho configurável por
  `FORENSIHASH_TESSERACT_PATH`.
- Poppler (`pdftoppm`): exigido pelo OCR de PDF e não instalado pelo pip;
  diretório configurável por `FORENSIHASH_POPPLER_PATH`.
- Os recursos podem ser desabilitados pelas variáveis documentadas em
  `.env.example`. Estados ausente, desabilitado e caminho inválido são distintos.

---

# 🛣 Roadmap

## Sprint 1

- ✅ Estrutura inicial
- ✅ Interface principal

## Sprint 2

- ✅ Hash Engine
- ✅ Metadata Engine

## Sprint 3

- ✅ Findings Engine
- ✅ Interface modular
- ✅ Organização por páginas

## Sprint 4

- ✅ Magic Number
- ✅ Assinatura Digital
- ✅ Integração com pyHanko
- ✅ Parser de PDF
- 🚧 Validação criptográfica

## Próximas Sprints

- 📄 OCR
- 🔍 Hex Viewer
- 📊 Comparação Forense entre Arquivos
- 📱 Análise de JSONs de biometria
- 📍 Geolocalização
- 🗺 Timeline Inteligente
- 📑 Snapshot para Laudos
- 📄 Exportação PDF
- 🤖 Motor de Correlação de Evidências
- 🧠 Temporal Consistency Engine

---

# 💡 Filosofia do Projeto

O objetivo do ForensiHash **não é apenas exibir informações técnicas**.

A proposta é fornecer uma plataforma capaz de correlacionar evidências digitais e auxiliar o raciocínio técnico-pericial durante a elaboração de laudos.

---

# ⚖️ Aviso

Este software encontra-se em desenvolvimento contínuo.

As informações apresentadas possuem caráter de apoio à perícia digital e não substituem a análise técnica realizada por profissional habilitado.

---

# 👨‍💻 Autor

**Rodrigo Galvão**

Auxiliar de perícia em Computação Forense

Estudante de Análise e Desenvolvimento de Sistemas — PUC Minas

---

# ⭐ Status

🚧 Em desenvolvimento ativo.

Novas funcionalidades são adicionadas continuamente por meio de sprints planejadas.

