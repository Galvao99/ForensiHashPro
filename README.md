# 🔍 ForensiHash Pro

> Plataforma de apoio à perícia digital voltada para análise de documentos eletrônicos, contratos digitais, metadados, assinaturas digitais e evidências computacionais.

<p align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue)
![PySide6](https://img.shields.io/badge/PySide6-Qt-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Status](https://img.shields.io/badge/status-In%20Development-yellow)

</p>

---

# 📖 Sobre

O **ForensiHash Pro** é um software em desenvolvimento destinado a auxiliar peritos, advogados e profissionais da computação forense na análise técnica de arquivos digitais.

O objetivo do projeto é reunir, em uma única plataforma, diversas análises que normalmente exigem o uso de várias ferramentas independentes, organizando os resultados de forma intuitiva e orientada ao raciocínio pericial.

---

# 🎯 Objetivos

- Automatizar análises repetitivas realizadas durante perícias digitais;
- Organizar evidências técnicas em um único ambiente;
- Auxiliar a elaboração de laudos periciais;
- Facilitar a identificação de inconsistências técnicas em documentos digitais;
- Fornecer uma interface moderna para análise forense.

---

# 🚀 Funcionalidades

## ✅ Implementadas

- Hashes (MD5, SHA1, SHA224, SHA256, SHA384 e SHA512)
- Extração de Metadados
- Motor de Vestígios Técnicos (Findings Engine)
- Magic Number (Assinatura Binária)
- Detecção de Assinaturas Digitais em PDF
- Extração de:
  - Assinante
  - Emissor
  - Número de Série
  - Vigência do Certificado
- Timeline inicial
- Interface modular por abas
- Arquitetura baseada em Engines

---

## 🚧 Em desenvolvimento

- Extração de Timestamp
- Algoritmo Criptográfico
- Data da Assinatura
- OCR
- Comparação entre Arquivos
- Snapshot para Laudos
- Exportação PDF
- Hex Viewer
- Comparação Byte a Byte
- Motor de Correlação de Evidências
- Temporal Consistency Engine

---

# 🏛 Arquitetura

```
ForensiHash

            UI

             │

      Analysis Tabs

             │

        AnalysisService

             │

        FileAnalyzer

             │

──────────────────────────────────────

Hash Engine

Metadata Engine

Magic Number Engine

Digital Signature Engine

Findings Engine

──────────────────────────────────────

             │

          Models
```

---

# 📂 Estrutura

```
app/

├── engines/
├── services/
├── models/
├── pages/
├── widgets/
├── digital_signature/
├── ui/
├── rules/
├── factory/
└── tests/
```

---

# 🖥 Interface

O sistema possui uma interface baseada em abas, permitindo que cada aspecto do arquivo seja analisado de forma independente.

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

---

# 📌 Roadmap

- [x] Hash Engine
- [x] Metadata Engine
- [x] Findings Engine
- [x] Magic Number
- [x] Digital Signature Foundation
- [ ] OCR
- [ ] Face Biometrics
- [ ] JSON Biometrics Analyzer
- [ ] Timeline Engine
- [ ] Evidence Explorer
- [ ] Hex Viewer
- [ ] Temporal Consistency Engine
- [ ] AI-assisted Technical Reports

---

# 💡 Diferenciais

O ForensiHash não busca apenas exibir informações técnicas.

Seu principal objetivo é correlacionar evidências digitais para auxiliar o raciocínio pericial, reduzindo o tempo gasto na utilização de múltiplas ferramentas independentes.

---

# 👨‍💻 Autor

**Rodrigo Galvão**

Perito em Computação Forense

Estudante de Análise e Desenvolvimento de Sistemas – PUC Minas

---

# ⚖️ Aviso

Este software encontra-se em desenvolvimento contínuo e não substitui a análise técnica realizada por profissional habilitado.

As informações fornecidas possuem caráter de apoio à perícia digital.